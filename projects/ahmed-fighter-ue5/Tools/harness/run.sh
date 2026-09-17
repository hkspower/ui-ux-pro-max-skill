#!/usr/bin/env bash
# Build and run every check that does not need an engine. From the project root:
#   Tools/harness/run.sh
# Needs g++ (or clang++). Nothing else: the files under test include a small
# stub of FVector and FMath instead of CoreMinimal.h when AHMED_HARNESS is set.
set -u
cd "$(dirname "$0")/../.." || exit 1
CXX=${CXX:-g++}
OUT=$(mktemp -d); trap 'rm -rf "$OUT"' EXIT
fail=0

for t in Tools/harness/tests/*.cpp; do
  name=$(basename "$t" .cpp)
  echo "== $name =="
  if ! "$CXX" -std=c++17 -O1 -Wall -Wextra -Werror -DAHMED_HARNESS \
        -ITools/harness -o "$OUT/$name" "$t"; then
    echo "  did not build"; fail=1; continue
  fi
  "$OUT/$name" || fail=1
  echo
done

echo "== the layout the map is built from =="
python3 Tools/fab/lay_out_world.py > "$OUT/plan.txt" 2>&1 \
  && echo "  $(head -1 "$OUT/plan.txt")" \
  || { echo "  the layout plan failed its own checks"; cat "$OUT/plan.txt"; fail=1; }

echo
[ $fail -eq 0 ] && echo "everything that can run here passed" || echo "SOMETHING FAILED"
exit $fail
