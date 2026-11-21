"""Plot a stage 4 matched-cost candidate ranking and energy margins."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

METRICS = ("schur_score", "frozen_drop_ha", "frozen_density_total_drop_ha", "scf_drop_ha")
LABELS = ("Schur\nscore", "Frozen KS\nspectrum", "Total energy at\nfrozen density", "Self-consistent\ntotal energy")
COLORS = {"Li_s08": "#147c8b", "H_s20": "#b35418"}


def plot(input_path, output_path):
    data = json.loads(input_path.read_text(encoding="utf-8"))
    rankings = data["rankings"]
    names = rankings[METRICS[0]]
    rows = {row["id"]: row for row in data["candidates"] if row["status"] == "ok"}
    if set(names) != set(rows) or not all(set(rankings[key]) == set(rows) for key in METRICS):
        raise ValueError("The four ranking lists must cover the same successful candidates.")

    layout = dict(width_ratios=[1.55, 1.0])
    fig, (rank_panel, margin_panel) = plt.subplots(1, 2, figsize=(11.4, 4.6),
                                                  gridspec_kw=layout, layout="constrained")
    fig.suptitle(f"LiH first-shell experiment | RKS/LDA | +{data['added_ao']} AO | grid {data['grid']['level']}",
                 fontsize=15, fontweight="bold", color="#243346")
    x = range(len(METRICS))
    for name in names:
        ranks = [1 + rankings[key].index(name) for key in METRICS]
        color = COLORS.get(name, "#8995a3")
        rank_panel.plot(x, ranks, "-o", color=color, lw=2.25, markersize=6)
        rank_panel.annotate(name, (3, ranks[-1]), xytext=(8, 0), textcoords="offset points",
                            va="center", color=color, fontweight="bold", fontsize=9)
    rank_panel.set(ylabel="Rank (1 = largest score or lowering)",
                   xlim=(-0.1, 3.8), ylim=(len(names) + 0.32, 0.68),
                   xticks=list(x), xticklabels=LABELS, yticks=list(range(1, len(names) + 1)))
    rank_panel.grid(axis="y", color="#e4e9ef")

    margin_metrics = METRICS[1:]
    margins = [1000 * (rows["H_s20"][key] - rows["Li_s08"][key]) for key in margin_metrics]
    positions = range(len(margins))
    bars = margin_panel.barh(positions, margins, color=["#477692", "#79a3b5", "#234d66"], height=0.55)
    margin_panel.bar_label(bars, labels=[f"{value:+.3f}" for value in margins], padding=4, fontsize=10)
    margin_panel.set(xlabel="Difference in lowering (mHa)",
                     yticks=list(positions), yticklabels=[label.replace("\n", " ") for label in LABELS[1:]])
    margin_panel.invert_yaxis()
    margin_panel.set_xlim(min(0.0, min(margins) * 1.4), max(0.05, max(margins) * 1.34))
    margin_panel.grid(axis="x", color="#e4e9ef")
    margin_panel.axvline(0, color="#8995a3", lw=0.8)
    for axis, title in ((rank_panel, "A   Candidate rank"), (margin_panel, "B   H_s20 versus Li_s08")):
        axis.set_axisbelow(True)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.spines["bottom"].set_color("#c7d0da")
        axis.tick_params(length=0, colors="#34475a", labelsize=9)
        axis.set_title(title, loc="left", color="#243346", fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plot(args.input, args.output)
