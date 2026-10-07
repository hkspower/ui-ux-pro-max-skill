#!/usr/bin/env bash
# Prove the harness's checks bite: every sabotage in bites.txt, each on a
# fresh copy of the sources, must make its test FAIL with the line it names.
# From the project root:
#   Tools/harness/bite.sh [pattern]
# (pattern: only the lines whose expected FAIL text contains it)
#
# bites.txt, one sabotage a line (blank lines and # comments skipped):
#   test|file|sed expression|text of the FAIL line it must cause
# - test: Tools/harness/tests/<test>.cpp
# - file: relative to the project root, and under a directory this copies
#   (Source/SaudFighter, Content/Data or Tools/harness): a file the harness
#   compiles or reads; the rest of Content and Tools is linked, read-only in
#   spirit, and the test runs from the copy's root (2026-10-07: the System's
#   lines are data, and the status screen reads SaudGameInstance)
# - the sed expression is applied to that file in the copy; a sed that
#   changes nothing is refused ("did not apply"), never counted
# - caught only if the test builds with run.sh's flags, exits 1, and prints
#   a FAIL line containing the text
# The unbroken sources must pass first, or nothing can be counted.
set -u
cd "$(dirname "$0")/../.." || exit 1
CXX=${CXX:-g++}
FLAGS=(-std=c++17 -O1 -Wall -Wextra -Werror -DSAUD_HARNESS)
ONLY=${1:-}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

fresh() {   # a clean copy of what the harness compiles, same layout
    rm -rf "$TMP/src"
    mkdir -p "$TMP/src/Source" "$TMP/src/Tools" "$TMP/src/Content"
    cp -r Source/SaudFighter "$TMP/src/Source/"
    cp -r Tools/harness "$TMP/src/Tools/"
    cp -r Content/Data "$TMP/src/Content/"
    local d
    [ -e "$TMP/saud-fighter" ] || ln -s "$(cd .. && pwd)/saud-fighter" "$TMP/saud-fighter"   # the browser game, ../
    for d in Content/* Tools/*; do
        [ -e "$TMP/src/$d" ] || ln -s "$PWD/$d" "$TMP/src/$d"
    done
}

run_test() {   # $1 test name; builds and runs it in the copy; output in $TMP/out
    if ! "$CXX" "${FLAGS[@]}" -I"$TMP/src/Tools/harness" -o "$TMP/t" "$TMP/src/Tools/harness/tests/$1.cpp" \
            > "$TMP/out" 2>&1; then
        return 2
    fi
    (cd "$TMP/src" && "$TMP/t") > "$TMP/out" 2>&1
}

t0=$(date +%s)
# the unbroken sources first
for t in $(cut -d'|' -f1 Tools/harness/bites.txt | grep -v '^\s*#' | grep -v '^\s*$' | sort -u); do
    fresh
    run_test "$t"
    rc=$?
    if [ $rc -ne 0 ]; then
        echo "the unbroken $t test does not pass (exit $rc), so no sabotage can be counted:"
        cat "$TMP/out"
        exit 1
    fi
    echo "  (unbroken $t) passes"
done

caught=0; total=0
while IFS='|' read -r test file expr want; do
    case "$test" in ''|\#*) continue ;; esac
    if [ -n "$ONLY" ] && [[ "$want" != *"$ONLY"* ]]; then continue; fi
    total=$((total + 1))
    fresh
    target="$TMP/src/$file"
    if [ ! -f "$target" ]; then
        echo "  NOT caught   [$test] no such file in the copy: $file"
        continue
    fi
    cp "$target" "$TMP/before"
    sed -i -e "$expr" "$target"
    if cmp -s "$target" "$TMP/before"; then
        echo "  did not apply [$test] $expr"
        continue
    fi
    run_test "$test"
    rc=$?
    if [ $rc -eq 2 ]; then
        echo "  NOT caught   [$test] $expr -- did not build:"
        sed 's/^/      /' "$TMP/out" | head -5
    elif [ $rc -eq 1 ] && grep -F "FAIL" "$TMP/out" | grep -qF -- "$want"; then
        caught=$((caught + 1))
        echo "  caught       [$test] $expr -> $want"
    else
        echo "  NOT caught   [$test] $expr (exit $rc; wanted: $want)"
        grep -F "FAIL" "$TMP/out" | sed 's/^/      /' | head -5
    fi
done < Tools/harness/bites.txt

echo "$caught of $total sabotages caught ($(( $(date +%s) - t0 )) s)"
[ "$caught" -eq "$total" ] && [ "$total" -gt 0 ]
