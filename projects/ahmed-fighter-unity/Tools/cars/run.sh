#!/usr/bin/env bash
# The street-car tool outside Unity (Assets/CarTool/Editor/Core + Tools/cars/CarRun.cs),
# from the project root:  Tools/cars/run.sh [--out DIR] [--bite]
# Needs mono and mcs, like Tools/harness/run.sh. Reads ../saud-fighter-ue5/Content/Models/Cars/cars.json.
set -eu
cd "$(dirname "$0")/../.."
OUT=$(mktemp -d); trap 'rm -rf "$OUT"' EXIT
mcs -out:"$OUT/cars.exe" -target:exe -warnaserror -warn:4 \
    Assets/CarTool/Editor/Core/*.cs Tools/cars/CarRun.cs
mono "$OUT/cars.exe" "$@"
