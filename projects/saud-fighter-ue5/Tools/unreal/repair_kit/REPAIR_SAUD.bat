@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SAUD - repair the Unreal Engine 5 project

rem ==========================================================================
rem  SAUD repair kit. Double-click this file.
rem
rem  It finds Unreal Engine 5.4, checks this PC and the game's files, moves
rem  the old build folders aside (Binaries, Intermediate, DerivedDataCache,
rem  .vs and the .sln - Unreal makes them again), makes the Visual Studio
rem  project files again, rebuilds the game code from nothing, sets the
rem  game's maps up again inside Unreal, and leaves ONE zip on the Desktop:
rem  SaudRepair_<date>.zip. Send that zip back, whatever happened.
rem
rem  Nothing is deleted from the game: the old build folders are MOVED to
rem  Saved\RepairKit\old_<date>. The next repair removes the previous
rem  old_ folder before it moves the new one, so only one is ever kept.
rem  Delete it yourself to free the space once the game opens.
rem
rem  To skip the long setup step, run it from a command prompt as:
rem      REPAIR_SAUD.bat quick
rem
rem  Written 2026-11-01 (Riyadh). It has never been run: there is no Windows
rem  and no Unreal where it was written. See README.txt beside it.
rem ==========================================================================

set "KIT=%~dp0"
if "%KIT:~-1%"=="\" set "KIT=%KIT:~0,-1%"
set "LOGS=%KIT%\logs"
if not exist "%LOGS%" mkdir "%LOGS%"
del /q "%LOGS%\*.log" "%LOGS%\*.txt" >nul 2>&1
set "KITLOG=%LOGS%\kit.log"
set "STEPS=8"
set "FAILED="
set "FILES_BAD="
set "MIN_FREE_GB=40"
set "PROJ="
set "UE_DIR="
set "STAMP="
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "try { [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow,'Arab Standard Time').ToString('yyyy-MM-dd_HH-mm') } catch { (Get-Date).ToString('yyyy-MM-dd_HH-mm') }"`) do set "STAMP=%%T"
if not defined STAMP set "STAMP=now"

call :say "SAUD repair kit - started %STAMP% (Riyadh time)"
call :say "Leave this window open. It tells you what it is doing, and when it is finished."

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 1 of %STEPS%: Finding Unreal Engine 5.4 and the game"
for %%P in ("%KIT%\..\..\..") do set "CAND=%%~fP"
if exist "%CAND%\SaudFighter.uproject" set "PROJ=%CAND%"
if defined PROJ goto have_proj
set "FAILED=The game folder was not found. This file must stay in Tools\unreal\repair_kit inside the saud-fighter-ue5 folder. If you opened it inside the zip, first extract the whole zip, then double-click it again."
goto pack
:have_proj
set "UPROJECT=%PROJ%\SaudFighter.uproject"
call :say "The game: %PROJ%"

for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\EpicGames\Unreal Engine\5.4" /v InstalledDirectory /reg:64 2^>nul ^| find /i "InstalledDirectory"') do set "UE_DIR=%%B"
if defined UE_DIR if not exist "%UE_DIR%\Engine\Binaries\Win64\UnrealEditor.exe" set "UE_DIR="
if not defined UE_DIR if exist "%ProgramFiles%\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor.exe" set "UE_DIR=%ProgramFiles%\Epic Games\UE_5.4"
set "TRIES=0"
:ask_ue
if defined UE_DIR goto have_ue
set /a TRIES+=1
if %TRIES% GTR 3 goto no_ue
call :say "Unreal Engine 5.4 was not found by itself."
set "ANSWER="
set /p "ANSWER=Type the Unreal Engine 5.4 folder, for example D:\Epic Games\UE_5.4, then press Enter: "
if not defined ANSWER goto ask_ue
set "ANSWER=!ANSWER:"=!"
if "!ANSWER:~-1!"=="\" set "ANSWER=!ANSWER:~0,-1!"
if exist "!ANSWER!\Engine\Binaries\Win64\UnrealEditor.exe" set "UE_DIR=!ANSWER!"
if not defined UE_DIR call :say "There is no Unreal editor in that folder. The right folder has Engine\Binaries\Win64\UnrealEditor.exe inside it."
goto ask_ue
:no_ue
set "FAILED=Unreal Engine 5.4 was not found. Install 5.4 from the Epic Games Launcher, then double-click this file again. If it is installed and still not found, open the Launcher, Library, the arrow next to 5.4, and press Verify."
goto pack
:have_ue
call :say "Unreal Engine 5.4: %UE_DIR%"

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 2 of %STEPS%: Checking this PC"
tasklist /FI "IMAGENAME eq UnrealEditor.exe" 2>nul | find /i "UnrealEditor.exe" >nul
if not errorlevel 1 goto ue_open
tasklist /FI "IMAGENAME eq UnrealEditor-Cmd.exe" 2>nul | find /i "UnrealEditor-Cmd.exe" >nul
if not errorlevel 1 goto ue_open
goto ue_closed
:ue_open
set "FAILED=Unreal Engine is open. Close every Unreal window - save your work first - then double-click this file again. The repair cannot move the build folders while Unreal is using them."
goto pack
:ue_closed
tasklist /FI "IMAGENAME eq devenv.exe" 2>nul | find /i "devenv.exe" >nul
if not errorlevel 1 call :say "WARNING: Visual Studio is open. If it has the game's solution open, close it now; the repair replaces that solution."
set "VS_CPP="
set "VSI=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
if not exist "%VSI%\vswhere.exe" goto vs_checked
pushd "%VSI%"
for /f "usebackq delims=" %%V in (`vswhere.exe -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property catalog_productLineVersion`) do if "%%V"=="2022" set "VS_CPP=1"
popd
:vs_checked
if defined VS_CPP goto vs_have
set "FAILED=Visual Studio 2022 with its C++ tools was not found. Install Visual Studio 2022 Community - it is free - and tick Game development with C++ in its installer, or open the Visual Studio Installer, press Modify and tick it. Then double-click this file again."
goto pack
:vs_have
call :say "Visual Studio 2022 with C++: found"
set "SDK="
set "KITS=%ProgramFiles(x86)%\Windows Kits\10\Include"
if not exist "%KITS%" goto sdk_checked
pushd "%KITS%"
for /d %%S in (10.*) do set "SDK=%%S"
popd
:sdk_checked
if defined SDK goto sdk_have
set "FAILED=The Windows 10 or 11 SDK is not installed. Open the Visual Studio Installer, press Modify, and under Individual components tick the newest Windows 11 SDK. Then double-click this file again."
goto pack
:sdk_have
call :say "Windows SDK: %SDK%"
set "DRV=%PROJ:~0,1%"
set "FREE_GB="
powershell -NoProfile -Command "[math]::Floor((Get-PSDrive -Name $env:DRV).Free / 1GB)" > "%LOGS%\free.txt" 2>nul
set /p FREE_GB=<"%LOGS%\free.txt"
echo(%FREE_GB%| findstr /r "^[0-9][0-9]*$" >nul || goto disk_checked
if %FREE_GB% LSS %MIN_FREE_GB% call :say "WARNING: only %FREE_GB% GB free on drive %DRV%. A rebuild needs about %MIN_FREE_GB% GB. Free some space if the build stops with a disk-full error."
if %FREE_GB% GEQ %MIN_FREE_GB% call :say "Free space on drive %DRV%: %FREE_GB% GB"
:disk_checked

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 3 of %STEPS%: Checking the game's files"
set "UE_PY=%UE_DIR%\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
if exist "%UE_PY%" goto py_have
call :say "WARNING: Unreal's own Python was not found, so the files were not checked. The rest of the repair goes on."
goto files_done
:py_have
"%UE_PY%" "%KIT%\repair_check.py" "%PROJ%" "%LOGS%\files_report.txt" > "%LOGS%\files.log" 2>&1
if errorlevel 1 set "FILES_BAD=1"
for /f "usebackq delims=" %%L in ("%LOGS%\files_report.txt") do call :say "  %%L"
if defined FILES_BAD call :say "Some of the game's files are damaged - see above. The repair goes on, but those files must be replaced from the branch for the game to work."
:files_done

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 4 of %STEPS%: Moving the old build folders aside - Unreal makes them again"
set "OLDROOT=%PROJ%\Saved\RepairKit"
set "OLD=%OLDROOT%\old_%STAMP%"
if not exist "%OLDROOT%" mkdir "%OLDROOT%"
for /d %%D in ("%OLDROOT%\old_*") do (
    call :say "Removing the folders an earlier repair kept: %%~nxD"
    rd /s /q "%%D"
)
mkdir "%OLD%" >nul 2>&1
set "MOVEFAIL="
call :moveaside Binaries
call :moveaside Intermediate
call :moveaside DerivedDataCache
call :moveaside .vs
call :moveaside SaudFighter.sln
if defined MOVEFAIL goto move_failed
call :say "The old build folders are in %OLD% - delete that folder once the game opens, to free the space."
goto moved
:move_failed
set "FAILED=%MOVEFAIL% could not be moved aside - a program is still using it. Close Unreal, Visual Studio and any Explorer window inside the game's folder, then double-click this file again."
goto pack
:moved

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 5 of %STEPS%: Making the Visual Studio project files again"
set "UBT=%UE_DIR%\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe"
if exist "%UBT%" goto ubt_have
call :say "WARNING: UnrealBuildTool was not found, so the project files were not made again. The build in the next step makes what it needs anyway."
goto files_made
:ubt_have
"%UBT%" -projectfiles -project="%UPROJECT%" -game -rocket -progress > "%LOGS%\projectfiles.log" 2>&1
if errorlevel 1 call :say "WARNING: the project files could not be made again - logs\projectfiles.log says why. The build in the next step goes on."
if not errorlevel 1 call :say "The Visual Studio project files were made again."
:files_made

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 6 of %STEPS%: Rebuilding the game code from nothing. This can take 10 to 40 minutes."
call "%UE_DIR%\Engine\Build\BatchFiles\Build.bat" SaudFighterEditor Win64 Development -Project="%UPROJECT%" -WaitMutex -FromMsBuild > "%LOGS%\build.log" 2>&1
set "BUILD_RC=%ERRORLEVEL%"
>>"%KITLOG%" echo Build.bat exit code: %BUILD_RC%
if "%BUILD_RC%"=="0" goto built
set "FAILED=The game code did not build. The reason is in logs\build.log, which is in the zip. Send the zip back."
goto pack
:built
call :say "The game code built."

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 7 of %STEPS%: Setting the game's maps and materials up again inside Unreal. This can take 30 to 90 minutes."
if /i "%~1"=="quick" goto setup_skip
choice /C RS /T 30 /D R /M "Press S to skip this long step, or R to do it. It does it by itself in 30 seconds."
if errorlevel 2 goto setup_skip
for %%P in ("%KIT%\..\render_kit\setup_all.py") do set "SETUP=%%~fP"
if exist "%SETUP%" goto setup_have
call :say "WARNING: the render kit's setup_all.py was not found beside this kit, so the setup was not redone."
goto setup_done
:setup_have
set "MARKER=%PROJ%\Saved\RenderKit\setup_done.txt"
if exist "%MARKER%" del /q "%MARKER%"
set "PY_TARGET=%PROJ%\Saved\RenderKitPython"
if exist "%PY_TARGET%\numpy\__init__.py" goto np_ready
if not exist "%UE_PY%" goto np_missing
call :say "Getting numpy for Unreal's own Python - the monkey island needs it. This needs the internet."
"%UE_PY%" -m pip install --disable-pip-version-check --no-warn-script-location --target "%PY_TARGET%" numpy pillow > "%LOGS%\pip.log" 2>&1
if exist "%PY_TARGET%\numpy\__init__.py" goto np_ready
:np_missing
call :say "WARNING: numpy could not be installed - logs\pip.log says why. The monkey island will be skipped; everything else goes on."
:np_ready
call :say "Unreal is now working without a window. Nothing will seem to happen for a long time. That is normal."
"%UE_DIR%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "%UPROJECT%" -run=pythonscript -script="%SETUP%" -unattended -nosplash -stdout -FullStdOutLogOutput > "%LOGS%\setup.log" 2>&1
>>"%KITLOG%" echo setup exit code: %ERRORLEVEL%
if exist "%MARKER%" goto setup_ok
set "FAILED=The setup inside Unreal stopped before its end. logs\setup.log and Saved\RenderKit\setup_report.txt say where. Send the zip back."
goto pack
:setup_ok
for /f "usebackq delims=" %%L in ("%MARKER%") do call :say "Setup: %%L"
goto setup_done
:setup_skip
call :say "Skipped. The maps and materials are as they were."
:setup_done

rem --------------------------------------------------------------------------
:pack
call :say ""
if defined FAILED call :say "STOPPED: %FAILED%"
if not defined FAILED if not defined FILES_BAD call :say "REPAIRED: the game code was rebuilt from nothing. Open SaudFighter.uproject to check."
if not defined FAILED if defined FILES_BAD call :say "REBUILT, BUT some of the game's files are damaged - logs\files_report.txt lists them. Replace them from the branch."
call :say "STEP 8 of %STEPS%: Packing every log into one zip on your Desktop"
set "Z_KITLOGS=%LOGS%"
set "Z_KITLOG=%KITLOG%"
set "Z_UELOGS="
set "Z_SETUP="
if defined PROJ set "Z_UELOGS=%PROJ%\Saved\Logs"
if defined PROJ set "Z_SETUP=%PROJ%\Saved\RenderKit\setup_report.txt"
set "Z_STAMP=%STAMP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Continue'; $desk=[Environment]::GetFolderPath('Desktop'); if (-not $desk) { $desk=$env:USERPROFILE }; $zip=Join-Path $desk ('SaudRepair_'+$env:Z_STAMP+'.zip'); $st=Join-Path $env:TEMP ('SaudRepair_'+$env:Z_STAMP); if (Test-Path $st) { Remove-Item $st -Recurse -Force }; New-Item -ItemType Directory -Force -Path $st | Out-Null; if (Test-Path $env:Z_KITLOGS) { Copy-Item -Path $env:Z_KITLOGS -Destination (Join-Path $st 'logs') -Recurse -Force }; if ($env:Z_SETUP -and (Test-Path $env:Z_SETUP)) { Copy-Item -Path $env:Z_SETUP -Destination $st -Force }; $ue=Join-Path $st 'UnrealLogs'; New-Item -ItemType Directory -Force -Path $ue | Out-Null; if ($env:Z_UELOGS -and (Test-Path $env:Z_UELOGS)) { Get-ChildItem -Path $env:Z_UELOGS -Filter '*.log' -File | Copy-Item -Destination $ue -Force }; if (Test-Path $zip) { Remove-Item $zip -Force }; Compress-Archive -Path (Join-Path $st '*') -DestinationPath $zip -Force; if (Test-Path $zip) { Add-Content -Path $env:Z_KITLOG -Value ('Send this file back: '+$zip); Write-Host ''; Write-Host ('Send this file back: '+$zip) -ForegroundColor Green; Start-Process explorer.exe -ArgumentList ('/select,'+[char]34+$zip+[char]34); exit 0 } else { Write-Host 'The zip could not be made. Send this folder instead:' -ForegroundColor Red; Write-Host $env:Z_KITLOGS; exit 1 }"

call :say ""
call :say "Finished. You can close this window."
pause
endlocal
exit /b 0

rem --------------------------------------------------------------------------
rem  call :moveaside NAME -- %PROJ%\NAME into %OLD%, if it is there
:moveaside
if not exist "%PROJ%\%~1" exit /b 0
move "%PROJ%\%~1" "%OLD%\%~1" >nul 2>&1
if errorlevel 1 set "MOVEFAIL=%~1"
if not errorlevel 1 call :say "Moved %~1 aside."
exit /b 0

rem  call :say "text" -- the line on screen and in logs\kit.log
:say
echo(%~1
>>"%KITLOG%" echo(%~1
exit /b 0
