#!/bin/bash
# ==========================================================================
#  SAUD repair kit for a Mac. Double-click this file.
#
#  It finds Unreal Engine 5.4, checks this Mac and the game's files, moves
#  the old build folders aside (Binaries, Intermediate, DerivedDataCache
#  and the Xcode workspace - Unreal makes them again), makes the Xcode
#  project files again, rebuilds the game code from nothing, sets the
#  game's maps up again inside Unreal, and leaves ONE zip on the Desktop:
#  SaudRepair_<date>.zip. Send that zip back, whatever happened.
#
#  Nothing is deleted from the game: the old build folders are MOVED to
#  Saved/RepairKit/old_<date>. The next repair removes the previous old_
#  folder before it moves the new one, so only one is ever kept. Delete
#  it yourself to free the space once the game opens.
#
#  To skip the long setup step, run it in Terminal as:
#      bash REPAIR_SAUD_MAC.command quick
#
#  Written 2026-11-01 (Riyadh) for an Apple Silicon MacBook. It has never
#  been run: there is no Mac and no Unreal where it was written. See
#  README_MAC.txt beside it.
# ==========================================================================

set -u

KIT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$KIT/logs"
mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$LOGS"/*.txt 2>/dev/null
KITLOG="$LOGS/kit.log"
STEPS=8
FAILED=""
FILES_BAD=""
MIN_FREE_GB=40
PROJ=""
UE_DIR=""
UE_PY=""
QUICK="${1:-}"
STAMP="$(TZ=Asia/Riyadh date '+%Y-%m-%d_%H-%M')"

say() {
    echo "$1"
    echo "$1" >> "$KITLOG"
}

say "SAUD repair kit (Mac) - started $STAMP (Riyadh time)"
say "Leave this window open. It tells you what it is doing, and when it is finished."

# --------------------------------------------------------------------------
step1() {
    say ""
    say "STEP 1 of $STEPS: Finding Unreal Engine 5.4 and the game"
    if [ -f "$KIT/../../../SaudFighter.uproject" ]; then
        PROJ="$(cd "$KIT/../../.." && pwd)"
    else
        FAILED="The game folder was not found. This file must stay in Tools/unreal/repair_kit inside the saud-fighter-ue5 folder. If you opened it inside the zip, first extract the whole zip, then double-click it again."
        return 1
    fi
    UPROJECT="$PROJ/SaudFighter.uproject"
    say "The game: $PROJ"
    local cand
    for cand in "/Users/Shared/Epic Games/UE_5.4" "$HOME/Epic Games/UE_5.4" /Users/Shared/Epic\ Games/UE_5.4*; do
        if [ -d "$cand/Engine/Binaries/Mac" ]; then UE_DIR="$cand"; break; fi
    done
    local tries=0
    while [ -z "$UE_DIR" ] && [ $tries -lt 3 ]; do
        tries=$((tries + 1))
        say "Unreal Engine 5.4 was not found by itself."
        printf "Drag the UE_5.4 folder into this window (or type its path), then press Return: "
        local answer=""
        read -r answer
        answer="${answer%/}"
        answer="${answer#\'}"; answer="${answer%\'}"
        answer="${answer//\\ / }"
        if [ -n "$answer" ] && [ -d "$answer/Engine/Binaries/Mac" ]; then
            UE_DIR="$answer"
        else
            say "There is no Unreal Engine in that folder. The right folder has Engine/Binaries/Mac inside it."
        fi
    done
    if [ -z "$UE_DIR" ]; then
        FAILED="Unreal Engine 5.4 was not found. Install 5.4 from the Epic Games Launcher for Mac, then double-click this file again. If it is installed and still not found, open the Launcher, Library, the arrow next to 5.4, and press Verify."
        return 1
    fi
    say "Unreal Engine 5.4: $UE_DIR"
    return 0
}

