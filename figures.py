"""Figures for the report (run after `python rule.py fit`).

  Figure 1: share of runs in which each signal exceeds its frozen threshold, by case
  Figure 2: example price paths, one run per case (plus the collusion run with messages blanked)

Usage:  python figures.py              (uses the test split; --split all for everything)
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agents import joint_max_price, nash_price
from signals import load

SIG = ["P", "C", "A", "D_int", "D_obs"]
SIG_LABEL = ["P\nparallel\nprices", "C\ntalk", "A\ncoalition\nadvantage", "D_int\ndependence\n(ablation)",
             "D_obs\ndependence\n(logs)"]
GROUPS = [("collusion", False, "Collusion"), ("collusion", True, "Collusion + cost shock"),
          ("common_incentives", True, "Common incentives\n(cost shock)"),
          ("talk_only", False, "Talk only"), ("talk_only", True, "Talk only + cost shock")]
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
SEQ = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})


def fig1(rows, th, out):
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    grid, ylabels = [], []
    for case, shock, label in GROUPS:
        sub = [r for r in rows if r["case"] == case and bool(r["shock_round"]) == shock]
        if not sub:
            continue
        grid.append([sum(float(r[s]) > th[s] for r in sub) / len(sub) for s in SIG])
        ylabels.append(f"{label}  (n={len(sub)})")
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=9,
                    color="white" if v > 0.55 else INK)
    ax.set_xticks(range(len(SIG)), SIG_LABEL, fontsize=8)
    ax.set_yticks(range(len(ylabels)), ylabels)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, len(SIG))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(ylabels))], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.axhline(1.5, color=INK, linewidth=1)
    ax.set_title("Share of runs where each signal exceeds its frozen threshold", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def fig2(rows, data, out):
    def pick(case, shock):
        sub = [r for r in rows if r["case"] == case and bool(r["shock_round"]) == shock]
        if case == "collusion":   # prefer a run with a cheat-and-punish episode
            sub.sort(key=lambda r: (float(r["D_obs"]) > 0, float(r["P"])), reverse=True)
        return sub[0] if sub else None

    picks = [("Collusion", pick("collusion", False)),
             ("Common incentives (cost shock)", pick("common_incentives", True)),
             ("Talk only + cost shock", pick("talk_only", True))]
    picks = [(t, r) for t, r in picks if r]
    fig, axes = plt.subplots(1, len(picks), figsize=(7.2, 2.6), sharey=True)
    for ax, (title, r) in zip(axes, picks):
        rounds = load(data / "runs" / f"{r['run_id']}.jsonl")
        t = [rd["firm_a"]["round"] for rd in rounds]
        costs = [rd["firm_a"]["cost"] for rd in rounds]
        ax.step(t, [nash_price(c) for c in costs], where="mid", color=MUTED, linestyle=":", linewidth=1.2,
                label="Competitive price")
        ax.step(t, [joint_max_price(c) for c in costs], where="mid", color=MUTED, linestyle="--", linewidth=1,
                label="Cartel price")
        if r["case"] == "collusion":
            ab = load(data / "runs" / f"{r['run_id']}_ablated.jsonl")
            ax.plot(t, [rd["firm_a"]["price"] for rd in ab], color="#9a9893", linewidth=2,
                    label="firm_a, messages blanked")
        ax.plot(t, [rd["firm_a"]["price"] for rd in rounds], color=BLUE, linewidth=2, marker="o", markersize=3,
                label="firm_a")
        ax.plot(t, [rd["firm_b"]["price"] for rd in rounds], color=ORANGE, linewidth=2, marker="o", markersize=3,
                label="firm_b")
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("Round")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Price")
    handles, labels = [], []
    for ax in axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h); labels.append(l)
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=7.5, frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--results", default="results")
    ap.add_argument("--split", default="test", choices=["test", "train", "all"])
    a = ap.parse_args()
    data, res = Path(a.data), Path(a.results)
    res.mkdir(exist_ok=True)
    th = json.loads((data / "frozen_rule.json").read_text(encoding="utf-8"))["thresholds"]
    rows = list(csv.DictReader(open(data / "signals.csv", encoding="utf-8")))
    if a.split != "all":
        rows = [r for r in rows if r["split"] == a.split]
    fig1(rows, th, res / "fig1_signal_heatmap.png")
    fig2(rows, data, res / "fig2_price_paths.png")
    print(f"Wrote {res / 'fig1_signal_heatmap.png'} and {res / 'fig2_price_paths.png'}")


if __name__ == "__main__":
    main()
