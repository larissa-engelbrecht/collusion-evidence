# What counts as evidence of collusion? Plus factors for AI agents

Apart Research AI Collusion Sprint, October 2026, question 2.3.

Tests a decision rule based on the antitrust **plus-factors doctrine**: parallel
conduct alone is never enough, so a collusion flag needs parallel pricing **plus**
a behavioural factor. Evaluated on three case types built to fool single signals:
real collusion, common incentives (a shared cost shock), and talk that never
changes behaviour.

## Run it (Windows PowerShell, from this folder)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python generate.py          # 60 runs + 60 message-blanked twins -> data/
$env:ANTHROPIC_API_KEY="..."
python judge.py --limit 2   # try 2 calls first, check data/judge_cache.json
python judge.py             # the rest (60 calls total, cached)
python signals.py           # -> data/signals.csv
python rule.py fit          # thresholds from TRAIN only -> data/frozen_rule.json

git add -A
git commit -m "Freeze decision rule before looking at test split"
git tag rule-frozen

python rule.py test         # -> results/test_results.md
python figures.py           # -> results/fig1_signal_heatmap.png, fig2_price_paths.png
```

Without an API key, skip `judge.py`: `signals.py` falls back to a keyword
baseline for C and says so. Everything is seeded and deterministic.

## Files

| File | What it does |
|---|---|
| `env/pricing.py` | Market, copied unchanged from ColludeBench |
| `env/base.py` | Minimal base classes so `pricing.py` runs standalone |
| `agents.py` | The three policies: colluder, common incentives, talk only |
| `generate.py` | Runs every case, normal and with messages blanked |
| `judge.py` | LLM judge for the talk signal C (prices removed first) |
| `signals.py` | Computes P, C, A, D_int, D_obs for each run |
| `rule.py` | Fits thresholds on train, freezes, scores test |
| `figures.py` | Figures 1 and 2 |

## Credit

`env/pricing.py` is from ColludeBench / Audit the Whisper
(https://github.com/Ostailor/Steganographic_Collusion), MIT License; see
`env/LICENSE-ColludeBench`.
