"""W1 實驗：有風時比較 AltHold、Loiter、Stabilize。

先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762，起飛後依序切換模式，
用 RC override 把搖桿全部放在中間（油門 1500），每秒印出高度與水平漂移。
"""
import math
import time

from pymavlink import mavutil

CONN = "tcp:127.0.0.1:5762"
TAKEOFF_ALT = 10
PHASE_SECONDS = 15
WIND_SPEED = 5  # m/s
WIND_DIR = 90  # 度，風從哪個方向吹來

MODES = {"STABILIZE": 0, "ALT_HOLD": 2, "GUIDED": 4, "LOITER": 5, "LAND": 9}

m = mavutil.mavlink_connection(CONN)
m.wait_heartbeat(timeout=10)
m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
last_rc = 0.0
sticks_centered = True


def send_rc():
    """RC override 必須持續發送（約 10 Hz），否則飛控會當作遙控器斷線。"""
    global last_rc
    if sticks_centered and time.time() - last_rc > 0.1:
        m.mav.rc_channels_override_send(m.target_system, m.target_component,
                                        1500, 1500, 1500, 1500, 0, 0, 0, 0)
        last_rc = time.time()


def set_mode(name):
    m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        MODES[name])


def set_param(name, value):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), value,
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)


def pause(seconds):
    end = time.time() + seconds
    while time.time() < end:
        send_rc()
        time.sleep(0.05)


def position():
    msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
    return (msg.x, msg.y, -msg.z) if msg else None


def observe(label, seconds):
    print(f"\n=== {label}（{seconds} 秒）===")
    origin = position()
    start = last_print = time.time()
    while time.time() - start < seconds:
        send_rc()
        pos = position()
        if pos and time.time() - last_print >= 1:
            drift = math.hypot(pos[0] - origin[0], pos[1] - origin[1])
            print(f"高度 {pos[2]:5.1f} m   水平漂移 {drift:5.1f} m")
            last_print = time.time()


try:
    print("切到 Guided、解鎖、起飛")
    set_mode("GUIDED")
    pause(1)
    # param2=21196 是強制解鎖（略過 "Throttle (RC3) is not neutral" 等檢查），QGC 的 Takeoff 也這樣做；
    # 只適合模擬，實機不要用
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 21196, 0, 0, 0, 0, 0)
    ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if ack is None or ack.result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        raise SystemExit(f"解鎖被拒絕：{ack}")
    pause(2)
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, TAKEOFF_ALT)
    deadline = time.time() + 30
    while time.time() < deadline:
        send_rc()
        pos = position()
        if pos and pos[2] > TAKEOFF_ALT - 0.5:
            break
    else:
        raise SystemExit("30 秒內沒有到達起飛高度")
    print(f"已到 {pos[2]:.1f} m；開風 {WIND_SPEED} m/s")
    set_param("SIM_WIND_SPD", WIND_SPEED)
    set_param("SIM_WIND_DIR", WIND_DIR)
    pause(3)

    set_mode("ALT_HOLD")
    observe("AltHold：高度不變，位置被風吹走", PHASE_SECONDS)
    set_mode("LOITER")
    observe("Loiter：高度不變，位置也頂住風", PHASE_SECONDS)
    set_mode("STABILIZE")
    observe("Stabilize：高度與位置都不管", 10)
finally:
    print("\n降落並關風")
    sticks_centered = False
    m.mav.rc_channels_override_send(m.target_system, m.target_component, 0, 0, 0, 0, 0, 0, 0, 0)
    set_mode("LAND")
    set_param("SIM_WIND_SPD", 0)
