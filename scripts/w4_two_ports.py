"""W4 實驗 3：同時連 5762 與 5763，看速率設定是各自一份還是共用，以及同一個埠能不能連兩次。

A、B 兩條連線在同一個程式裡同時讀取（效果等同兩個程式，對 SITL 來說都是兩個 TCP 連線）。
最後試著再連一次 5762（已被 A 佔用）與 5760（被 MAVProxy 佔用），看有沒有 HEARTBEAT。
先執行 scripts/sitl.sh；用法：vendor/venv/bin/python -u -I scripts/w4_two_ports.py
"""
import time

from pymavlink import mavutil

mav = mavutil.mavlink  # MAVLink 的常數與訊息編號都在這個模組裡
WINDOW = 3.0  # 每階段觀察的秒數
ATT = mav.MAVLINK_MSG_ID_ATTITUDE  # ATTITUDE 的訊息編號

# a、b：分別連 5762、5763 的兩條 MAVLink 連線
a = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
b = mavutil.mavlink_connection("tcp:127.0.0.1:5763")
for name, conn in (("A(5762)", a), ("B(5763)", b)):
    conn.wait_heartbeat(timeout=10)
    print(f"{name} 連線成功 system={conn.target_system}")


def interval(conn, hz):
    """SET_MESSAGE_INTERVAL 設定 ATTITUDE 的速率；hz = -1 表示停止。"""
    us = int(1e6 / hz) if hz > 0 else hz  # us：間隔（微秒）
    conn.mav.command_long_send(conn.target_system, conn.target_component,
                               mav.MAV_CMD_SET_MESSAGE_INTERVAL, 0, ATT, us, 0, 0, 0, 0, 0)


def measure():
    """同時讀 a、b 各 WINDOW 秒，回傳各自的 (ATTITUDE 每秒筆數, COMMAND_ACK 個數)。"""
    att, ack = {"A": 0, "B": 0}, {"A": 0, "B": 0}
    start = time.time()
    while time.time() - start < WINDOW:
        for key, conn in (("A", a), ("B", b)):
            msg = conn.recv_match(blocking=False)  # 不阻塞，輪流讀兩條連線
            while msg is not None:
                if msg.get_type() == "ATTITUDE":
                    att[key] += 1
                elif msg.get_type() == "COMMAND_ACK":
                    ack[key] += 1
                msg = conn.recv_match(blocking=False)
        time.sleep(0.002)
    return {k: v / WINDOW for k, v in att.items()}, ack


def stage(label, action):
    action()
    time.sleep(0.5)  # 讓新設定生效
    rates, acks = measure()
    print(f"{label:<34} A {rates['A']:5.1f} Hz   B {rates['B']:5.1f} Hz   ACK：A {acks['A']} 個、B {acks['B']} 個")


for conn in (a, b):  # 清掉上次實驗留下的速率
    conn.mav.request_data_stream_send(conn.target_system, conn.target_component, mav.MAV_DATA_STREAM_ALL, 0, 0)
    interval(conn, -1)
time.sleep(1)

print(f"\n{'階段':<34} ATTITUDE 實際速率")
stage("0. 都沒要求", lambda: None)
stage("1. A 要 20 Hz", lambda: interval(a, 20))
stage("2. B 再要 5 Hz", lambda: interval(b, 5))
stage("3. A 改成 2 Hz", lambda: interval(a, 2))
stage("4. B 停止", lambda: interval(b, -1))
interval(a, -1)

print("\n== 同一個埠連兩次 ==")
for port in (5762, 5760):
    extra = mavutil.mavlink_connection(f"tcp:127.0.0.1:{port}")
    hb = extra.wait_heartbeat(timeout=3)
    print(f"第二次連 {port}：{'收到 HEARTBEAT' if hb else '3 秒內沒有 HEARTBEAT'}")
    extra.close()  # 一定要關掉，否則它可能在 A 斷線後接手這個埠
