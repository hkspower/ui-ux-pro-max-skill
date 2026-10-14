@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SAUD - render with Unreal Engine 5

rem ==========================================================================
rem  SAUD render kit. Double-click this file.
rem
rem  It finds Unreal Engine 5.4, checks this PC, builds the game code, sets
rem  the game's maps up inside Unreal (once), renders the pictures, and
rem  leaves ONE zip on the Desktop: SaudRenders_<date>.zip. Send that zip
rem  back, whatever happened -- it holds the pictures and every log.
rem
rem  To redo the setup step from scratch, run it from a command prompt as:
rem      RENDER_SAUD.bat fresh
rem  (or press R when it asks).
rem
rem  Written 2026-10-14 (Riyadh). It has never been run: there is no Windows
rem  and no Unreal where it was written. See README.txt beside it.
rem ==========================================================================

set "KIT=%~dp0"
if "%KIT:~-1%"=="\" set "KIT=%KIT:~0,-1%"
set "LOGS=%KIT%\logs"
if not exist "%LOGS%" mkdir "%LOGS%"
del /q "%LOGS%\*.log" "%LOGS%\*.txt" >nul 2>&1
set "KITLOG=%LOGS%\kit.log"
set "STEPS=6"
set "FAILED="
set "WATCHDOG_MINUTES=90"
set "MIN_FREE_GB=40"
set "PROJ="
set "UE_DIR="

call :say "SAUD render kit - started %date% %time%"
call :say "Leave this window open. It tells you what it is doing, and when it is finished."

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 1 of %STEPS%: Finding Unreal Engine 5.4 and the game"
for %%P in ("%KIT%\..\..\..") do set "CAND=%%~fP"
if exist "%CAND%\SaudFighter.uproject" set "PROJ=%CAND%"
if defined PROJ goto have_proj
for %%P in ("%KIT%\..\..") do set "CAND=%%~fP"
if exist "%CAND%\SaudFighter.uproject" set "PROJ=%CAND%"
if defined PROJ goto have_proj
set "FAILED=The game folder was not found. This file must stay in Tools\unreal\render_kit inside the saud-fighter-ue5 folder. If you opened it inside the zip, first extract the whole zip, then double-click it again."
goto pack
:have_proj
set "UPROJECT=%PROJ%\SaudFighter.uproject"
call :say "The game: %PROJ%"
if not "%PROJ:~100,1%"=="" call :say "WARNING: the game folder path is long. Unreal can fail on long paths. If the build fails, move the folder to C:\SAUD and try again."

