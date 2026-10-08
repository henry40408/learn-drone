"""PID 完整升空：0 m → 9.5 m → 10 m，同時畫出高度與 P、I、D 三項的數字。

模型與增益同 pid_demo.py：推力 u 在 0–1 之間，懸停需要 u = 0.5；a = 2g(u - 0.5) - c·v。
左欄是整段 15 秒，右欄放大 4–13 秒（接近 9.5 m 到停在 10 m 的過程）。
用法：vendor/venv/bin/python -I scripts/pid_climb.py <輸出.png>
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

G, DRAG, DT, T_END, TARGET = 9.8, 3.0, 0.01, 15.0, 10.0
KP, KI, KD = 1.0, 0.5, 1.2

alt = vel = integral = 0.0
prev_err = TARGET - alt
ts, hs, ps, is_, ds, us = [], [], [], [], [], []
for n in range(int(T_END / DT)):
    err = TARGET - alt
    integral = min(max(integral + err * DT, -1.0), 1.0)  # 同 pid_demo.py：限制積分
    p, i, d = KP * err, KI * integral, KD * (err - prev_err) / DT
    prev_err = err
    u = min(max(p + i + d, 0.0), 1.0)
    vel += (2 * G * (u - 0.5) - DRAG * vel) * DT
    alt = max(alt + vel * DT, 0.0)
    ts.append(n * DT); hs.append(alt); ps.append(p); is_.append(i); ds.append(d); us.append(u)

t95 = next(t for t, h in zip(ts, hs) if h >= 9.5)
print(f"到達 9.5 m：t={t95:.2f} 秒")
for t in (0.0, 0.1, 1.0, 2.0, 3.0, t95, 6.0, 8.0, 11.0, 14.9):
    k = min(int(round(t / DT)), len(ts) - 1)
    print(f"t={ts[k]:5.2f}  高度={hs[k]:6.2f}  P={ps[k]:6.2f}  I={is_[k]:5.2f}  D={ds[k]:6.2f}  實際推力={us[k]:.2f}")

plt.rcParams["font.sans-serif"] = ["PingFang TC", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(2, 2, figsize=(12, 7.5), dpi=150, facecolor="#fcfcfb",
                         gridspec_kw={"height_ratios": [1, 1.6]})
(alt_l, alt_r), (pid_l, pid_r) = axes
for ax in axes.flat:
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    ax.tick_params(colors="#52514e")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")

for ax in (alt_l, alt_r):
    ax.plot(ts, hs, color="#0b0b0b", linewidth=2)
    ax.axhline(TARGET, color="#8a8984", linestyle="--", linewidth=1.2)
    ax.axhline(9.5, color="#8a8984", linestyle=":", linewidth=1.2)
    ax.axvline(t95, color="#c3c2b7", linewidth=1)
for ax in (pid_l, pid_r):
    ax.axhline(0, color="#c3c2b7", linewidth=1)
    ax.plot(ts, ps, color="#2a78d6", linewidth=2, label="P（現在差多少）")
    ax.plot(ts, is_, color="#eb6834", linewidth=2, label="I（累積的誤差）")
    ax.plot(ts, ds, color="#1baf7a", linewidth=2, label="D（誤差變化多快）")
    ax.plot(ts, us, color="#0b0b0b", linewidth=1.5, linestyle=":", label="實際推力（P+I+D，夾在 0–1）")
    ax.axvline(t95, color="#c3c2b7", linewidth=1)

alt_l.set_xlim(0, T_END); alt_l.set_ylim(0, 11)
alt_l.text(T_END - 0.1, TARGET + 0.2, "目標 10 m", color="#52514e", fontsize=10, ha="right")
alt_l.text(7.5, 8.6, "虛線 9.5 m", color="#52514e", fontsize=10)
alt_l.set_ylabel("高度（公尺）", color="#52514e")
alt_l.set_title("整段：0 → 10 m（15 秒）", loc="left", color="#0b0b0b", fontsize=12)
alt_r.set_xlim(4, 13); alt_r.set_ylim(9.0, 10.2)
alt_r.text(t95 + 0.1, 9.05, f"t = {t95:.1f} 秒：到達 9.5 m", color="#52514e", fontsize=10)
alt_r.set_title("放大：4–13 秒（9.5 → 10 m）", loc="left", color="#0b0b0b", fontsize=12)

pid_l.set_xlim(0, T_END); pid_l.set_ylim(-4.5, 3)
pid_l.set_xlabel("時間（秒）", color="#52514e")
pid_l.set_ylabel("推力貢獻（1.0 = 100%，不管單位）", color="#52514e")
pid_l.text(0.15, 2.55, "P 起始 10（圖外）", color="#2a78d6", fontsize=10)
pid_l.text(0.15, 1.15, "實際推力：前 2 秒 = 1.0", color="#0b0b0b", fontsize=10)
pid_l.text(2.0, -4.25, "D 負值 = 煞車", color="#1baf7a", fontsize=10)
pid_l.legend(frameon=False, loc="upper right", labelcolor="#0b0b0b", fontsize=9)

pid_r.set_xlim(4, 13); pid_r.set_ylim(-0.1, 1.05)
pid_r.set_xlabel("時間（秒）", color="#52514e")
pid_r.text(12.9, 0.52, "I 撐住 0.5", color="#eb6834", fontsize=10, ha="right", va="bottom")
pid_r.text(12.9, 0.03, "P、D 漸漸回到 0", color="#52514e", fontsize=10, ha="right", va="bottom")

fig.suptitle("PID 三項的數字怎麼變：0 m → 9.5 m → 10 m", x=0.01, ha="left", color="#0b0b0b", fontsize=14)
fig.tight_layout()
fig.savefig(sys.argv[1], facecolor=fig.get_facecolor())
