#!/usr/bin/env bash
# 啟動 ArduCopter SITL，並用 MAVProxy 轉送到 UDP 14550（QGC 預設埠）。Ctrl-C 結束。
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$root/vendor/venv/bin:$PATH"
mkdir -p "$root/vendor/sitl-run" && cd "$root/vendor/sitl-run"

python ../ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter --no-rebuild --no-mavproxy -w >sitl.log 2>&1 &
trap 'pkill -f arducopter || true; pkill -f sim_vehicle || true; kill 0' EXIT INT TERM
sleep 10
# 5760: 給 MAVProxy；5762: 留給自己的 pymavlink 程式；14550: QGC
mavproxy.py --master tcp:127.0.0.1:5760 --out udp:127.0.0.1:14550 --daemon --non-interactive
