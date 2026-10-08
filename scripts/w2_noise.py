"""W2 實驗：開啟模擬的 IMU 震動雜訊，比較原始值與 EKF 估算。

SIM_ACC1_RND / SIM_GYR1_RND 只在馬達轉動時生效（陀螺儀還會乘上油門），
加速度計的雜訊還要 SIM_VIB_FREQ 非 0 才會加進去，所以必須在空中懸停。
先執行 scripts/sitl.sh；用法：vendor/venv/bin/python -u -I scripts/w2_noise.py [--hold]
"""
import math
import statistics
import sys
import time

from pymavlink import mavutil

HOLD = "--hold" in sys.argv  # 懸停並保持雜訊，Ctrl-C 結束（給 QGC 觀察用）
# ACC_RND、GYR_RND：模擬加速度計、陀螺儀的隨機雜訊（rnd = random）強度；VIB_FREQ：x、y、z 軸的振動頻率
ACC_RND, GYR_RND = (10.0, 10.0) if HOLD else (3.0, 5.0)
VIB_FREQ = (50.0, 60.0, 70.0)  # Hz；加速度計雜訊要有振動頻率才會加進去
N = 100  # 每階段取樣筆數

# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=10)


def set_param(name, value):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), value,
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)


def command(cmd, *params, timeout=10):  # cmd：MAV_CMD 指令編號；params：最多 7 個指令參數，不足補 0
    m.mav.command_long_send(m.target_system, m.target_component, cmd, 0,
                            *(list(params) + [0] * (7 - len(params))))
    ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout)
    if ack is None or ack.result != 0:
        sys.exit(f"指令 {cmd} 失敗：{ack}")


def interval(name, hz):
    mid = getattr(mavutil.mavlink, f"MAVLINK_MSG_ID_{name}")  # mid：message id，訊息編號
    command(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, mid, int(1e6 / hz))


def sample():
    imu, att = [], []  # imu：RAW_IMU 原始值；att：EKF 估算的 ATTITUDE
    deadline = time.time() + 30
    while time.time() < deadline and (len(imu) < N or len(att) < N):
        msg = m.recv_match(type=["RAW_IMU", "ATTITUDE"], blocking=True, timeout=1)
        if msg is None:
            continue
        (imu if msg.get_type() == "RAW_IMU" else att).append(msg)
    if len(imu) < N or len(att) < N:
        sys.exit("取樣逾時")
    return imu[:N], att[:N]


def report(label, imu, att):
    sd = statistics.stdev  # sd：standard deviation，標準差，用來表示雜訊大小
    # roll_acc：只用加速度計算的 roll；roll_ekf：EKF 估算的 roll（度）
    roll_acc = [math.degrees(math.atan2(r.yacc, -r.zacc)) for r in imu]
    roll_ekf = [math.degrees(r.roll) for r in att]
    print(f"\n== {label} ==")
    print(f"  陀螺儀 x 標準差   {sd([r.xgyro / 1000 for r in imu]):.4f} rad/s")
    print(f"  加速度計 z 標準差 {sd([r.zacc / 1000 * 9.80665 for r in imu]):.4f} m/s²")
    print(f"  roll 只用加速度計  標準差 {sd(roll_acc):.3f}°（範圍 {min(roll_acc):.2f}~{max(roll_acc):.2f}）")
    print(f"  roll EKF 估算      標準差 {sd(roll_ekf):.3f}°（範圍 {min(roll_ekf):.2f}~{max(roll_ekf):.2f}）")


try:
    command(mavutil.mavlink.MAV_CMD_DO_SET_MODE, 1, 4)  # Guided
    command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1, 21196)  # 模擬用強制解鎖
    command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10)
    for name in ("RAW_IMU", "ATTITUDE"):
        interval(name, 20)
    print("起飛中…")
    while True:
        pos = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
        if pos and -pos.z > 9.5:
            break
    time.sleep(3)

    if not HOLD:
        imu, att = sample()
        report("無雜訊（懸停 10 m）", imu, att)

    set_param("SIM_ACC1_RND", ACC_RND)
    set_param("SIM_GYR1_RND", GYR_RND)
    for axis, hz in zip("XYZ", VIB_FREQ):
        set_param(f"SIM_VIB_FREQ_{axis}", hz)
    time.sleep(2)
    if HOLD:
        print("雜訊已開啟，懸停中；在 QGC 的 MAVLink Inspector 觀察，Ctrl-C 結束")
        while True:
            m.recv_match(blocking=True, timeout=1)  # 要持續讀，否則 TCP 緩衝區塞滿會卡住 SITL
    imu, att = sample()
    report(f"有雜訊（SIM_ACC1_RND={ACC_RND}, SIM_GYR1_RND={GYR_RND}）", imu, att)
finally:
    set_param("SIM_ACC1_RND", 0)
    set_param("SIM_GYR1_RND", 0)
    for axis in "XYZ":
        set_param(f"SIM_VIB_FREQ_{axis}", 0)
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0, 1, 9, 0, 0, 0, 0, 0)  # Land
    print("\n已關閉雜訊並切 Land")
