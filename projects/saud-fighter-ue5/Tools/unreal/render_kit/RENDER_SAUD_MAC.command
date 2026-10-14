#!/bin/bash
# ==========================================================================
#  SAUD render kit for a Mac. Double-click this file.
#
#  It finds Unreal Engine 5.4, checks this Mac, builds the game code, sets
#  the game's maps up inside Unreal (once), renders the pictures, and
#  leaves ONE zip on the Desktop: SaudRenders_<date>.zip. Send that zip
#  back, whatever happened -- it holds the pictures and every log.
#
#  To redo the setup step from scratch, run it in Terminal as:
#      bash RENDER_SAUD_MAC.command fresh
#
#  Written 2026-10-14 (Riyadh) for an Apple Silicon MacBook. It has never
#  been run: there is no Mac and no Unreal where it was written. The same
#  setup_all.py and render_views.py as the Windows kit do the work inside
#  Unreal. See README_MAC.txt beside it.
# ==========================================================================

set -u

KIT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$KIT/logs"
mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$LOGS"/*.txt 2>/dev/null
KITLOG="$LOGS/kit.log"
STEPS=6
FAILED=""
WATCHDOG_MINUTES=90
MIN_FREE_GB=40
PROJ=""
UE_DIR=""
FRESH="${1:-}"

say() {
    echo "$1"
    echo "$1" >> "$KITLOG"
}

say "SAUD render kit (Mac) - started $(TZ=Asia/Riyadh date '+%Y-%m-%d %H:%M') Riyadh time"
say "Leave this window open. It tells you what it is doing, and when it is finished."

# --------------------------------------------------------------------------
step1() {
    say ""
    say "STEP 1 of $STEPS: Finding Unreal Engine 5.4 and the game"
    local cand
    for cand in "$KIT/../../.." "$KIT/../.."; do
        if [ -f "$cand/SaudFighter.uproject" ]; then
            PROJ="$(cd "$cand" && pwd)"
            break
        fi
    done
    if [ -z "$PROJ" ]; then
        FAILED="The game folder was not found. This file must stay in Tools/unreal/render_kit inside the saud-fighter-ue5 folder. If you opened it inside the zip, first extract the whole zip, then double-click it again."
        return 1
    fi
    UPROJECT="$PROJ/SaudFighter.uproject"
    say "The game: $PROJ"
    case "$PROJ" in
        "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
            say "NOTE: the game is in Desktop, Documents or Downloads. If macOS asks whether Terminal may open files there, press Allow." ;;
    esac

    for cand in "/Users/Shared/Epic Games/UE_5.4" "$HOME/Epic Games/UE_5.4" /Users/Shared/Epic\ Games/UE_5.4*; do
        if [ -d "$cand/Engine/Binaries/Mac" ]; then
            UE_DIR="$cand"
            break
        fi
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
        FAILED="Unreal Engine 5.4 was not found. Install 5.4 from the Epic Games Launcher for Mac, then double-click this file again."
        return 1
    fi
    say "Unreal Engine 5.4: $UE_DIR"
    return 0
}

# --------------------------------------------------------------------------
step2() {
    say ""
    say "STEP 2 of $STEPS: Checking this Mac has what Unreal needs to build the game"
    say "This Mac: $(sw_vers -productName 2>/dev/null) $(sw_vers -productVersion 2>/dev/null), $(uname -m), $(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
    if [ "$(uname -m)" != "arm64" ]; then
        say "NOTE: this is not an Apple Silicon Mac. The kit was written for one; it may still work."
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
    if ! xcodebuild -checkFirstLaunchStatus >/dev/null 2>&1; then
        say "WARNING: Xcode has not finished its first launch or its licence is not accepted. If the build fails, open Xcode once, or run in Terminal:  sudo xcodebuild -license accept"
    fi
    local free_gb
    free_gb=$(df -g "$PROJ" 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -n "$free_gb" ]; then
        if [ "$free_gb" -lt "$MIN_FREE_GB" ] 2>/dev/null; then
            say "WARNING: only $free_gb GB free. Unreal needs about $MIN_FREE_GB GB. It will try anyway, but it may stop with a disk-full error."
        else
            say "Free space: $free_gb GB"
        fi
    fi
    return 0
}

