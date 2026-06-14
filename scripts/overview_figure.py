"""
Compact Knowledge Honeypot overview figure.

Outputs:
    figures/overview_figure.pdf
    figures/overview_figure.png
"""

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)


C_ATTACKER = "#E8593C"
C_DEFENDER = "#1D9E75"
C_HONEYPOT = "#378ADD"
C_LIGHT_A = "#FAECE7"
C_LIGHT_D = "#E1F5EE"
C_LIGHT_H = "#E6F1FB"
C_TEXT = "#1A1A1A"
C_MUTED = "#555555"
C_DIVIDER = "#C8C8C8"


plt.rcParams.update(
    {
        "font.family": "Georgia",
        "font.size": 13,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


fig, ax = plt.subplots(figsize=(15.6, 4.45))
ax.set_xlim(0, 15.6)
ax.set_ylim(0, 4.45)
ax.axis("off")
fig.patch.set_facecolor("white")


def box(x, y, w, h, label, sublabel=None, facecolor=C_LIGHT_D, edgecolor=C_DEFENDER, lw=1.15):
    rect = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.035,rounding_size=0.07",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
        zorder=3,
    )
    ax.add_patch(rect)
    cx, cy = x + w / 2, y + h / 2
    if sublabel:
        ax.text(cx, cy + 0.12, label, ha="center", va="center", fontsize=11, fontweight="bold", color=C_TEXT, zorder=4)
        ax.text(cx, cy - 0.14, sublabel, ha="center", va="center", fontsize=9.2, color=C_MUTED, zorder=4)
    else:
        ax.text(cx, cy, label, ha="center", va="center", fontsize=11, fontweight="bold", color=C_TEXT, zorder=4)


def arrow(x1, y1, x2, y2, color=C_MUTED, lw=1.25, dashed=False, label=None, dy=0.18):
    ls = (0, (4, 3)) if dashed else "solid"
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color=color, lw=lw, linestyle=ls, shrinkA=2, shrinkB=2),
        zorder=2,
    )
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, ha="center", va="center", fontsize=9.2, color=C_MUTED, zorder=5)


def curved_arrow(x1, y1, x2, y2, rad, color=C_MUTED, lw=1.25, dashed=False, label=None):
    ls = (0, (4, 3)) if dashed else "solid"
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="->",
            color=color,
            lw=lw,
            linestyle=ls,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=2,
            shrinkB=2,
        ),
        zorder=2,
    )
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + abs(rad) * 0.55, label, ha="center", va="center", fontsize=9, color=C_MUTED, zorder=5)


def header(x, text, color):
    ax.text(x, 4.2, text, ha="center", va="center", fontsize=14, fontweight="bold", color=color)


for x in (4.75, 9.8):
    ax.plot([x, x], [0.25, 4.05], color=C_DIVIDER, lw=0.8, ls="--", zorder=1)

header(2.3, "Attacker", C_ATTACKER)
header(7.3, "Defender (Victim API)", C_DEFENDER)
header(12.7, "Honeypot KG", C_HONEYPOT)


# Attacker lane
box(0.45, 3.15, 3.05, 0.58, "Surrogate model", facecolor=C_LIGHT_A, edgecolor=C_ATTACKER)
box(0.45, 2.15, 3.05, 0.58, "Query selection", "PPL + BFS entities", facecolor=C_LIGHT_A, edgecolor=C_ATTACKER)
box(0.45, 0.88, 3.05, 0.58, "Collected QA pairs", facecolor=C_LIGHT_A, edgecolor=C_ATTACKER)
arrow(1.98, 3.15, 1.98, 2.73, color=C_ATTACKER, label="acquire")
curved_arrow(0.45, 1.17, 0.45, 3.43, rad=-0.42, color=C_ATTACKER, dashed=True, label="ICL / fine-tune")


# Defender lane
box(5.35, 3.15, 3.85, 0.58, "Victim model (GPT-4.1)", facecolor=C_LIGHT_D, edgecolor=C_DEFENDER)
box(5.35, 2.16, 3.85, 0.62, "Attacker detector", "source · length · keywords · timing", facecolor=C_LIGHT_D, edgecolor=C_DEFENDER)

