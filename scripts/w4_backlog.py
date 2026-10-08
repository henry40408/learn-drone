"""W4 實驗：沒被讀取的資料會被丟掉，還是下次讀取時一次收到？

A. 有要求但暫停讀取：要 ATTITUDE 20 Hz，停止讀取 PAUSE 秒，再讀取，看收到的是不是一批舊資料。
B. 沒要求：停止要求 ATTITUDE，等 PAUSE 秒，再要求，看是不是一下子湧進一批。
先執行 scripts/sitl.sh；用法：vendor/venv/bin/python -u -I scripts/w4_backlog.py
"""
import time

from pymavlink import mavutil

mav = mavutil.mavlink  # MAVLink 的常數與訊息編號都在這個模組裡
PAUSE = 5.0  # 暫停（秒）
HZ = 20

# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=10)


def interval(hz):
    """SET_MESSAGE_INTERVAL 設定 ATTITUDE 的速率；hz = -1 表示停止。"""
    mid = getattr(mav, "MAVLINK_MSG_ID_ATTITUDE")  # mid：message id，訊息編號
    us = int(1e6 / hz) if hz > 0 else hz  # us：間隔（微秒）
    m.mav.command_long_send(m.target_system, m.target_component, mav.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mid, us, 0, 0, 0, 0, 0)


def read_for(seconds):
    """讀 seconds 秒，回傳 [(收到時刻（相對本次開始，秒）, 飛控開機後的毫秒數)]。"""
    out, start = [], time.time()
    while time.time() - start < seconds:
        msg = m.recv_match(type="ATTITUDE", blocking=True, timeout=0.5)
        if msg is not None:
            out.append((time.time() - start, msg.time_boot_ms))
    return out


def summary(label, msgs, before_ms=None):
    first_burst = sum(1 for t, _ in msgs if t < 0.5)  # 恢復讀取後 0.5 秒內收到幾筆
    line = f"{label}：共 {len(msgs)} 筆；前 0.5 秒收到 {first_burst} 筆"
    if before_ms is not None and msgs:
        line += f"；第一筆比暫停前最後一筆晚 {(msgs[0][1] - before_ms) / 1000:.2f} 秒（飛控時間）"
    print(line)


m.mav.request_data_stream_send(m.target_system, m.target_component, mav.MAV_DATA_STREAM_ALL, 0, 0)
interval(-1)
time.sleep(1)

print("== A. 有要求，但暫停讀取 ==")
interval(HZ)
warm = read_for(1.0)
summary("暫停前 1 秒", warm)
last_ms = warm[-1][1]
print(f"暫停 {PAUSE:.0f} 秒（不讀取）…")
time.sleep(PAUSE)
after = read_for(2.0)
summary("恢復讀取後 2 秒", after, last_ms)
print(f"  預期：若是即時資料，前 0.5 秒約 {HZ // 2} 筆；若有堆積，會多出約 {int(PAUSE * HZ)} 筆")

print("\n== B. 沒要求（速率 -1），暫停後再要求 ==")
interval(-1)
time.sleep(0.5)
while m.recv_match(blocking=False):  # 丟掉緩衝區裡剩下的
    pass
print(f"不要求 {PAUSE:.0f} 秒（不讀取）…")
time.sleep(PAUSE)
leftover = 0
while m.recv_match(type="ATTITUDE", blocking=False):  # 這段期間有沒有東西在排隊
    leftover += 1
print(f"緩衝區裡的 ATTITUDE：{leftover} 筆")
interval(HZ)
resumed = read_for(2.0)
summary("重新要求後 2 秒", resumed)
interval(-1)