# --------------------------------------------------------------------------
step3() {
    say ""
    say "STEP 3 of $STEPS: Building the game code. The first time can take 10 to 40 minutes."
    say "The game code has never been built before, so this step may fail. That is expected, and the log it leaves is exactly what is needed."
    "$UE_DIR/Engine/Build/BatchFiles/Mac/Build.sh" SaudFighterEditor Mac Development -Project="$UPROJECT" -WaitMutex > "$LOGS/build.log" 2>&1
    local rc=$?
    echo "Build.sh exit code: $rc" >> "$KITLOG"
    if [ $rc -ne 0 ]; then
        FAILED="The game code did not build - expected on the very first try. The reason is in logs/build.log, which is in the zip. Send the zip back."
        return 1
    fi
    say "The game code built."
    return 0
}

# the editor's command-line binary and its windowed binary, wherever this
# engine version keeps them
editor_cmd() {
    local c
    for c in "$UE_DIR/Engine/Binaries/Mac/UnrealEditor-Cmd" \
             "$UE_DIR/Engine/Binaries/Mac/UnrealEditor-Cmd.app/Contents/MacOS/UnrealEditor-Cmd" \
             "$UE_DIR/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"; do
        if [ -x "$c" ]; then echo "$c"; return 0; fi
    done
    return 1
}
editor_gui() {
    local c="$UE_DIR/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
    if [ -x "$c" ]; then echo "$c"; return 0; fi
    return 1
}

# --------------------------------------------------------------------------
step4() {
    say ""
    say "STEP 4 of $STEPS: Setting the game's maps and materials up inside Unreal. The first time can take 30 to 90 minutes."
    local marker="$PROJ/Saved/RenderKit/setup_done.txt"
    if [ "$FRESH" != "fresh" ] && [ -f "$marker" ]; then
        say "The setup was already done on an earlier run."
        local answer="K"
        read -r -t 20 -p "Press R then Return to redo it, or wait 20 seconds to keep it: " answer
        echo ""
        case "$answer" in
            r|R) ;;
            *) say "Keeping the earlier setup."; setup_summary "$marker"; return 0 ;;
        esac
    fi
    rm -f "$marker"

    local py_target="$PROJ/Saved/RenderKitPython"
    if [ ! -f "$py_target/numpy/__init__.py" ]; then
        local ue_py="$UE_DIR/Engine/Binaries/ThirdParty/Python3/Mac/bin/python3"
        if [ ! -x "$ue_py" ]; then
            ue_py="$(find "$UE_DIR/Engine/Binaries/ThirdParty/Python3/Mac" -maxdepth 3 -name python3 -type f -perm -u+x 2>/dev/null | head -1)"
        fi
        if [ -n "$ue_py" ]; then
            say "Getting numpy for Unreal's own Python - the monkey island needs it. This needs the internet."
            "$ue_py" -m pip install --disable-pip-version-check --no-warn-script-location --target "$py_target" numpy pillow > "$LOGS/pip.log" 2>&1
        fi
        if [ ! -f "$py_target/numpy/__init__.py" ]; then
            say "WARNING: numpy could not be installed - logs/pip.log says why. The monkey island will be skipped; everything else goes on."
        fi
    fi

    local cmd
    if ! cmd="$(editor_cmd)"; then
        FAILED="Unreal's editor program was not found inside $UE_DIR/Engine/Binaries/Mac. Reinstall 5.4 from the Epic Games Launcher (Library, the arrow next to 5.4, Verify), then double-click this file again."
        return 1
    fi
    say "Unreal is now working without a window. Nothing will seem to happen for a long time. That is normal."
    "$cmd" "$UPROJECT" -run=pythonscript -script="$KIT/setup_all.py" -unattended -nosplash -stdout -FullStdOutLogOutput > "$LOGS/setup.log" 2>&1
    echo "setup exit code: $?" >> "$KITLOG"
    if [ ! -f "$marker" ]; then
        FAILED="The setup inside Unreal stopped before its end. logs/setup.log and Saved/RenderKit/setup_report.txt say where. Send the zip back."
        return 1
    fi
    setup_summary "$marker"
    return 0
}
setup_summary() {
    local line
    while IFS= read -r line; do say "Setup: $line"; done < "$1"
    say "Setup details: $PROJ/Saved/RenderKit/setup_report.txt"
}

