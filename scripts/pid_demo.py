"""PID 示範：一維高度控制，從 0 m 升到 10 m，比較 P、PI、PID。

模型：推力 u 在 0–1 之間，懸停需要 u = 0.5；a = 2g(u - 0.5) - c·v（c 是空氣阻力）。
用法：vendor/venv/bin/python -I scripts/pid_demo.py <輸出.png>
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

G, DRAG, DT, T_END, TARGET = 9.8, 3.0, 0.01, 15.0, 10.0
T_START = 2.5  # 圖只顯示 10 m 附近，略過前面的爬升段
KP, KI, KD = 1.0, 0.5, 1.2


def simulate(kp, ki, kd):
    alt = vel = integral = 0.0
    prev_err = TARGET - alt
    ts, hs = [], []
    for i in range(int(T_END / DT)):
        err = TARGET - alt
        integral = min(max(integral + err * DT, -1.0), 1.0)  # 限制積分，避免累積過頭（anti-windup）
        deriv = (err - prev_err) / DT
        prev_err = err
        u = min(max(kp * err + ki * integral + kd * deriv, 0.0), 1.0)
        acc = 2 * G * (u - 0.5) - DRAG * vel
        vel += acc * DT
        alt = max(alt + vel * DT, 0.0)
        ts.append(i * DT)
        hs.append(alt)
    return ts, hs


runs = [("只有 P", (KP, 0, 0), "#2a78d6"), ("P + I", (KP, KI, 0), "#eb6834"), ("P + I + D", (KP, KI, KD), "#1baf7a")]
results = {name: simulate(*gains) for name, gains, _ in runs}
for name, (_, hs) in results.items():
    print(f"{name}: 最後 {hs[-1]:.2f} m，最高 {max(hs):.2f} m")

plt.rcParams["font.sans-serif"] = ["PingFang TC", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(9, 5), dpi=150, facecolor="#fcfcfb")
ax.set_facecolor("#fcfcfb")
ax.axhline(TARGET, color="#8a8984", linestyle="--", linewidth=1.2)
ax.text(T_END - 0.1, TARGET + 0.04, "目標 10 m", color="#52514e", fontsize=10, ha="right")
for name, _, color in runs:
    ts, hs = results[name]
    ax.plot(ts, hs, color=color, linewidth=2, label=name)
ax.text(T_END + 0.15, results["只有 P"][1][-1], "只有 P", color="#0b0b0b", fontsize=10, va="center")
ax.text(6.9, 9.72, "P + I + D：平順到 10 m", color="#0b0b0b", fontsize=10)
ax.set_xlim(T_START, T_END)
ax.set_ylim(9.0, 10.7)
peak_t, peak_h = max(zip(*results["P + I"]), key=lambda p: p[1])
ax.annotate(f"P + I：衝過頭 {peak_h - TARGET:.2f} m", (peak_t, peak_h), (peak_t + 1.0, peak_h + 0.1),
            color="#52514e", fontsize=10, arrowprops=dict(arrowstyle="-", color="#8a8984"))
ax.annotate("", (T_END - 1.5, 9.5), (T_END - 1.5, TARGET),
            arrowprops=dict(arrowstyle="<->", color="#2a78d6"))
ax.text(T_END - 1.3, 9.72, f"卡住，差 {TARGET - results['只有 P'][1][-1]:.1f} m", color="#52514e", fontsize=10)
ax.set_xlabel("時間（秒）", color="#52514e")
ax.set_ylabel("高度（公尺）", color="#52514e")
ax.set_title("PID 控制高度：放大 10 m 附近（從 0 m 升到 10 m）", loc="left", color="#0b0b0b", fontsize=13)
ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
ax.tick_params(colors="#52514e")
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color("#c3c2b7")
ax.legend(frameon=False, loc="lower right", labelcolor="#0b0b0b")
fig.subplots_adjust(right=0.86)
fig.savefig(sys.argv[1], facecolor=fig.get_facecolor())
