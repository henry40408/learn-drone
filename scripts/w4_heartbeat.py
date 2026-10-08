"""W4 實驗 4：HEARTBEAT 斷線偵測。

用法：vendor/venv/bin/python -u -I scripts/w4_heartbeat.py [freeze|kill]
  freeze（預設）：5 秒時暫停 arducopter 程序（SIGSTOP），13 秒時恢復（SIGCONT）。
                  TCP 連線還在，只是飛控不再送資料，只能靠 HEARTBEAT 逾時偵測。
  kill：5 秒時直接殺掉 arducopter（SIGKILL），TCP 連線被關閉。跑完要重啟 SITL。
        連線關閉後 pymavlink 會空轉狂印 "EOF on TCP socket"（10 秒約 290 萬行），用管線濾掉：
        ... scripts/w4_heartbeat.py kill | grep -v "EOF on TCP socket"
偵測方法：超過 TIMEOUT 秒沒收到「飛控」的 HEARTBEAT 就判定斷線（HEARTBEAT 每秒 1 次）。
連線上還會收到 GCS（地面站，system 255）的 HEARTBEAT，是別的程式發的、經飛控轉送過來，必須過濾掉。
先執行 scripts/sitl.sh。
"""
import os
import signal
import subprocess
import sys
import time

from pymavlink import mavutil

MODE = sys.argv[1] if len(sys.argv) > 1 else "freeze"
TIMEOUT = 3.0  # 超過幾秒沒收到 HEARTBEAT 就判定斷線（約 3 次沒收到）

# m：MAVLink 連線；m.recv_match 接收訊息
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=10)
pid = int(subprocess.check_output(["pgrep", "-x", "arducopter"]).split()[0])  # 飛控程序的 pid

if MODE == "freeze":
    events = [(5.0, signal.SIGSTOP, "暫停飛控（SIGSTOP）"), (13.0, signal.SIGCONT, "恢復飛控（SIGCONT）")]
    end = 20.0
else:
    events = [(5.0, signal.SIGKILL, "殺掉飛控（SIGKILL）")]
    end = 15.0

t0 = time.time()  # 實驗開始時刻
last_hb = t0  # 上次收到 HEARTBEAT 的時刻
last_print = t0
lost_at = None  # 判定斷線的時刻
stopped_at = None  # 飛控被暫停或殺掉的時刻
hb_count = 0
gcs_count = 0  # 被過濾掉的 GCS HEARTBEAT 個數
hb_times = []  # 每個 HEARTBEAT 的收到時刻（相對實驗開始，秒）

while time.time() - t0 < end:
    now = time.time() - t0
    if events and now >= events[0][0]:
        _, sig, label = events.pop(0)
        os.kill(pid, sig)
        if sig != signal.SIGCONT:
            stopped_at = now
        print(f"[{now:5.1f}s] {label}")
    try:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
    except Exception as e:  # 連線被關閉時 pymavlink 可能丟例外
        print(f"[{now:5.1f}s] recv_match 例外：{e!r}")
        hb = None
    if hb is not None and hb.type == mavutil.mavlink.MAV_TYPE_GCS:  # 不是飛控發的，忽略
        gcs_count += 1
        continue
    if hb is not None:
        hb_count += 1
        hb_times.append(time.time() - t0)
        if lost_at is not None:
            print(f"[{time.time() - t0:5.1f}s] 恢復：收到 HEARTBEAT（斷線 {time.time() - t0 - lost_at:.1f} 秒）")
            lost_at = None
        last_hb = time.time()
    gap = time.time() - last_hb
    if gap > TIMEOUT and lost_at is None:
        lost_at = time.time() - t0
        print(f"[{lost_at:5.1f}s] 判定斷線：{gap:.1f} 秒沒收到 HEARTBEAT"
              + (f"（暫停後 {lost_at - stopped_at:.1f} 秒）" if stopped_at is not None else ""))
    if time.time() - last_print >= 1.0:
        print(f"[{time.time() - t0:5.1f}s] 距上次 HEARTBEAT {gap:.1f} 秒" + ("  ← 斷線中" if lost_at else ""))
        last_print = time.time()

# 各階段收到幾個 HEARTBEAT：(開始, 結束, 標籤)
phases = [(0, 5, "暫停前"), (5, 13, "暫停中"), (13, 14, "恢復後 1 秒"), (14, end, "恢復後其餘")] if MODE == "freeze" \
    else [(0, 5, "殺掉前"), (5, end, "殺掉後")]
for lo, hi, label in phases:
    print(f"{label}（{lo}–{hi:.0f} 秒）：{sum(lo <= t < hi for t in hb_times)} 個 HEARTBEAT")
print(f"\n共收到 {hb_count} 個飛控 HEARTBEAT（另外過濾掉 {gcs_count} 個 GCS HEARTBEAT）")
