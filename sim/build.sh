#!/bin/sh
# Builds all eleven unmodified firmware images with the repo's own preset (arm-none-eabi-gcc on PATH).
# Output: build/Debug/<BOARD>/<BOARD>.elf at the repo root (git-ignored).
set -e
cd "$(dirname "$0")/.."
git submodule update --init --recursive
cmake --preset Debug
cmake --build build/Debug