decision = mpatches.RegularPolygon(
    (7.28, 1.55),
    numVertices=4,
    radius=0.48,
    orientation=0,
    facecolor="white",
    edgecolor=C_DEFENDER,
    linewidth=1.15,
    zorder=3,
)
ax.add_patch(decision)
ax.text(7.28, 1.55, "$s_t>\\tau$?", ha="center", va="center", fontsize=10.2, fontweight="bold", color=C_TEXT, zorder=4)
box(5.35, 0.62, 3.85, 0.55, "Normal response", facecolor=C_LIGHT_D, edgecolor=C_DEFENDER)

arrow(3.5, 2.45, 5.35, 3.44, color=C_ATTACKER, label="query")
arrow(7.28, 3.15, 7.28, 2.78, color=C_DEFENDER)
arrow(7.28, 2.16, 7.28, 2.03, color=C_DEFENDER)
arrow(7.28, 1.08, 7.28, 1.17, color=C_DEFENDER, label="no", dy=0.02)
curved_arrow(5.35, 0.9, 3.5, 1.17, rad=0.18, color=C_DEFENDER, dashed=True, label="response")


# Honeypot lane
hkg_outer = FancyBboxPatch(
    (10.25, 2.42),
    4.55,
    1.37,
    boxstyle="round,pad=0.055,rounding_size=0.08",
    facecolor=C_LIGHT_H,
    edgecolor=C_HONEYPOT,
    linewidth=1.35,
    zorder=3,
)
ax.add_patch(hkg_outer)
ax.text(12.52, 3.6, "Honeypot Knowledge Graph", ha="center", va="center", fontsize=11.2, fontweight="bold", color=C_TEXT, zorder=4)
ax.text(12.52, 3.36, "1,500 nodes · $d_{min}=3$ · low utility", ha="center", va="center", fontsize=9.4, color=C_MUTED, zorder=4)

for x, text in [
    (10.48, "Historical\nminutiae"),
    (11.85, "Peripheral\ntaxonomy"),
    (13.22, "Niche\nprocedures"),
]:
    box(x, 2.62, 1.22, 0.47, text, facecolor="white", edgecolor=C_HONEYPOT, lw=0.75)

box(10.25, 1.32, 4.55, 0.62, "Breadcrumb injector", "high-degree HKG target", facecolor=C_LIGHT_H, edgecolor=C_HONEYPOT)
box(10.25, 0.55, 4.55, 0.55, "HKG response", "true · non-transferable · new targets", facecolor=C_LIGHT_H, edgecolor=C_HONEYPOT)

arrow(7.76, 1.55, 10.25, 1.63, color=C_HONEYPOT, label="yes")
arrow(12.52, 1.94, 12.52, 2.42, color=C_HONEYPOT, label="steer")
arrow(12.52, 2.42, 12.52, 1.1, color=C_HONEYPOT, dashed=True)
curved_arrow(14.8, 0.83, 14.8, 1.62, rad=-0.55, color=C_HONEYPOT, label="entrapment loop")
curved_arrow(10.25, 0.82, 3.5, 0.95, rad=0.13, color=C_HONEYPOT, dashed=True, label="honeypot response")


# Compact bottom takeaways
ax.text(2.3, 0.28, "Budget waste", ha="center", va="center", fontsize=10.2, color=C_ATTACKER, fontstyle="italic")
ax.text(7.3, 0.28, "Benign users unchanged", ha="center", va="center", fontsize=10.2, color=C_DEFENDER, fontstyle="italic")
ax.text(12.7, 0.28, "Self-reinforcing lure", ha="center", va="center", fontsize=10.2, color=C_HONEYPOT, fontstyle="italic")

legend_elements = [
    mpatches.Patch(facecolor=C_LIGHT_A, edgecolor=C_ATTACKER, label="Attacker"),
    mpatches.Patch(facecolor=C_LIGHT_D, edgecolor=C_DEFENDER, label="Defender"),
    mpatches.Patch(facecolor=C_LIGHT_H, edgecolor=C_HONEYPOT, label="Honeypot"),
]
ax.legend(
    handles=legend_elements,
    loc="lower center",
    ncol=3,
    fontsize=9.5,
    framealpha=0.95,
    edgecolor=C_DIVIDER,
    bbox_to_anchor=(0.5, -0.035),
)

plt.tight_layout(pad=0.25)
for ext in ("pdf", "png"):
    plt.savefig(FIGURES / f"overview_figure.{ext}", dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved: {FIGURES / 'overview_figure.pdf'}")
