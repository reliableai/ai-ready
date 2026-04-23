"""
Two images illustrating bias vs noise:
  1. With target visible  -> can see both bias (offset) and noise (spread)
  2. Without target       -> can still measure noise, cannot measure bias
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D

# ---- shared data ----------------------------------------------------------
rng = np.random.default_rng(7)
n = 25
# true target at origin; shots biased to (1.6, 1.2) with gaussian noise
bias_vec = np.array([1.6, 1.2])
noise_sd = 0.55
shots = rng.normal(loc=bias_vec, scale=noise_sd, size=(n, 2))
shot_mean = shots.mean(axis=0)

# ---- style ----------------------------------------------------------------
NAVY       = "#1E2761"
INK        = "#263069"
TEXT       = "#E7ECFF"
SHOT       = "#F97316"   # orange
SHOT_EDGE  = "#7a3a0a"
BULLS      = "#22C55E"   # green bullseye
MEAN_COLOR = "#EAB308"   # yellow
BIAS_COLOR = "#EF4444"   # red arrow
RING       = "#3B82F6"

def style_axes(ax, title):
    ax.set_facecolor(INK)
    ax.set_xlim(-4, 4)
    ax.set_ylim(-4, 4)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#475080")
        s.set_linewidth(0.8)
    ax.set_title(title, color=TEXT, fontsize=17, pad=12, weight="bold",
                 loc="center", wrap=True)

def draw_shots(ax):
    ax.scatter(shots[:,0], shots[:,1],
               s=110, c=SHOT, edgecolors=SHOT_EDGE, linewidths=0.8,
               alpha=0.9, zorder=4)

def draw_shot_mean(ax):
    ax.scatter([shot_mean[0]], [shot_mean[1]],
               s=320, marker="X", c=MEAN_COLOR,
               edgecolors="black", linewidths=1.2, zorder=6,
               label="observed mean")

def draw_spread_ring(ax, label_side="right"):
    # 1-sigma empirical ring centered on observed mean
    sd = shots.std(axis=0).mean()
    ring = Circle(shot_mean, sd, fill=False, ls="--",
                  ec=MEAN_COLOR, lw=1.8, zorder=5, alpha=0.95)
    ax.add_patch(ring)
    if label_side == "right":
        tx, ty = shot_mean[0] + 1.55, shot_mean[1] + 1.35
        xy = shot_mean + np.array([sd*0.75, sd*0.75])
    else:
        tx, ty = shot_mean[0] - 1.9, shot_mean[1] + 1.35
        xy = shot_mean + np.array([-sd*0.75, sd*0.75])
    ax.annotate("noise\n(empirical spread)",
                xy=xy, xytext=(tx, ty),
                color=MEAN_COLOR, fontsize=12, weight="bold",
                ha="center", va="center",
                arrowprops=dict(arrowstyle="-", color=MEAN_COLOR, lw=1.2))

# ---- FIGURE 1: WITH TARGET -----------------------------------------------
fig, ax = plt.subplots(figsize=(8.2, 8.2), facecolor=NAVY,
                       constrained_layout=True)
style_axes(ax, "With ground truth — bias AND noise visible")

# bullseye rings
for r, a in [(3.0, 0.18), (2.0, 0.28), (1.0, 0.42), (0.35, 0.95)]:
    ax.add_patch(Circle((0,0), r, color=BULLS, alpha=a, zorder=1))
ax.plot(0, 0, marker="+", ms=18, mew=2.5, color="white", zorder=3)
ax.annotate("true value",
            xy=(0,0), xytext=(-2.9, -3.3),
            color="white", fontsize=12, weight="bold",
            arrowprops=dict(arrowstyle="->", color="white", lw=1.2))

draw_shots(ax)
draw_shot_mean(ax)
draw_spread_ring(ax, label_side="right")

# bias arrow: from truth to observed mean
ax.annotate("",
            xy=shot_mean, xytext=(0, 0),
            arrowprops=dict(arrowstyle="->", color=BIAS_COLOR,
                            lw=2.8, shrinkA=10, shrinkB=12))
# label offset perpendicular to the bias vector so it doesn't overlap the ring
ang = np.arctan2(bias_vec[1], bias_vec[0])
perp = np.array([-np.sin(ang), np.cos(ang)]) * 0.45
mid = shot_mean * 0.5 + perp
ax.text(mid[0], mid[1], "bias",
        color=BIAS_COLOR, fontsize=16, weight="bold",
        rotation=np.degrees(ang),
        ha="center", va="center")

# legend
legend_items = [
    Line2D([0],[0], marker="o", color="none", markerfacecolor=SHOT,
           markeredgecolor=SHOT_EDGE, markersize=10, label="measurements"),
    Line2D([0],[0], marker="X", color="none", markerfacecolor=MEAN_COLOR,
           markeredgecolor="black", markersize=13, label="observed mean"),
    Line2D([0],[0], marker="+", color="white", markersize=13,
           mew=2, linestyle="none", label="true value"),
]
leg = ax.legend(handles=legend_items, loc="lower right",
                facecolor=INK, edgecolor="#475080", labelcolor=TEXT,
                fontsize=10, framealpha=0.95)

out1 = "/sessions/wizardly-dazzling-pasteur/mnt/ai-native/slides_assets/bias_noise_with_target.png"
fig.savefig(out1, dpi=200, facecolor=NAVY, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)

# ---- FIGURE 2: WITHOUT TARGET --------------------------------------------
fig, ax = plt.subplots(figsize=(8.2, 8.2), facecolor=NAVY,
                       constrained_layout=True)
style_axes(ax, "Without ground truth — only noise is measurable")

# NO bullseye, NO origin marker
draw_shots(ax)
draw_shot_mean(ax)
draw_spread_ring(ax, label_side="right")

# explanatory annotations
ax.text(-3.7, 3.55,
        "We can still compute:\n"
        " • observed mean\n"
        " • empirical std / CI\n"
        " • bootstrap distribution",
        color=TEXT, fontsize=11.5, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.5", fc=NAVY, ec="#475080", lw=0.8))

ax.text(-3.7, -2.2,
        "We CANNOT compute:\n"
        " • bias\n"
        " • distance from truth\n"
        " • whether our answer is correct",
        color="#FCA5A5", fontsize=11.5, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.5", fc=NAVY, ec=BIAS_COLOR, lw=1.0))

# Greyed-out ghost of where truth WOULD be — optional faint crosshair
# (commented out to keep the "no target" idea pure)
# ax.plot(0, 0, marker="+", ms=14, mew=1.2, color="#475080", alpha=0.6, zorder=2)

legend_items = [
    Line2D([0],[0], marker="o", color="none", markerfacecolor=SHOT,
           markeredgecolor=SHOT_EDGE, markersize=10, label="measurements"),
    Line2D([0],[0], marker="X", color="none", markerfacecolor=MEAN_COLOR,
           markeredgecolor="black", markersize=13, label="observed mean"),
    Line2D([0],[0], linestyle="--", color=MEAN_COLOR, lw=1.6,
           label="empirical spread (noise)"),
]
ax.legend(handles=legend_items, loc="lower right",
          facecolor=INK, edgecolor="#475080", labelcolor=TEXT,
          fontsize=10, framealpha=0.95)

out2 = "/sessions/wizardly-dazzling-pasteur/mnt/ai-native/slides_assets/bias_noise_without_target.png"
fig.savefig(out2, dpi=200, facecolor=NAVY, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)

print("WROTE:", out1)
print("WROTE:", out2)
print(f"observed mean = ({shot_mean[0]:.2f}, {shot_mean[1]:.2f})")
print(f"true bias     = ({bias_vec[0]:.2f}, {bias_vec[1]:.2f})")
print(f"empirical sd  = {shots.std(axis=0).mean():.3f}")
