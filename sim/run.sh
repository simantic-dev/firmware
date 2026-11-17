#!/bin/sh
# usage: sim/run.sh [scenario.yaml] [virtual seconds]      (default: scenario.yaml, 10 s)
# Runs one scenario with `sim` on PATH (or SIM=...) against the images from sim/build.sh.
# Output in sim/out/<scenario>/: uart.log (every board's console, prefixed [board]),
# can-frames.txt (every CAN frame each node sent or received), sim.log (warnings, timing).
# For scenario.yaml the script also asserts on what the firmware itself printed and exits 1
# if any line is missing.
set -e
cd "$(dirname "$0")"
SIM=${SIM:-sim}
SC=${1:-scenario.yaml}
SECS=${2:-10}
NAME=$(basename "$SC" .yaml)
OUT=out/$NAME
[ -f ../build/Debug/BMS/BMS.elf ] || { echo "build first: sim/build.sh"; exit 1; }
mkdir -p "$OUT"
# The DCU's SD card: an empty 32 MB FAT16 volume (mtools), rebuilt on every run.
if grep -q dcu "$SC"; then
  truncate -s 32M out/dcu-sd.img
  mformat -i out/dcu-sd.img -T 65536 -h 16 -s 63 -c 2 -v DCU ::
fi
"$SIM" run --scenario "$SC" --timeout "$SECS" --ascii --frames-only can --frames "$OUT/can-frames.txt" \
  > "$OUT/uart.raw" 2> "$OUT/sim.log"
# strip the log colours (the sim prints ESC as '.') and the stream arrows so the asserts match plain text
sed 's/\.\[[0-9;]*m//g; s/\x1b\[[0-9;]*m//g; s/ → [a-z0-9]*)/)/; s/ ← [a-z0-9]*)/)/' "$OUT/uart.raw" > "$OUT/uart.log"
rm -f "$OUT/uart.raw"
echo "$NAME: $SECS virtual seconds; $(grep -c 'CAN Tx' "$OUT/can-frames.txt") CAN frames sent; logs in sim/$OUT/"
[ "$NAME" = scenario ] || exit 0
fail=0
need() { # need <file> <egrep pattern> <what>
  if grep -a -q -E "$2" "$OUT/$1"; then echo "ok   $3"; else echo "FAIL $3"; fail=1; fi
}
need uart.log '^\[bms\].*BOOT -> LV_POWER' "BMS boots to LV_POWER"
need uart.log '^\[bms\].*LV_POWER -> BUS_HEALTH_CHECK' "BMS takes the console-requested step to BUS_HEALTH_CHECK"
need uart.log '^\[bms\].*Shutdown open during health check, returning to LV_POWER' "BMS backs out: shutdown loop open"
need uart.log '^\[bms\].*FAULT ENTRY: FAULT_BMS' "BMS faults in PRECHARGE (no current sensor)"
need uart.log '^\[bms\].*Pack Voltage: [0-9.]+V' "BMS console reports pack voltage from the ADBMS chain"
need uart.log '^\[pcu\].*PCU Setup Complete ===' "PCU finishes its 8-step setup"
need uart.log '^\[lvpdb\].*TPS init: 7/7 chips OK' "LVPDB finds all seven TPS2482"
need uart.log '^\[front\].*Gyro auto-cal done' "FRONT sensor node calibrates its gyro"
need uart.log '^\[rear\].*Gyro auto-cal done' "REAR sensor node calibrates its gyro"
need uart.log '^\[dcu\].*Logging to 0:log_0001.csv' "DCU opens its SD log"
need can-frames.txt '^\[bms\] .*CAN Tx id=0x5 ' "BMS sends bms_state (0x5)"
need can-frames.txt '^\[pcu\] .*CAN Rx id=0x5 ' "PCU receives bms_state from the real BMS"
need can-frames.txt '^\[dcu\] .*CAN Rx id=0x5 ' "DCU receives bms_state from the real BMS"
need can-frames.txt '^\[front\] .*CAN Tx id=0x26 ' "FRONT sends its IMU acceleration frame (0x26)"
need can-frames.txt '^\[rear\] .*CAN Tx id=0x27 ' "REAR sends its IMU acceleration frame (0x27)"
need can-frames.txt '^\[pcu\] .*CAN Tx id=0xC0 ' "PCU sends torque commands (0xC0)"
need can-frames.txt '^\[bms\] .*CAN Rx id=0x10 ' "the DASH stand-in's dash_state (0x10) reaches the bus"
rows=$(mtype -i out/dcu-sd.img ::LOG_0001.CSV 2>/dev/null | wc -l)
if [ "$rows" -gt 100 ]; then echo "ok   DCU wrote $rows CAN rows to log_0001.csv on the SD image"; else echo "FAIL DCU SD log has $rows rows"; fail=1; fi
exit $fail
