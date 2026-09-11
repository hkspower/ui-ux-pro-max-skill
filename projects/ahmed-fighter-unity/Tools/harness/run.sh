#!/usr/bin/env bash
# Build and run every check against the harness. From the project root:
#   Tools/harness/run.sh
# Needs mono and mcs (apt install mono-mcs mono-runtime). numpy for the
# algebra cross-check; it is skipped if python3 or numpy is missing.
set -u
cd "$(dirname "$0")/../.." || exit 1
H=Tools/harness
OUT=$(mktemp -d); trap 'rm -rf "$OUT"' EXIT
fail=0

echo "== compiling the port (warnings as errors) =="
mcs -target:library -out:"$OUT/port.dll" -warnaserror -warn:4 -nowarn:649 \
    "$H/UnityEngine.cs" Assets/Scripts/*/*.cs || fail=1

for t in World IK Hub Pose Algebra Strata Place Feel; do
  echo
  echo "== $t =="
  if ! mcs -out:"$OUT/$t.exe" -target:exe -nowarn:649 \
        "$H/UnityEngine.cs" "$H/tests/TestData.cs" "$H/tests/$t.cs" Assets/Scripts/*/*.cs 2>&1 | grep -v '^$'; then :; fi
  [ -f "$OUT/$t.exe" ] || { echo "  did not build"; fail=1; continue; }
  mono "$OUT/$t.exe" || fail=1
done

echo
echo "== algebra vs numpy =="
if python3 -c "import numpy" 2>/dev/null; then
  mcs -out:"$OUT/dump.exe" -target:exe -nowarn:649 \
      "$H/UnityEngine.cs" "$H/xcheck/Dump.cs" Assets/Scripts/Combat/TwoBoneIK.cs \
    && mono "$OUT/dump.exe" > "$OUT/dump.txt" \
    && python3 "$H/xcheck/verify.py" "$OUT/dump.txt" || fail=1
else
  echo "  skipped: no numpy"
fi

echo
[ $fail -eq 0 ] && echo "everything passed" || echo "SOMETHING FAILED"
exit $fail
