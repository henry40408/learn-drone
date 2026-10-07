#!/usr/bin/env bash
# 啟動 ArduCopter SITL，並用 MAVProxy 轉送到 UDP 14550（QGC 預設埠）。Ctrl-C 結束。
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$root/vendor/venv/bin:$PATH"
mkdir -p "$root/vendor/sitl-run" && cd "$root/vendor/sitl-run"

cleanup() {
  trap - EXIT INT TERM
  pkill -f "[m]avproxy.py" || true
  pkill -f "[a]rducopter" || true
  pkill -f "[s]im_vehicle" || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

python ../ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter --no-rebuild --no-mavproxy -w >sitl.log 2>&1 &
sleep 10
# 5760: 給 MAVProxy；5762: 留給自己的 pymavlink 程式；14550: QGC
# 放背景再 wait，Ctrl-C 才會立刻觸發 trap（前景子程序會延後 trap）
mavproxy.py --master tcp:127.0.0.1:5760 --out udp:127.0.0.1:14550 --daemon --non-interactive &
wait $!