for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\EpicGames\Unreal Engine\5.4" /v InstalledDirectory /reg:64 2^>nul ^| find /i "InstalledDirectory"') do set "UE_DIR=%%B"
if defined UE_DIR if not exist "%UE_DIR%\Engine\Binaries\Win64\UnrealEditor.exe" set "UE_DIR="
if not defined UE_DIR if exist "C:\Program Files\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor.exe" set "UE_DIR=C:\Program Files\Epic Games\UE_5.4"
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
set "FAILED=Unreal Engine 5.4 was not found. Install 5.4 from the Epic Games Launcher, then double-click this file again."
goto pack
:have_ue
call :say "Unreal Engine 5.4: %UE_DIR%"
>>"%KITLOG%" echo engine folder: %UE_DIR%

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 2 of %STEPS%: Checking this PC has what Unreal needs to build the game"
set "VS_ANY="
set "VS_CPP="
set "VS_GAME="
set "VSI=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
if not exist "%VSI%\vswhere.exe" goto vs_checked
pushd "%VSI%"
for /f "usebackq delims=" %%V in (`vswhere.exe -products * -property catalog_productLineVersion`) do if "%%V"=="2022" set "VS_ANY=1"
for /f "usebackq delims=" %%V in (`vswhere.exe -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property catalog_productLineVersion`) do if "%%V"=="2022" set "VS_CPP=1"
for /f "usebackq delims=" %%V in (`vswhere.exe -products * -requires Microsoft.VisualStudio.Workload.NativeGame -property catalog_productLineVersion`) do if "%%V"=="2022" set "VS_GAME=1"
popd
:vs_checked
if defined VS_ANY goto vs_have
set "FAILED=Visual Studio 2022 is not installed. Install Visual Studio 2022 Community - it is free - and tick Game development with C++ in the installer. Then double-click this file again."
goto pack
:vs_have
if defined VS_CPP goto vs_cpp
set "FAILED=Visual Studio 2022 is installed, but without its C++ tools. Open the Visual Studio Installer, press Modify, tick Game development with C++, install, then double-click this file again."
goto pack
:vs_cpp
if not defined VS_GAME call :say "WARNING: Visual Studio 2022 has C++ but not the Game development with C++ workload. The build may still work. If it fails, add that workload in the Visual Studio Installer."
if defined VS_GAME call :say "Visual Studio 2022 with Game development with C++: found"

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
if %FREE_GB% LSS %MIN_FREE_GB% call :say "WARNING: only %FREE_GB% GB free on drive %DRV%. Unreal needs about %MIN_FREE_GB% GB. It will try anyway, but it may stop with a disk-full error."
if %FREE_GB% GEQ %MIN_FREE_GB% call :say "Free space on drive %DRV%: %FREE_GB% GB"
:disk_checked
powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController).Name; [Environment]::OSVersion.VersionString" > "%LOGS%\pc.txt" 2>nul
for /f "usebackq delims=" %%G in ("%LOGS%\pc.txt") do call :say "This PC: %%G"

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 3 of %STEPS%: Building the game code. The first time can take 10 to 40 minutes."
call :say "The game code has never been built before, so this step may fail. That is expected, and the log it leaves is exactly what is needed."
call "%UE_DIR%\Engine\Build\BatchFiles\Build.bat" SaudFighterEditor Win64 Development -Project="%UPROJECT%" -WaitMutex -FromMsBuild > "%LOGS%\build.log" 2>&1
set "BUILD_RC=%ERRORLEVEL%"
>>"%KITLOG%" echo Build.bat exit code: %BUILD_RC%
if "%BUILD_RC%"=="0" goto built
set "FAILED=The game code did not build - expected on the very first try. The reason is in logs\build.log, which is in the zip. Send the zip back."
goto pack
:built
call :say "The game code built."

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 4 of %STEPS%: Setting the game's maps and materials up inside Unreal. The first time can take 30 to 90 minutes."
set "MARKER=%PROJ%\Saved\RenderKit\setup_done.txt"
if /i "%~1"=="fresh" goto do_setup
if not exist "%MARKER%" goto do_setup
call :say "The setup was already done on an earlier run."
choice /C KR /T 20 /D K /M "Press K to keep it, or R to redo it. It keeps it by itself in 20 seconds."
if errorlevel 2 goto do_setup
call :say "Keeping the earlier setup."
goto setup_summary
:do_setup
if exist "%MARKER%" del /q "%MARKER%"
set "UE_PY=%UE_DIR%\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
set "PY_TARGET=%PROJ%\Saved\RenderKitPython"
if exist "%PY_TARGET%\numpy\__init__.py" goto py_ready
if not exist "%UE_PY%" goto py_missing
call :say "Getting numpy for Unreal's own Python - the monkey island needs it. This needs the internet."
"%UE_PY%" -m pip install --disable-pip-version-check --no-warn-script-location --target "%PY_TARGET%" numpy pillow > "%LOGS%\pip.log" 2>&1
if exist "%PY_TARGET%\numpy\__init__.py" goto py_ready
:py_missing
call :say "WARNING: numpy could not be installed - logs\pip.log says why. The monkey island will be skipped; everything else goes on."
:py_ready
call :say "Unreal is now working without a window. Nothing will seem to happen for a long time. That is normal."
"%UE_DIR%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "%UPROJECT%" -run=pythonscript -script="%KIT%\setup_all.py" -unattended -nosplash -stdout -FullStdOutLogOutput > "%LOGS%\setup.log" 2>&1
>>"%KITLOG%" echo setup exit code: %ERRORLEVEL%
if exist "%MARKER%" goto setup_summary
set "FAILED=The setup inside Unreal stopped before its end. logs\setup.log and Saved\RenderKit\setup_report.txt say where. Send the zip back."
goto pack
:setup_summary
for /f "usebackq delims=" %%L in ("%MARKER%") do call :say "Setup: %%L"
call :say "Setup details: %PROJ%\Saved\RenderKit\setup_report.txt"

