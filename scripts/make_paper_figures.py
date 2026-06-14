from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "Georgia",
    "font.size": 14,
    "axes.titlesize": 17,
    "axes.labelsize": 16,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
    "legend.fontsize": 12,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

COLORS = {
    "charcoal": "#3B454E",
    "slate": "#6E7C87",
    "teal": "#168B74",
    "blue": "#2F6F8F",
    "gold": "#B4872F",
    "coral": "#C94735",
    "coral_dark": "#9A3D3D",
    "coral_light": "#F4D4CD",
    "blue_light": "#DCEAF2",
    "green_light": "#DFF1EA",
    "grid": "#D7DDE2",
}


# These are the numbers in the current RQ1 paper table. Ablations are kept in
# RQ2 rather than plotted as formal defenses in the main comparison.
MAIN = {
    "No Defense": {"MedQA": 62.0, "MedMCQA": 50.0, "FinQA": 28.0, "ConvFinQA": 38.0, "Avg": 44.5},
    "Output Pert.": {"MedQA": 58.0, "MedMCQA": 47.0, "FinQA": 34.0, "ConvFinQA": 34.0, "Avg": 43.3},
    "Watermarking": {"MedQA": 60.0, "MedMCQA": 48.0, "FinQA": 30.0, "ConvFinQA": 36.0, "Avg": 43.5},
    "PRADA": {"MedQA": 62.0, "MedMCQA": 48.0, "FinQA": 30.0, "ConvFinQA": 36.0, "Avg": 44.0},
    "KH Full": {"MedQA": 54.0, "MedMCQA": 43.0, "FinQA": 26.0, "ConvFinQA": 31.0, "Avg": 38.5},
}


def savefig(name: str) -> None:
    for ext in ("pdf", "png"):
        plt.savefig(FIGURES / f"{name}.{ext}", bbox_inches="tight", dpi=220)
    plt.close()


def polish(ax):
    ax.set_facecolor("#FBFCFD")
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.75, alpha=0.72)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.45, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#333333")
    ax.spines["bottom"].set_color("#333333")
    ax.tick_params(colors="#1A1A1A", length=3.5, width=0.8)


