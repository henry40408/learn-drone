"""W5 實驗 2：Guided 模式速度控制（pymavlink）：用速度指令飛正方形。

用法：vendor/venv/bin/python -u -I scripts/w5_velocity_square.py [square|timeout]
  square（預設）：起飛後依序往北、東、南、西各飛一邊，回到起點上空後降落。
  timeout：只往東飛 SIDE_SECONDS 秒，然後「停止發送」速度指令 SILENT_SECONDS 秒，
           觀察飛機什麼時候停下來（ArduCopter 的 GUID_TIMEOUT，預設 3 秒）。
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762。
速度指令（SET_POSITION_TARGET_LOCAL_NED 的 vx, vy, vz）必須持續發送，約 10 Hz。
"""
import math
import sys
import time

from pymavlink import mavutil

MODE = sys.argv[1] if len(sys.argv) > 1 else "square"
CONN = "tcp:127.0.0.1:5762"
TAKEOFF_ALT = 10  # 起飛高度，公尺（相對起飛點）
SPEED = 2.0  # 飛行速度，m/s
SIDE_SECONDS = 10  # 每邊飛幾秒（邊長約 SPEED * SIDE_SECONDS = 20 m）
SILENT_SECONDS = 8  # timeout 模式：停止發送後觀察幾秒
SEND_HZ = 10  # 速度指令發送頻率，Hz
GUIDED = 4  # ArduCopter 的 GUIDED 模式編號
LAND = 9  # ArduCopter 的 LAND 模式編號
TIMEOUT = 60  # 起飛與降落最多等幾秒

T = mavutil.mavlink  # T：MAVLink 常數的命名空間，只為了縮短下面的名稱
# type_mask 只啟用速度（vx, vy, vz），忽略位置、加速度、yaw、yaw 速率
VEL_ONLY = (T.POSITION_TARGET_TYPEMASK_X_IGNORE | T.POSITION_TARGET_TYPEMASK_Y_IGNORE
            | T.POSITION_TARGET_TYPEMASK_Z_IGNORE | T.POSITION_TARGET_TYPEMASK_AX_IGNORE
            | T.POSITION_TARGET_TYPEMASK_AY_IGNORE | T.POSITION_TARGET_TYPEMASK_AZ_IGNORE
            | T.POSITION_TARGET_TYPEMASK_YAW_IGNORE | T.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE)

# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection(CONN)
m.wait_heartbeat(timeout=10)
m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
t0 = time.time()  # 腳本開始時刻


def log(msg):
    print(f"[{time.time() - t0:5.1f}s] {msg}")


def command(cmd, *params):
    """送 COMMAND_LONG 並等 COMMAND_ACK；回傳 result（0 = ACCEPTED）。"""
    p = list(params) + [0] * (7 - len(params))
    m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *p)
    ack = m.recv_match(type="COMMAND_ACK", condition=f"COMMAND_ACK.command=={cmd}",
                       blocking=True, timeout=5)
    return None if ack is None else ack.result


def set_mode(mode):
    m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode)


def send_velocity(vx, vy, vz):
    """local NED 速度，m/s：vx 北、vy 東、vz 下（往上要給負數）。"""
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        VEL_ONLY, 0, 0, 0, vx, vy, vz, 0, 0, 0, 0, 0)


def fly(label, vx, vy, seconds, send=True):
    """以固定頻率發送速度 seconds 秒（send=False 則只觀察、不發送），每秒印位置與地速。"""
    log(label)
    end = time.time() + seconds
    next_send = time.time()
    next_print = time.time()
    while time.time() < end:
        if send and time.time() >= next_send:
            send_velocity(vx, vy, 0)
            next_send += 1 / SEND_HZ
        pos = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=0.05)
        if pos is not None and time.time() >= next_print:
            speed = math.hypot(pos.vx, pos.vy)  # 水平地速，m/s
            log(f"  位置 北 {pos.x:6.1f} 東 {pos.y:6.1f} 高 {-pos.z:5.1f} m，地速 {speed:.2f} m/s")
            next_print += 1.0


def wait_alt(check, label):
    end = time.time() + TIMEOUT
    while time.time() < end:
        g = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if g is not None and check(g.relative_alt / 1000):  # relative_alt 單位 mm → m
            log(f"{label}：完成")
            return
    raise SystemExit(f"逾時：{label}")


# 1. 切 GUIDED、arm（EKF 還沒準備好會被拒絕，所以重試）
set_mode(GUIDED)
m.recv_match(type="HEARTBEAT", condition=f"HEARTBEAT.custom_mode=={GUIDED}", blocking=True, timeout=5)
log("模式：GUIDED")
for _ in range(30):
    result = command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    if result == 0:
        break
    log(f"arm 被拒絕（result={result}），1 秒後重試")
    time.sleep(1)
else:
    raise SystemExit("arm 失敗")
log("已 arm")

# 2. 起飛
command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, TAKEOFF_ALT)
wait_alt(lambda alt: alt >= TAKEOFF_ALT * 0.95, "takeoff")

# 3. 速度控制
if MODE == "square":
    for name, vx, vy in [("往北", SPEED, 0), ("往東", 0, SPEED), ("往南", -SPEED, 0), ("往西", 0, -SPEED)]:
        fly(f"{name} {SPEED} m/s {SIDE_SECONDS} 秒", vx, vy, SIDE_SECONDS)
    fly("煞車：速度 0 持續發送 3 秒", 0, 0, 3)
else:
    fly(f"往東 {SPEED} m/s {SIDE_SECONDS} 秒", 0, SPEED, SIDE_SECONDS)
    fly(f"停止發送 {SILENT_SECONDS} 秒，觀察何時停下來", 0, 0, SILENT_SECONDS, send=False)

# 4. 降落
set_mode(LAND)
log("模式：LAND")
wait_alt(lambda alt: alt < 0.2, "降落")
