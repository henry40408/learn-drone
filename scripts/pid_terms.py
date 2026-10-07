"""PID 三項各自的「量」：懸停在 10 m，t=2 秒時突然多了載重，看 P、I、D 如何貢獻推力。

模型：a = 2g(u - h) - c·v，h 是懸停所需推力，載重使 h 由 0.5 變 0.6。
起始時積分已累積到剛好撐住 0.5 的量（代表之前已穩定懸停）。
用法：vendor/venv/bin/python -I scripts/pid_terms.py <輸出.png>
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

G, DRAG, DT, T_END, TARGET = 9.8, 3.0, 0.01, 12.0, 10.0
KP, KI, KD = 1.0, 0.5, 1.2
LOAD_T, HOVER_BEFORE, HOVER_AFTER = 2.0, 0.5, 0.6

alt, vel = TARGET, 0.0
integral = HOVER_BEFORE / KI  # 積分已累積到剛好撐住 0.5
prev_err = 0.0
ts, hs, ps, is_, ds, us = [], [], [], [], [], []
for n in range(int(T_END / DT)):
    t = n * DT
    hover = HOVER_AFTER if t >= LOAD_T else HOVER_BEFORE
    err = TARGET - alt
    integral = min(max(integral + err * DT, -2.0), 2.0)
    p, i, d = KP * err, KI * integral, KD * (err - prev_err) / DT
    prev_err = err
    u = min(max(p + i + d, 0.0), 1.0)
    vel += (2 * G * (u - hover) - DRAG * vel) * DT
    alt += vel * DT
    ts.append(t); hs.append(alt); ps.append(p); is_.append(i); ds.append(d); us.append(u)

print(f"最低 {min(hs):.2f} m，最後 {hs[-1]:.3f} m")
for t in (1.9, 2.1, 2.5, 3, 4, 6, 8, 11.9):
    k = int(t / DT)
    print(f"t={t:5.1f}  P={ps[k]:6.3f}  I={is_[k]:6.3f}  D={ds[k]:6.3f}  合計={us[k]:.3f}")

plt.rcParams["font.sans-serif"] = ["PingFang TC", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
fig, (top, bot) = plt.subplots(2, 1, figsize=(9, 7), dpi=150, facecolor="#fcfcfb",
                               sharex=True, gridspec_kw={"height_ratios": [1, 2]})
for ax in (top, bot):
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    ax.tick_params(colors="#52514e")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.axvline(LOAD_T, color="#8a8984", linestyle="--", linewidth=1.2, label="_load")

top.plot(ts, hs, color="#0b0b0b", linewidth=2)
top.axhline(TARGET, color="#8a8984", linewidth=1)
top.set_ylabel("高度（公尺）", color="#52514e")
top.set_title("PID 三項各自的量：懸停中突然多了載重（t = 2 秒）", loc="left", color="#0b0b0b", fontsize=13)
top.set_ylim(9.92, 10.01)
top.text(LOAD_T + 0.15, 9.925, "多了載重，需要的推力 50% → 60%", color="#52514e", fontsize=10)

bot.axhline(0, color="#c3c2b7", linewidth=1, label="_zero")
bot.plot(ts, ps, color="#2a78d6", linewidth=2, label="P（現在差多少）")
bot.plot(ts, is_, color="#eb6834", linewidth=2, label="I（累積的誤差）")
bot.plot(ts, ds, color="#1baf7a", linewidth=2, label="D（誤差變化多快）")
bot.plot(ts, us, color="#0b0b0b", linewidth=1.5, linestyle=":", label="合計 = P + I + D")
bot.set_ylim(-0.3, 0.8)
bot.set_xlim(0, T_END)
bot.set_xlabel("時間（秒）", color="#52514e")
bot.set_ylabel("推力貢獻（1.0 = 100%）", color="#52514e")
bot.text(0.05, 0.44, "載重前：I 撐住 50%", color="#52514e", fontsize=10)
bot.text(T_END - 0.1, 0.63, "I 慢慢累積到 60%", color="#eb6834", fontsize=10, ha="right", va="bottom")
bot.text(T_END - 0.1, 0.03, "P、D 回到 0", color="#52514e", fontsize=10, ha="right", va="bottom")
bot.legend(frameon=False, loc="center right", bbox_to_anchor=(1.0, 0.6), labelcolor="#0b0b0b", fontsize=10)
fig.tight_layout()
fig.savefig(sys.argv[1], facecolor=fig.get_facecolor())
