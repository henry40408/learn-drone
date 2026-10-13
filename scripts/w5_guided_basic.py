"""W5 實驗 1：Guided 模式基本流程（pymavlink）：切 GUIDED、arm、takeoff、goto、降落。

用法：vendor/venv/bin/python -u -I scripts/w5_guided_basic.py
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762，每個階段都等條件成立（不是睡固定秒數）。
"""
import math
import time

from pymavlink import mavutil

CONN = "tcp:127.0.0.1:5762"
TAKEOFF_ALT = 10  # 起飛高度，公尺（相對起飛點）
GOTO_NORTH = 20  # goto 目標：往北幾公尺（相對起飛點）
GOTO_EAST = 20  # goto 目標：往東幾公尺（相對起飛點）
GUIDED = 4  # ArduCopter 的 GUIDED 模式編號
TIMEOUT = 60  # 每個階段最多等幾秒

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


def wait_for(label, check):
    """每次收到 GLOBAL_POSITION_INT 就呼叫 check(msg)；成立就回傳，逾時就結束腳本。"""
    end = time.time() + TIMEOUT
    while time.time() < end:
        msg = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if msg is not None and check(msg):
            log(f"{label}：完成")
            return msg
    raise SystemExit(f"逾時：{label}")


def rel_alt(msg):
    return msg.relative_alt / 1000  # relative_alt 單位 mm → m


# 1. 切 GUIDED
m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, GUIDED)
m.recv_match(type="HEARTBEAT", condition=f"HEARTBEAT.custom_mode=={GUIDED}", blocking=True, timeout=5)
log("模式：GUIDED")

# 2. arm（SITL 剛啟動時 EKF 還沒準備好會被拒絕，所以重試）
for _ in range(30):
    result = command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    if result == 0:
        break
    log(f"arm 被拒絕（result={result}），1 秒後重試")
    time.sleep(1)
else:
    raise SystemExit("arm 失敗")
log("已 arm")

# 3. takeoff：高度達到目標的 95% 就算完成
log(f"takeoff 結果：{command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, TAKEOFF_ALT)}")
wait_for("takeoff", lambda g: rel_alt(g) >= TAKEOFF_ALT * 0.95)

# 4. goto：SET_POSITION_TARGET_LOCAL_NED（local NED：x 北、y 東、z 下；負 z 表示上方）
# type_mask 只啟用位置（x, y, z），忽略速度、加速度、yaw、yaw 速率
T = mavutil.mavlink  # T：MAVLink 常數的命名空間，只為了縮短下面的名稱
POS_ONLY = (T.POSITION_TARGET_TYPEMASK_VX_IGNORE | T.POSITION_TARGET_TYPEMASK_VY_IGNORE
            | T.POSITION_TARGET_TYPEMASK_VZ_IGNORE | T.POSITION_TARGET_TYPEMASK_AX_IGNORE
            | T.POSITION_TARGET_TYPEMASK_AY_IGNORE | T.POSITION_TARGET_TYPEMASK_AZ_IGNORE
            | T.POSITION_TARGET_TYPEMASK_YAW_IGNORE | T.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE)
m.mav.set_position_target_local_ned_send(
    0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
    POS_ONLY, GOTO_NORTH, GOTO_EAST, -TAKEOFF_ALT, 0, 0, 0, 0, 0, 0, 0, 0)
log(f"goto：北 {GOTO_NORTH} m、東 {GOTO_EAST} m")


def reached(_):
    pos = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=1)
    if pos is None:
        return False
    dist = math.hypot(pos.x - GOTO_NORTH, pos.y - GOTO_EAST)  # 到目標的水平距離，公尺
    log(f"距目標 {dist:.1f} m")
    return dist < 1.0


wait_for("goto", reached)

# 5. 降落：LAND 模式（編號 9），落地後飛控自動 disarm
m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 9)
log("模式：LAND")
wait_for("降落", lambda g: rel_alt(g) < 0.2)
