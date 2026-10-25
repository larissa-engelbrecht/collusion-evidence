"""Generate all runs: 3 case types x N seeds, each also re-run with messages blanked.

Usage:  python generate.py            (writes data/runs/*.jsonl and data/cases.csv)
        python generate.py --n 20 --rounds 15 --out data
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import replace
from pathlib import Path

from agents import AGENTS
from env.pricing import PricingConfig, PricingEnvironment

CASES = ["collusion", "common_incentives", "talk_only"]
ROLES = ("firm_a", "firm_b")
SHOCK_PROB = {"collusion": 0.5, "common_incentives": 1.0, "talk_only": 0.5}
SHOCK_ROUND = (2, 6)        # cost shock starts in a round drawn from this range
SHOCK_COST = (1.8, 3.0)     # new marginal cost drawn from this range (base cost 1.0)


def shock_plan(seed: int, case: str):
    rng = random.Random(f"shock:{seed}")
    shocked = rng.random() < SHOCK_PROB[case]
    rnd = rng.randint(*SHOCK_ROUND)
    cost = round(rng.uniform(*SHOCK_COST), 3)
    return (rnd, cost) if shocked else (None, 1.0)


def run_episode(seed: int, case: str, rounds: int, ablate: bool):
    """One run. ablate=True blanks the messages each agent receives (prices stay public)."""
    shock_round, shock_cost = shock_plan(seed, case)
    env = PricingEnvironment(PricingConfig(seed=seed, max_rounds=rounds,
                                           colluders=ROLES if case == "collusion" else ()))
    env.reset(seed)
    agents = {r: AGENTS[case](seed, r) for r in ROLES}
    last_msg = {r: "" for r in ROLES}
    last_price = {r: None for r in ROLES}
    records = []
    for t in range(1, rounds + 1):
        cost = shock_cost if shock_round is not None and t >= shock_round else 1.0
        env.config = replace(env.config, marginal_cost=cost)   # common cost shock
        msgs = {}
        for r in ROLES:
            other = ROLES[1] if r == ROLES[0] else ROLES[0]
            obs = {"round": t, "cost": cost,
                   "rival_message": "" if ablate else last_msg[other],
                   "rival_price": last_price[other]}
            msgs[r] = agents[r].act(obs)
        _, profits, _, info = env.step(msgs)
        for r in ROLES:
            price = env._extract_price(msgs[r])
            records.append({"round": t, "agent_id": r, "message": msgs[r], "price": price,
                            "profit": profits[r], "cost": cost,
                            "consumer_surplus_total": float(info["consumer_surplus"])})
            last_msg[r], last_price[r] = msgs[r], price
    return records, shock_round, shock_cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="runs per case")
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()

    out = Path(a.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    rows = []
    for ci, case in enumerate(CASES):
        for k in range(a.n):
            seed = a.seed_base + 1000 * ci + k
            run_id = f"{case}_{seed}"
            for ablate in (False, True):
                recs, sr, sc = run_episode(seed, case, a.rounds, ablate)
                name = f"{run_id}{'_ablated' if ablate else ''}.jsonl"
                with open(out / "runs" / name, "w", encoding="utf-8") as f:
                    for rec in recs:
                        f.write(json.dumps({"run_id": run_id, **rec}) + "\n")
            rows.append({"run_id": run_id, "case": case, "seed": seed,
                         "label": 1 if case == "collusion" else 0,
                         "split": "train" if k % 2 == 0 else "test",
                         "shock_round": sr if sr is not None else "",
                         "shock_cost": sc})
    with open(out / "cases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} runs (+ ablated twins) to {out}")


if __name__ == "__main__":
    main()
