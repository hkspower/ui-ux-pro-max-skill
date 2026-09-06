#!/usr/bin/env bash
# AHMED — Kuwait Fighter :: build and package for iOS, from a Mac
# =============================================================================
# Wraps the one RunUAT invocation that matters so nobody has to remember the
# flag order. Everything it does can be done from the editor's Platforms menu
# instead; this exists for the times you want it in a terminal or in CI.
#
#   ./Tools/ios/build-ios.sh                 Development, to Build/IOS
#   ./Tools/ios/build-ios.sh shipping        Shipping build
#   ./Tools/ios/build-ios.sh shipping dist   Shipping, signed for the store
#
# Needs, in this order, or it will fail with a message that does not say why:
#
#   1. macOS. iOS cannot be built from anything else -- Apple's toolchain is
#      Mac-only and Unreal shells out to it. There is no cross-compile.
#   2. Xcode, and `xcode-select -p` pointing at it. Not the command line tools
#      on their own: packaging needs the full Xcode.
#   3. Unreal Engine 5.4 installed, and UE_ROOT below pointing at it.
#   4. An Apple developer account, an App ID matching BundleIdentifier in
#      Config/IOS/IOSEngine.ini, and a signing certificate plus provisioning
#      profile for it installed in the login keychain.
# =============================================================================
set -euo pipefail

CONFIG="${1:-development}"
DIST="${2:-}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$HERE/../.." && pwd)"
PROJECT="$PROJECT_DIR/AhmedFighter.uproject"

# Where Unreal lives. The Epic Games Launcher installs here by default; a
# source build will be wherever you cloned it.
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.4}"
UAT="$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh"

say() { printf '\n\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31merror:\033[0m %s\n\n' "$*" >&2; exit 1; }

# ---- the checks worth doing before a twenty-minute cook ----------------------
[[ "$(uname -s)" == "Darwin" ]] || die \
  "iOS builds only run on macOS. Apple's toolchain is Mac-only and there is no
  cross-compile; a Linux or Windows machine cannot produce an .ipa."

command -v xcodebuild >/dev/null 2>&1 || die \
  "xcodebuild not found. Install Xcode from the App Store, open it once to
  accept the licence, then: sudo xcode-select -s /Applications/Xcode.app"

[[ -f "$UAT" ]] || die \
  "Unreal not found at:
    $UE_ROOT
  Set UE_ROOT to your install, e.g.
    UE_ROOT='/Users/Shared/Epic Games/UE_5.4' $0 $*"

[[ -f "$PROJECT" ]] || die "AhmedFighter.uproject not found at $PROJECT"

case "$CONFIG" in
  development|Development) UE_CONFIG=Development ;;
  shipping|Shipping)       UE_CONFIG=Shipping ;;
  debug|Debug)             UE_CONFIG=DebugGame ;;
  *) die "unknown configuration '$CONFIG' (development | shipping | debug)" ;;
esac

# ---- keep the tables honest --------------------------------------------------
# Cooking a build whose numbers disagree with the browser project is the one
# mistake this whole pipeline exists to prevent, so it is checked here rather
# than discovered later.
if command -v node >/dev/null 2>&1; then
  say "Checking Content/Data against the browser assets"
  if ! node "$PROJECT_DIR/Tools/export/export.mjs" --check; then
    die "The data tables are stale. Run:
    node Tools/export/export.mjs --api
  then build again."
  fi
else
  printf '\n\033[1;33mnote:\033[0m node not found; skipping the data check.\n'
fi

ARGS=(
  BuildCookRun
  -project="$PROJECT"
  -platform=IOS
  -clientconfig="$UE_CONFIG"
  -targetplatform=IOS
  -build -cook -stage -package -pak -iostore -compressed
  -utf8output
  -archive -archivedirectory="$PROJECT_DIR/Build/IOS"
  -nop4 -nocompileeditor
)

if [[ "$DIST" == "dist" || "$DIST" == "distribution" ]]; then
  # Signed for TestFlight or the App Store. Uses the distribution certificate
  # and provisioning profile rather than the development one.
  ARGS+=( -distribution )
  say "Building $UE_CONFIG for iOS — DISTRIBUTION (store signing)"
else
  say "Building $UE_CONFIG for iOS — development signing"
fi

say "Engine: $UE_ROOT"
"$UAT" "${ARGS[@]}"

say "Done. The .ipa is under:"
echo "  $PROJECT_DIR/Build/IOS"
echo
echo "To put it on a device:"
echo "  ios-deploy --bundle Build/IOS/AhmedFighter.ipa      (brew install ios-deploy)"
echo "or drag the .ipa into Xcode's Devices and Simulators window."
