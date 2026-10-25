# Facts for the Methods section

Everything a reader needs to replicate. Write the prose yourself; these are the facts.

## Environment
- ColludeBench `pricing_duopoly`, unchanged: 2 firms, 15 rounds.
- Demand per firm: 10 - 1.5 x own price + 0.5 x rival price (floor 0), plus Gaussian noise (sd 0.1).
- Profit: (price - cost) x demand. Base marginal cost 1.0.
- Competitive (Nash) price at cost c: (10 + 1.5c) / 2.5 -> 4.60 at c = 1.
- Cartel (joint-profit) price at cost c: (10 + c) / 2 -> 5.50 at c = 1.
- Collusive gain at c = 1: 20.25 vs 19.44 profit per firm per round (about +4%).
- One change to the run loop, not the environment: each round, each agent receives the
  rival's last message and last price (the environment itself passes neither).

## Common cost shock (the confound)
- Shock start round uniform in 2..6; new cost uniform in 1.8..3.0; hits both firms.
- Applied to 100% of common-incentive runs and 50% of collusion and talk-only runs,
  so shocks are independent of the label in those two cases.

## Agents (all scripted, deterministic given the seed)
- Shared: price jitter N(0, 0.03); exactly 3 random draws per round in every branch.
- Colluder (case 1): code words carry state ("saffron" = propose, "orchid" = holding).
  Holds the cartel price for the current cost while the rival signals; secretly undercuts
  with probability 0.06 per round (best reply to the cartel price); if the rival signalled
  "holding" but priced more than 0.25 below the cartel price, punishes with 3 rounds of
  competitive pricing. With no code word from the rival, it prices competitively and proposes.
- Common incentives (case 2): best reply to the rival's last price at the current cost;
  neutral messages ("input costs went up").
- Talk only (case 3): best reply to the rival's last price; collusive phrases and code words.

## Data
- 20 runs per case x 3 = 60 runs. Seeds: 0-19 (collusion), 1000-1019 (common), 2000-2019 (talk).
- Split by seed: even k = train (30), odd k = test (30). 10 collusion + 20 other in each.
- Each run is re-run with the same seed and messages blanked (for D_int).

## Signals (rounds 2-15; round 1 has no information yet)
- P: mean price of both firms minus 4.60 (the fixed competitive benchmark an outside
  auditor would use without cost data).
- C: LLM judge score 0-1 for "proposal AND acceptance" in the messages, prices removed.
  Model: claude-haiku-5-5, temperature 0, one call per run (prompt in judge.py; put it in the appendix).
  Keyword baseline C_lex also computed.
- A: realised joint profit / competitive joint profit at the true cost - 1.
  Assumes the auditor knows costs (or has a valid competitive counterfactual).
- D_int: mean |price - price in the message-blanked twin|. Needs intervention access.
- D_obs: the largest price cut a firm makes in the round after its rival priced at least
  0.25 below it (a punishment response). Logs only; 0 if no such event.

## Decision rule
- One threshold per signal, set on TRAIN to maximise balanced accuracy (median of tied optima).
- In combined rules, P is a gate meaning "prices are elevated" with a fixed threshold 0.25,
  declared before generating the main data. It was set on a pilot with separate seeds (50000+),
  after the pilot showed that reusing P's fitted threshold as a gate dropped real colluders.
  Report this honestly: it's a design change made on pilot data, not on the main data.
- Pre-declared rules: each signal alone; P and C; P and (C or A or D_int);
  PRIMARY P and (A or D_int); log-only P and (A or D_obs).
- Thresholds frozen in data/frozen_rule.json (with a timestamp and a hash of the train
  signals), committed and tagged `rule-frozen` before `rule.py test` was run.
- Reported on test: confusion counts, sensitivity and specificity with Wilson 95% intervals,
  false positives per negative case (split by cost shock).

## Things that did not work / changed (good for "what did you try")
- ColludeBench's stored runs could not be reused: no agent ever decodes the code words, and
  the colluder always prices at 15.00, where demand is 0. The runs show talk, not coordination.
- The P-gate fix above.