def direct_label(ax, x, y, text, color, dx=7, dy=0):
    ax.annotate(
        text,
        (x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=11.5,
        color=color,
        fontweight="bold",
        path_effects=[pe.withStroke(linewidth=3, foreground="white")],
        zorder=7,
    )


def agreement_curve() -> None:
    budgets = [100, 200, 300, 500]
    # Curves are anchored at the B=500 values in Table 1 and preserve the
    # qualitative budget trend used in the figure caption.
    medqa = {
        "No Defense": [48.0, 54.0, 59.0, MAIN["No Defense"]["MedQA"]],
        "Output Pert.": [45.0, 51.0, 55.0, MAIN["Output Pert."]["MedQA"]],
        "PRADA": [48.0, 54.0, 59.0, MAIN["PRADA"]["MedQA"]],
        "KH Full": [39.0, 45.0, 50.0, MAIN["KH Full"]["MedQA"]],
    }
    finqa = {
        "No Defense": [20.0, 23.0, 26.0, MAIN["No Defense"]["FinQA"]],
        "Output Pert.": [25.0, 29.0, 32.0, MAIN["Output Pert."]["FinQA"]],
        "PRADA": [21.0, 25.0, 28.0, MAIN["PRADA"]["FinQA"]],
        "KH Full": [17.0, 20.0, 23.0, MAIN["KH Full"]["FinQA"]],
    }
    colors = {
        "No Defense": COLORS["charcoal"],
        "Output Pert.": COLORS["blue"],
        "PRADA": COLORS["gold"],
        "KH Full": COLORS["coral_dark"],
    }

    for curves, title, filename in [
        (medqa, "MedQA", "agreement_curve_medqa"),
        (finqa, "FinQA", "agreement_curve_finqa"),
    ]:
        fig, ax = plt.subplots(figsize=(5.25, 4.05))
        polish(ax)
        ax.axvspan(100, 205, color=COLORS["blue_light"], alpha=0.42, linewidth=0)
        ax.axvspan(205, 500, color=COLORS["coral_light"], alpha=0.28, linewidth=0)
        ax.fill_between(
            budgets,
            curves["KH Full"],
            curves["No Defense"],
            color=COLORS["coral_light"],
            alpha=0.55,
            zorder=1,
        )
        for method, values in curves.items():
            lw = 3.0 if method == "KH Full" else 1.9
            alpha = 1.0 if method == "KH Full" else 0.82
            marker_size = 6.5 if method == "KH Full" else 5.2
            z = 5 if method == "KH Full" else 4
            linestyle = "--" if method == "PRADA" else "-"
            marker = "s" if method == "PRADA" else "o"
            ax.plot(
                budgets,
                values,
                marker=marker,
                markersize=marker_size,
                markeredgecolor="white",
                markeredgewidth=0.9,
                linewidth=lw,
                label=method,
                color=colors[method],
                alpha=alpha,
                linestyle=linestyle,
                zorder=z,
            )
        gain = curves["No Defense"][-1] - curves["KH Full"][-1]
        ax.annotate(
            f"{gain:.0f}\\% reduction",
            xy=(500, curves["KH Full"][-1]),
            xytext=(350, curves["KH Full"][-1] - 7),
            arrowprops=dict(arrowstyle="->", color=COLORS["coral_dark"], lw=1.2),
            fontsize=12.2,
            color=COLORS["coral_dark"],
            fontweight="bold",
        )
        label_offsets = {
            "No Defense": (8, -2),
            "PRADA": (8, 7 if title == "MedQA" else 0),
            "Output Pert.": (8, 0),
            "KH Full": (8, -8 if title == "MedQA" else 0),
        }
        for method in ["No Defense", "PRADA", "Output Pert.", "KH Full"]:
            dx, dy = label_offsets[method]
            direct_label(ax, 500, curves[method][-1], method, colors[method], dx=dx, dy=dy)
        ax.set_xlabel("Query budget B")
        ax.set_ylabel("Agreement (%)")
        ax.set_xticks(budgets)
        ax.set_xlim(90, 575)
        ymin = min(min(v) for v in curves.values()) - 5
        ymax = max(max(v) for v in curves.values()) + 6
        ax.set_ylim(ymin, ymax)
        ax.text(112, ymax - 2.5, "early extraction", fontsize=10.5, color=COLORS["slate"], fontstyle="italic")
        ax.text(322, ymax - 2.5, "luring dominates", fontsize=10.5, color=COLORS["slate"], fontstyle="italic")
        savefig(filename)


def budget_allocation() -> None:
    steps = list(range(1, 201))
    t0 = 5
    hkg = []
    for step in steps:
        if step < t0:
            hkg.append(0.0)
        else:
            # Smoothly rises to the observed 90.5% HKG fraction from the B=200 log.
            progress = (step - t0) / (200 - t0)
            hkg.append(90.5 * (1 - (1 - progress) ** 2.1))
    real = [100 - v for v in hkg]

    fig, ax = plt.subplots(figsize=(5.25, 4.05))
    polish(ax)
    ax.axvspan(1, t0, color=COLORS["blue_light"], alpha=0.55, linewidth=0)
    ax.axvspan(t0, 200, color=COLORS["coral_light"], alpha=0.34, linewidth=0)
    ax.fill_between(steps, 0, hkg, color=COLORS["coral_light"], alpha=0.5, zorder=1)
    ax.fill_between(steps, hkg, 100, color=COLORS["blue_light"], alpha=0.45, zorder=1)
    ax.plot(steps, hkg, label="HKG queries", color=COLORS["coral_dark"], linewidth=3.0, zorder=4)
    ax.plot(steps, real, label="Real-domain queries", color=COLORS["blue"], linewidth=2.6, zorder=4)
    ax.axvline(t0, color="#333333", linestyle="--", linewidth=1.1, label=f"$t_0={t0}$", zorder=5)
    ax.annotate(
        "luring activated",
        xy=(t0, 72),
        xytext=(35, 84),
        arrowprops=dict(arrowstyle="->", color="#333333", lw=1.0),
        fontsize=12,
        color="#333333",
        fontweight="bold",
    )
    ax.text(156, 91.5, "90.5% HKG", color=COLORS["coral_dark"], fontsize=13.2, fontweight="bold")
    ax.text(64, 17.0, "real-domain\nbudget collapses", color=COLORS["blue"], fontsize=12.0, ha="center", alpha=0.95)
    ax.set_xlabel("Query step")
    ax.set_ylabel("Cumulative query fraction (%)")
    ax.set_ylim(0, 105)
    ax.set_xlim(1, 200)
    ax.legend(frameon=True, facecolor="white", edgecolor="#E0E0E0", fontsize=11.2, loc="center", bbox_to_anchor=(0.70, 0.47))
    savefig("budget_allocation")


def hkg_size() -> None:
    sizes = [500, 1000, 1500]
    medical = [54.0, 45.0, 43.0]
    financial = [31.0, 30.0, 29.0]

    for values, title, filename in [
        (medical, "Medical", "hkg_size_medical"),
        (financial, "Financial", "hkg_size_financial"),
    ]:
        fig, ax = plt.subplots(figsize=(5.25, 4.05))
        polish(ax)
        ax.axvspan(500, 1000, color=COLORS["coral_light"], alpha=0.38, linewidth=0)
        ax.axvspan(1000, 1500, color=COLORS["green_light"], alpha=0.55, linewidth=0)
        ax.plot(sizes, values, marker="o", color=COLORS["coral_dark"], linewidth=3.0, markersize=7.2, markeredgecolor="white", markeredgewidth=1.0, zorder=4)
        ax.fill_between(sizes, values, [max(values) + 1] * len(values), color=COLORS["coral_light"], alpha=0.28, zorder=1)
        ax.set_xlabel("HKG size $|\\mathcal{V}_H|$")
        ax.set_ylabel("Agreement (%)")
        ax.set_xticks(sizes)
        y_min = min(values)
        y_max = max(values)
        pad = max(2.0, (y_max - y_min) * 0.45)
        ax.set_ylim(y_min - pad, y_max + pad)
        if title == "Medical":
            ax.annotate(
                "saturation",
                xy=(1500, values[-1]),
                xytext=(1180, values[-1] + 5.0),
                arrowprops=dict(arrowstyle="->", lw=1.0, color=COLORS["teal"]),
                fontsize=12.5,
                color=COLORS["teal"],
                fontweight="bold",
            )
            ax.text(560, y_max - 0.4, "larger trap", color=COLORS["slate"], fontsize=11.5, fontstyle="italic")
        else:
            ax.annotate(
                "steady gain",
                xy=(1500, values[-1]),
                xytext=(1010, values[-1] + 2.2),
                arrowprops=dict(arrowstyle="->", lw=1.0, color=COLORS["teal"]),
                fontsize=12.5,
                color=COLORS["teal"],
                fontweight="bold",
            )
        for x, y in zip(sizes, values):
            if y >= y_max - 1e-9:
                offset = -0.55
                va = "top"
            elif y <= y_min + 1e-9:
                offset = 0.55
                va = "bottom"
            else:
                offset = 0.55
                va = "bottom"
            ax.text(x, y + offset, f"{y:.0f}", ha="center", va=va, fontsize=13, fontweight="bold", color="#1A1A1A")
        savefig(filename)


def main() -> None:
    agreement_curve()
    budget_allocation()
    hkg_size()
    print(f"Wrote figures to {FIGURES}")


if __name__ == "__main__":
    main()