rem --------------------------------------------------------------------------
call :say ""
call :say "STEP 5 of %STEPS%: Rendering the pictures. Unreal opens its window - do not close it. It closes by itself when done, at most %WATCHDOG_MINUTES% minutes."
set "W_EXE=%UE_DIR%\Engine\Binaries\Win64\UnrealEditor.exe"
set "W_ARGS="%UPROJECT%" -ExecutePythonScript="%KIT%\render_views.py" -unattended -nosplash -log"
set "W_REPORT=%PROJ%\Saved\RenderKit\render_report.txt"
set "W_MINUTES=%WATCHDOG_MINUTES%"
if exist "%W_REPORT%" del /q "%W_REPORT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $p=Start-Process -FilePath $env:W_EXE -ArgumentList $env:W_ARGS -PassThru; $t0=Get-Date; $fin=$null; $rc=0; while (-not $p.HasExited) { Start-Sleep -Seconds 15; $now=Get-Date; if (($null -eq $fin) -and (Test-Path $env:W_REPORT)) { $fin=$now; Write-Host 'The pictures are done. Waiting for Unreal to close by itself.' }; if (($null -ne $fin) -and (($now-$fin).TotalMinutes -gt 3)) { Write-Host 'Unreal did not close by itself, so it is being closed now.'; & taskkill.exe /T /F /PID $p.Id | Out-Null; $rc=2; break }; if (($now-$t0).TotalMinutes -gt [double]$env:W_MINUTES) { Write-Host ('Unreal ran for more than '+$env:W_MINUTES+' minutes, so it is being stopped. The logs are still sent.'); & taskkill.exe /T /F /PID $p.Id | Out-Null; $rc=3; break } }; exit $rc"
set "WATCH_RC=%ERRORLEVEL%"
>>"%KITLOG%" echo render watchdog exit code: %WATCH_RC%
if "%WATCH_RC%"=="1" call :say "WARNING: Unreal's window could not be started. The zip has the logs."
if "%WATCH_RC%"=="3" call :say "WARNING: the rendering ran out of time and was stopped. The pictures made before that are in the zip."
set "SHOTS=0"
for %%F in ("%PROJ%\Saved\RenderKit\*.png") do set /a SHOTS+=1
call :say "Pictures made: %SHOTS%"
if exist "%W_REPORT%" call :say "Render details: %W_REPORT%"
if not exist "%W_REPORT%" call :say "WARNING: there is no render report; the logs in the zip say what happened."

rem --------------------------------------------------------------------------
:pack
call :say ""
if defined FAILED call :say "STOPPED: %FAILED%"
call :say "STEP 6 of %STEPS%: Packing the pictures and every log into one zip on your Desktop"
set "Z_RK="
set "Z_UELOGS="
if defined PROJ set "Z_RK=%PROJ%\Saved\RenderKit"
if defined PROJ set "Z_UELOGS=%PROJ%\Saved\Logs"
set "Z_KITLOGS=%LOGS%"
set "Z_KITLOG=%KITLOG%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Continue'; try { $t=[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow,'Arab Standard Time') } catch { $t=Get-Date }; $stamp=$t.ToString('yyyy-MM-dd_HH-mm'); $desk=[Environment]::GetFolderPath('Desktop'); if (-not $desk) { $desk=$env:USERPROFILE }; $zip=Join-Path $desk ('SaudRenders_'+$stamp+'.zip'); $st=Join-Path $env:TEMP ('SaudRenders_'+$stamp); if (Test-Path $st) { Remove-Item $st -Recurse -Force }; New-Item -ItemType Directory -Force -Path $st | Out-Null; if ($env:Z_RK -and (Test-Path $env:Z_RK)) { Copy-Item -Path $env:Z_RK -Destination (Join-Path $st 'RenderKit') -Recurse -Force }; if ($env:Z_KITLOGS -and (Test-Path $env:Z_KITLOGS)) { Copy-Item -Path $env:Z_KITLOGS -Destination (Join-Path $st 'logs') -Recurse -Force }; $ue=Join-Path $st 'UnrealLogs'; New-Item -ItemType Directory -Force -Path $ue | Out-Null; if ($env:Z_UELOGS -and (Test-Path $env:Z_UELOGS)) { Get-ChildItem -Path $env:Z_UELOGS -Filter '*.log' -File | Copy-Item -Destination $ue -Force }; if (Test-Path $zip) { Remove-Item $zip -Force }; Compress-Archive -Path (Join-Path $st '*') -DestinationPath $zip -Force; if (Test-Path $zip) { Add-Content -Path $env:Z_KITLOG -Value ('Send this file back: '+$zip); Write-Host ''; Write-Host ('Send this file back: '+$zip) -ForegroundColor Green; Start-Process explorer.exe -ArgumentList ('/select,'+[char]34+$zip+[char]34); exit 0 } else { Write-Host 'The zip could not be made. Send these folders instead:' -ForegroundColor Red; Write-Host $env:Z_RK; Write-Host $env:Z_KITLOGS; Write-Host $env:Z_UELOGS; exit 1 }"

call :say ""
call :say "Finished. You can close this window."
pause
endlocal
exit /b 0

rem --------------------------------------------------------------------------
rem  call :say "text" -- the line on screen and in logs\kit.log
:say
echo(%~1
>>"%KITLOG%" echo(%~1
exit /b 0