# --------------------------------------------------------------------------
step2() {
    say ""
    say "STEP 2 of $STEPS: Checking this Mac"
    if pgrep -x UnrealEditor >/dev/null 2>&1 || pgrep -x UnrealEditor-Cmd >/dev/null 2>&1; then
        FAILED="Unreal Engine is open. Close every Unreal window - save your work first - then double-click this file again. The repair cannot move the build folders while Unreal is using them."
        return 1
    fi
    if pgrep -x Xcode >/dev/null 2>&1; then
        say "WARNING: Xcode is open. If it has the game's workspace open, close it now; the repair replaces that workspace."
    fi
    if ! xcode-select -p >/dev/null 2>&1 || ! xcodebuild -version >/dev/null 2>&1; then
        FAILED="Xcode is not installed (the full Xcode app, not only its command line tools). Install Xcode from the App Store, open it once and let it finish installing its parts, then double-click this file again."
        return 1
    fi
    case "$(xcode-select -p)" in
        */CommandLineTools*)
            FAILED="Only Apple's command line tools are selected, not Xcode itself. Open Terminal and run:  sudo xcode-select -s /Applications/Xcode.app  (it asks for your Mac password), then double-click this file again."
            return 1 ;;
    esac
    say "Xcode: $(xcodebuild -version 2>/dev/null | head -1)"
    local free_gb
    free_gb=$(df -g "$PROJ" 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -n "$free_gb" ]; then
        if [ "$free_gb" -lt "$MIN_FREE_GB" ] 2>/dev/null; then
            say "WARNING: only $free_gb GB free. A rebuild needs about $MIN_FREE_GB GB. Free some space if the build stops with a disk-full error."
        else
            say "Free space: $free_gb GB"
        fi
    fi
    return 0
}

# --------------------------------------------------------------------------
step3() {
    say ""
    say "STEP 3 of $STEPS: Checking the game's files"
    UE_PY="$UE_DIR/Engine/Binaries/ThirdParty/Python3/Mac/bin/python3"
    if [ ! -x "$UE_PY" ]; then
        UE_PY="$(find "$UE_DIR/Engine/Binaries/ThirdParty/Python3/Mac" -maxdepth 3 -name python3 -type f -perm -u+x 2>/dev/null | head -1)"
    fi
    if [ -z "$UE_PY" ]; then
        say "WARNING: Unreal's own Python was not found, so the files were not checked. The rest of the repair goes on."
        return 0
    fi
    "$UE_PY" "$KIT/repair_check.py" "$PROJ" "$LOGS/files_report.txt" > "$LOGS/files.log" 2>&1 || FILES_BAD=1
    local line
    while IFS= read -r line; do say "  $line"; done < "$LOGS/files_report.txt"
    if [ -n "$FILES_BAD" ]; then
        say "Some of the game's files are damaged - see above. The repair goes on, but those files must be replaced from the branch for the game to work."
    fi
    return 0
}

# --------------------------------------------------------------------------
step4() {
    say ""
    say "STEP 4 of $STEPS: Moving the old build folders aside - Unreal makes them again"
    local oldroot="$PROJ/Saved/RepairKit" old d name
    old="$oldroot/old_$STAMP"
    mkdir -p "$oldroot"
    for d in "$oldroot"/old_*; do
        [ -d "$d" ] || continue
        say "Removing the folders an earlier repair kept: $(basename "$d")"
        rm -rf "$d"
    done
    mkdir -p "$old"
    for name in Binaries Intermediate DerivedDataCache SaudFighter.xcworkspace "SaudFighter (Mac).xcworkspace"; do
        [ -e "$PROJ/$name" ] || continue
        if mv "$PROJ/$name" "$old/$name" 2>/dev/null; then
            say "Moved $name aside."
        else
            FAILED="$name could not be moved aside - a program is still using it. Close Unreal, Xcode and any Finder window inside the game's folder, then double-click this file again."
            return 1
        fi
    done
    say "The old build folders are in $old - delete that folder once the game opens, to free the space."
    return 0
}

# --------------------------------------------------------------------------
step5() {
    say ""
    say "STEP 5 of $STEPS: Making the Xcode project files again"
    local gen="$UE_DIR/Engine/Build/BatchFiles/Mac/GenerateProjectFiles.sh"
    if [ ! -x "$gen" ]; then
        say "WARNING: GenerateProjectFiles.sh was not found, so the project files were not made again. The build in the next step makes what it needs anyway."
        return 0
    fi
    if "$gen" -project="$UPROJECT" -game > "$LOGS/projectfiles.log" 2>&1; then
        say "The Xcode project files were made again."
    else
        say "WARNING: the project files could not be made again - logs/projectfiles.log says why. The build in the next step goes on."
    fi
    return 0
}

# --------------------------------------------------------------------------
step6() {
    say ""
    say "STEP 6 of $STEPS: Rebuilding the game code from nothing. This can take 10 to 40 minutes."
    "$UE_DIR/Engine/Build/BatchFiles/Mac/Build.sh" SaudFighterEditor Mac Development -Project="$UPROJECT" -WaitMutex > "$LOGS/build.log" 2>&1
    local rc=$?
    echo "Build.sh exit code: $rc" >> "$KITLOG"
    if [ $rc -ne 0 ]; then
        FAILED="The game code did not build. The reason is in logs/build.log, which is in the zip. Send the zip back."
        return 1
    fi
    say "The game code built."
    return 0
}