# --------------------------------------------------------------------------
step5() {
    say ""
    say "STEP 5 of $STEPS: Rendering the pictures. Unreal opens its window - do not close it. It closes by itself when done, at most $WATCHDOG_MINUTES minutes."
    local gui
    if ! gui="$(editor_gui)"; then
        say "WARNING: Unreal's window program was not found; the pictures cannot be made. The zip has the logs."
        return 0
    fi
    local report="$PROJ/Saved/RenderKit/render_report.txt"
    rm -f "$report"
    "$gui" "$UPROJECT" -ExecutePythonScript="$KIT/render_views.py" -unattended -nosplash -log > "$LOGS/render.log" 2>&1 &
    local pid=$!
    local start now done_at=""
    start=$(date +%s)
    while kill -0 "$pid" 2>/dev/null; do
        sleep 15
        now=$(date +%s)
        if [ -z "$done_at" ] && [ -f "$report" ]; then
            done_at=$now
            say "The pictures are done. Waiting for Unreal to close by itself."
        fi
        if [ -n "$done_at" ] && [ $((now - done_at)) -gt 180 ]; then
            say "Unreal did not close by itself, so it is being closed now."
            kill "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null
            echo "render watchdog: closed after the report" >> "$KITLOG"
            break
        fi
        if [ $((now - start)) -gt $((WATCHDOG_MINUTES * 60)) ]; then
            say "WARNING: Unreal ran for more than $WATCHDOG_MINUTES minutes, so it is being stopped. The pictures made before that are in the zip."
            kill "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null
            echo "render watchdog: timed out" >> "$KITLOG"
            break
        fi
    done
    local shots
    shots=$(ls "$PROJ/Saved/RenderKit/"*.png 2>/dev/null | wc -l | tr -d ' ')
    say "Pictures made: $shots"
    if [ -f "$report" ]; then
        say "Render details: $report"
    else
        say "WARNING: there is no render report; the logs in the zip say what happened."
    fi
    return 0
}

# --------------------------------------------------------------------------
pack() {
    say ""
    if [ -n "$FAILED" ]; then say "STOPPED: $FAILED"; fi
    say "STEP 6 of $STEPS: Packing the pictures and every log into one zip on your Desktop"
    local stamp desk stage zip
    stamp="$(TZ=Asia/Riyadh date '+%Y-%m-%d_%H-%M')"
    desk="$HOME/Desktop"
    [ -d "$desk" ] || desk="$HOME"
    stage="${TMPDIR:-/tmp}/SaudRenders_$stamp"
    zip="$desk/SaudRenders_$stamp.zip"
    rm -rf "$stage"; mkdir -p "$stage/UnrealLogs"
    if [ -n "$PROJ" ] && [ -d "$PROJ/Saved/RenderKit" ]; then cp -R "$PROJ/Saved/RenderKit" "$stage/RenderKit"; fi
    cp -R "$LOGS" "$stage/logs" 2>/dev/null
    if [ -n "$PROJ" ] && [ -d "$PROJ/Saved/Logs" ]; then cp "$PROJ/Saved/Logs/"*.log "$stage/UnrealLogs/" 2>/dev/null; fi
    rm -f "$zip"
    if ditto -c -k --sequesterRsrc "$stage" "$zip" 2>/dev/null && [ -f "$zip" ]; then
        echo "Send this file back: $zip" >> "$KITLOG"
        echo ""
        echo "Send this file back: $zip"
        open -R "$zip" 2>/dev/null
    else
        echo "The zip could not be made. Send these folders instead:"
        echo "  $PROJ/Saved/RenderKit"
        echo "  $LOGS"
        echo "  $PROJ/Saved/Logs"
    fi
}

# --------------------------------------------------------------------------
if step1 && step2 && step3 && step4; then
    step5
fi
pack
say ""
say "Finished. You can close this window."
