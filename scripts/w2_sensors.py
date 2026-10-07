"""W2 實作：讀 SITL 靜止時的原始感測器值，與 EKF 估算的姿態比較。

先執行 scripts/sitl.sh，等出現 EKF3 IMU0 is using GPS。
用法：vendor/venv/bin/python -u -I scripts/w2_sensors.py
"""
import math
import statistics
import sys
import time

from pymavlink import mavutil

N = 50  # 取樣筆數
TYPES = ["RAW_IMU", "SCALED_PRESSURE", "GPS_RAW_INT", "ATTITUDE"]

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=30)

# 要求每個訊息 10 Hz（單位：微秒）
for name in TYPES:
    mid = getattr(mavutil.mavlink, f"MAVLINK_MSG_ID_{name}")
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mid, 100_000, 0, 0, 0, 0, 0)

data = {t: [] for t in TYPES}
deadline = time.time() + 30
while time.time() < deadline and min(len(v) for v in data.values()) < N:
    msg = m.recv_match(type=TYPES, blocking=True, timeout=1)
    if msg and len(data[msg.get_type()]) < N:
        data[msg.get_type()].append(msg)

if min(len(v) for v in data.values()) < N:
    sys.exit(f"逾時，收到筆數：{ {k: len(v) for k, v in data.items()} }")


def stat(xs):
    return statistics.mean(xs), statistics.stdev(xs)


def show(label, xs, unit):
    mean, sd = stat(xs)
    print(f"  {label:<10} 平均 {mean:10.3f}  雜訊（標準差）{sd:8.4f}  {unit}")


imu = data["RAW_IMU"]
print(f"== RAW_IMU（{N} 筆）==")
show("gyro x", [r.xgyro / 1000 for r in imu], "rad/s")
show("gyro y", [r.ygyro / 1000 for r in imu], "rad/s")
show("gyro z", [r.zgyro / 1000 for r in imu], "rad/s")
show("accel x", [r.xacc / 1000 * 9.80665 for r in imu], "m/s²")
show("accel y", [r.yacc / 1000 * 9.80665 for r in imu], "m/s²")
show("accel z", [r.zacc / 1000 * 9.80665 for r in imu], "m/s²（靜止時約 -9.8，即重力）")

print("== SCALED_PRESSURE ==")
show("氣壓", [r.press_abs for r in data["SCALED_PRESSURE"]], "hPa")
show("溫度", [r.temperature / 100 for r in data["SCALED_PRESSURE"]], "°C")

gps = data["GPS_RAW_INT"][-1]
print("== GPS_RAW_INT ==")
print(f"  fix_type {gps.fix_type}（3 = 3D 定位，6 = RTK 固定解；SITL 模擬的 GPS 回報 6），衛星數 {gps.satellites_visible}")
print(f"  緯度 {gps.lat / 1e7:.6f}，經度 {gps.lon / 1e7:.6f}，高度 {gps.alt / 1000:.1f} m")

att = data["ATTITUDE"]
print("== ATTITUDE（EKF 估算）==")
show("roll", [math.degrees(r.roll) for r in att], "°")
show("pitch", [math.degrees(r.pitch) for r in att], "°")
show("yaw", [math.degrees(r.yaw) for r in att], "°")

# 只用加速度計算傾角，對照 EKF 的估算
ax = [r.xacc for r in imu]
ay = [r.yacc for r in imu]
az = [r.zacc for r in imu]
roll_acc = math.degrees(math.atan2(statistics.mean(ay), -statistics.mean(az)))
pitch_acc = math.degrees(math.atan2(statistics.mean(ax),
                                     math.hypot(statistics.mean(ay), statistics.mean(az))))
print("== 加速度計單獨算的傾角 vs EKF ==")
print(f"  roll  加速度計 {roll_acc:7.3f}°  EKF {statistics.mean(math.degrees(r.roll) for r in att):7.3f}°")
print(f"  pitch 加速度計 {pitch_acc:7.3f}°  EKF {statistics.mean(math.degrees(r.pitch) for r in att):7.3f}°")