editor_cmd() {
    local c
    for c in "$UE_DIR/Engine/Binaries/Mac/UnrealEditor-Cmd" \
             "$UE_DIR/Engine/Binaries/Mac/UnrealEditor-Cmd.app/Contents/MacOS/UnrealEditor-Cmd" \
             "$UE_DIR/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"; do
        if [ -x "$c" ]; then echo "$c"; return 0; fi
    done
    return 1
}

# --------------------------------------------------------------------------
step7() {
    say ""
    say "STEP 7 of $STEPS: Setting the game's maps and materials up again inside Unreal. This can take 30 to 90 minutes."
    if [ "$QUICK" = "quick" ]; then say "Skipped. The maps and materials are as they were."; return 0; fi
    local answer="R"
    read -r -t 30 -p "Press S then Return to skip this long step, or wait 30 seconds to do it: " answer
    echo ""
    case "$answer" in s|S) say "Skipped. The maps and materials are as they were."; return 0 ;; esac
    local setup
    setup="$(cd "$KIT/../render_kit" 2>/dev/null && pwd)/setup_all.py"
    if [ ! -f "$setup" ]; then
        say "WARNING: the render kit's setup_all.py was not found beside this kit, so the setup was not redone."
        return 0
    fi
    local marker="$PROJ/Saved/RenderKit/setup_done.txt"
    rm -f "$marker"
    local py_target="$PROJ/Saved/RenderKitPython"
    if [ ! -f "$py_target/numpy/__init__.py" ] && [ -n "$UE_PY" ]; then
        say "Getting numpy for Unreal's own Python - the monkey island needs it. This needs the internet."
        "$UE_PY" -m pip install --disable-pip-version-check --no-warn-script-location --target "$py_target" numpy pillow > "$LOGS/pip.log" 2>&1
    fi
    if [ ! -f "$py_target/numpy/__init__.py" ]; then
        say "WARNING: numpy could not be installed - logs/pip.log says why. The monkey island will be skipped; everything else goes on."
    fi
    local cmd
    if ! cmd="$(editor_cmd)"; then
        FAILED="Unreal's editor program was not found inside $UE_DIR/Engine/Binaries/Mac. Reinstall 5.4 from the Epic Games Launcher (Library, the arrow next to 5.4, Verify), then double-click this file again."
        return 1
    fi
    say "Unreal is now working without a window. Nothing will seem to happen for a long time. That is normal."
    "$cmd" "$UPROJECT" -run=pythonscript -script="$setup" -unattended -nosplash -stdout -FullStdOutLogOutput > "$LOGS/setup.log" 2>&1
    echo "setup exit code: $?" >> "$KITLOG"
    if [ ! -f "$marker" ]; then
        FAILED="The setup inside Unreal stopped before its end. logs/setup.log and Saved/RenderKit/setup_report.txt say where. Send the zip back."
        return 1
    fi
    local line
    while IFS= read -r line; do say "Setup: $line"; done < "$marker"
    return 0
}

# --------------------------------------------------------------------------
pack() {
    say ""
    if [ -n "$FAILED" ]; then
        say "STOPPED: $FAILED"
    elif [ -n "$FILES_BAD" ]; then
        say "REBUILT, BUT some of the game's files are damaged - logs/files_report.txt lists them. Replace them from the branch."
    else
        say "REPAIRED: the game code was rebuilt from nothing. Open SaudFighter.uproject to check."
    fi
    say "STEP 8 of $STEPS: Packing every log into one zip on your Desktop"
    local desk stage zip
    desk="$HOME/Desktop"
    [ -d "$desk" ] || desk="$HOME"
    stage="${TMPDIR:-/tmp}/SaudRepair_$STAMP"
    zip="$desk/SaudRepair_$STAMP.zip"
    rm -rf "$stage"; mkdir -p "$stage/UnrealLogs"
    cp -R "$LOGS" "$stage/logs" 2>/dev/null
    if [ -n "$PROJ" ]; then
        cp "$PROJ/Saved/RenderKit/setup_report.txt" "$stage/" 2>/dev/null
        cp "$PROJ/Saved/Logs/"*.log "$stage/UnrealLogs/" 2>/dev/null
    fi
    rm -f "$zip"
    if ditto -c -k --sequesterRsrc "$stage" "$zip" 2>/dev/null && [ -f "$zip" ]; then
        echo "Send this file back: $zip" >> "$KITLOG"
        echo ""
        echo "Send this file back: $zip"
        open -R "$zip" 2>/dev/null
    else
        echo "The zip could not be made. Send this folder instead:"
        echo "  $LOGS"
    fi
}

# --------------------------------------------------------------------------
if step1 && step2 && step3 && step4 && step5 && step6; then
    step7
fi
pack
say ""
say "Finished. You can close this window."
