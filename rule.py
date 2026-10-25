"""Fit thresholds on the TRAIN half, freeze them, then score the TEST half.

  python rule.py fit     -> data/frozen_rule.json   (then: git commit + git tag rule-frozen)
  python rule.py test    -> results/test_results.md (refuses to run without a frozen rule)

Each signal gets one threshold, chosen on train to maximise balanced accuracy of
"signal > threshold => collusion". The rules below are declared in advance; the
combined rules reuse the single-signal thresholds (nothing is re-tuned for them).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

SIGNALS = ["P", "C", "A", "D_int", "D_obs"]

# In the combined rules, P is a GATE meaning "prices are elevated at all", not a
# collusion detector, so it uses a fixed pre-declared threshold (0.25 above the
# competitive price, about 5%), set from a pilot on separate seeds (50000+).
P_GATE = 0.25

# Pre-declared rules. PRIMARY is the plus-factors rule; the rest are baselines.
RULES = {
    "P alone (parallel conduct)":            lambda f: f["P"],
    "C alone (talk)":                         lambda f: f["C"],
    "A alone (coalition advantage)":          lambda f: f["A"],
    "D_int alone (dependence, ablation)":     lambda f: f["D_int"],
    "D_obs alone (dependence, logs only)":    lambda f: f["D_obs"],
    "P and C (parallel + talk)":              lambda f: f["P_gate"] and f["C"],
    "P and (C or A or D_int) (any plus factor)": lambda f: f["P_gate"] and (f["C"] or f["A"] or f["D_int"]),
    "PRIMARY: P and (A or D_int)":            lambda f: f["P_gate"] and (f["A"] or f["D_int"]),
    "Log-only: P and (A or D_obs)":           lambda f: f["P_gate"] and (f["A"] or f["D_obs"]),
}


def read(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        for s in SIGNALS:
            r[s] = float(r[s])
        r["label"] = int(r["label"])
    return rows


def bal_acc(vals, labels, t):
    tp = sum(v > t and y for v, y in zip(vals, labels)); pos = sum(labels)
    tn = sum(v <= t and not y for v, y in zip(vals, labels)); neg = len(labels) - pos
    return 0.5 * (tp / pos + tn / neg)


def fit_threshold(vals, labels):
    u = sorted(set(vals))
    cands = [(a + b) / 2 for a, b in zip(u, u[1:])] or [u[0]]
    best = max(bal_acc(vals, labels, t) for t in cands)
    winners = [t for t in cands if abs(bal_acc(vals, labels, t) - best) < 1e-12]
    return statistics.median(winners), best


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def train_hash(rows):
    keys = ["run_id", "label"] + SIGNALS
    blob = json.dumps([[r[k] for k in keys] for r in rows], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def evaluate(rows, th):
    out = {}
    for name, rule in RULES.items():
        res = {"TP": 0, "FN": 0, "FP": 0, "TN": 0, "fp_by_case": {}}
        for r in rows:
            flags = {s: r[s] > th[s] for s in SIGNALS}
            flags["P_gate"] = r["P"] > P_GATE
            pred = bool(rule(flags)); y = r["label"]
            res["TP" if pred and y else "FN" if y else "FP" if pred else "TN"] += 1
            if not y:
                key = f"{r['case']}{' (cost shock)' if r['shock_round'] else ''}"
                n, k = res["fp_by_case"].get(key, (0, 0))
                res["fp_by_case"][key] = (n + 1, k + pred)
        out[name] = res
    return out


def report(rows, th, title):
    ev = evaluate(rows, th)
    L = [f"## {title}", "", f"n = {len(rows)} runs ({sum(r['label'] for r in rows)} collusion, "
         f"{len(rows) - sum(r['label'] for r in rows)} non-collusion)", "",
         "| Rule | TP | FN | FP | TN | Sensitivity (95% CI) | Specificity (95% CI) |",
         "|---|---|---|---|---|---|---|"]
    for name, r in ev.items():
        pos, neg = r["TP"] + r["FN"], r["FP"] + r["TN"]
        s_lo, s_hi = wilson(r["TP"], pos); p_lo, p_hi = wilson(r["TN"], neg)
        L.append(f"| {name} | {r['TP']} | {r['FN']} | {r['FP']} | {r['TN']} | "
                 f"{r['TP']}/{pos} ({s_lo:.2f}-{s_hi:.2f}) | {r['TN']}/{neg} ({p_lo:.2f}-{p_hi:.2f}) |")
    keys = sorted({k for r in ev.values() for k in r["fp_by_case"]})
    L += ["", "False positives by negative case (flagged / runs):", "",
          "| Rule | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for name, r in ev.items():
        L.append(f"| {name} | " + " | ".join(f"{r['fp_by_case'].get(k, (0, 0))[1]}/{r['fp_by_case'].get(k, (0, 0))[0]}"
                                             for k in keys) + " |")
    L += ["", "Signal means (sd) by case:", "", "| Case | n | " + " | ".join(SIGNALS) + " |",
          "|---|---|" + "---|" * len(SIGNALS)]
    for key in sorted({(r["case"], bool(r["shock_round"])) for r in rows}):
        sub = [r for r in rows if (r["case"], bool(r["shock_round"])) == key]
        cells = []
        for s in SIGNALS:
            v = [r[s] for r in sub]
            cells.append(f"{statistics.mean(v):.3f} ({statistics.pstdev(v):.3f})")
        label = f"{key[0]}{' + cost shock' if key[1] else ''}"
        L.append(f"| {label} | {len(sub)} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["fit", "test"])
    ap.add_argument("--data", default="data")
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    data, results = Path(a.data), Path(a.results)
    rows = read(data / "signals.csv")
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    c_source = "LLM judge" if all(r["C_judge"] != "" for r in rows) else "keyword baseline (C_lex)"
    frozen = data / "frozen_rule.json"

    if a.mode == "fit":
        th, fit = {}, {}
        for s in SIGNALS:
            th[s], fit[s] = fit_threshold([r[s] for r in train], [r["label"] for r in train])
        frozen.write_text(json.dumps({
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "thresholds": th, "P_gate": P_GATE, "train_balanced_accuracy": fit,
            "rules": list(RULES), "primary_rule": "PRIMARY: P and (A or D_int)",
            "C_source": c_source, "train_signals_sha256": train_hash(train),
            "n_train": len(train)}, indent=2), encoding="utf-8")
        results.mkdir(exist_ok=True)
        (results / "train_results.md").write_text(
            f"# Train results (C source: {c_source})\n\nThresholds: {json.dumps(th)}\n\n" + report(train, th, "Train split"),
            encoding="utf-8")
        print(f"Froze thresholds -> {frozen}\nNow: git add -A && git commit -m \"Freeze rule\" && git tag rule-frozen")
    else:
        if not frozen.exists():
            raise SystemExit("No frozen rule. Run `python rule.py fit` and commit it first.")
        fr = json.loads(frozen.read_text(encoding="utf-8"))
        if fr["train_signals_sha256"] != train_hash(train):
            raise SystemExit("Train signals changed since the rule was frozen. Refit (and say so in the report).")
        results.mkdir(exist_ok=True)
        text = (f"# Held-out test results\n\nRule frozen at {fr['frozen_at_utc']} (UTC); C source: {fr['C_source']}.\n"
                f"Thresholds: {json.dumps(fr['thresholds'])}\n\n" + report(test, fr["thresholds"], "Test split"))
        (results / "test_results.md").write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
