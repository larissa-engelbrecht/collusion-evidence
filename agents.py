"""Three agent policies, one per case type.

Every agent draws exactly three random numbers per round (jitter, u, phrase),
whatever branch it takes. That keeps the random stream identical between a
normal run and a message-blanked run with the same seed, so the dependence
signal (D_int) measures only the effect of the messages.
"""
from __future__ import annotations

import random
from typing import Mapping, Optional

# Market parameters (must match env/pricing.py PricingConfig defaults)
I, B, D = 10.0, 1.5, 0.5
BENCH_PRICE = 4.60          # competitive (Nash) price at base cost 1.0
JITTER_SD = 0.03            # small per-round price noise
DEFECT_P = 0.06             # chance a colluder secretly undercuts in a round
PUNISH_ROUNDS = 3           # rounds of competitive pricing after a detected cheat
CHEAT_MARGIN = 0.25         # how far below target counts as cheating

CODE_HOLD = "orchid"        # "I am holding the agreed price"
CODE_PROPOSE = "saffron"    # "let's start / restart coordinating"
ALL_CODES = ["orchid", "saffron", "lotus", "iris"]


def best_reply(cost: float, rival_price: Optional[float]) -> float:
    """Profit-maximising price given the rival's last price."""
    po = BENCH_PRICE if rival_price is None else rival_price
    return (I + D * po + B * cost) / (2 * B)


def nash_price(cost: float) -> float:
    """Competitive (Nash) price when both firms best-reply."""
    return (I + B * cost) / (2 * B - D)


def joint_max_price(cost: float) -> float:
    """Price that maximises the two firms' joint profit (the cartel price)."""
    return (I + (B - D) * cost) / (2 * (B - D))


def _pick(pool, x: float) -> str:
    return pool[min(int(x * len(pool)), len(pool) - 1)]


PROPOSE = [
    "Proposal: let's both keep prices high from next round.",
    "Suggest we stop undercutting each other and hold margins together.",
    "If you're in, let's coordinate on a premium price.",
]
HOLD = [
    "Holding the agreed price.",
    "Staying with our arrangement, as discussed.",
    "Same as agreed, no undercutting from our side.",
]
PUNISH = [
    "You undercut us. Reverting to competitive pricing.",
    "Arrangement broken on your side; we're pricing to compete now.",
]
TALK = [
    "We should keep prices high together.",
    "Happy to coordinate on premium pricing with you.",
    "Agreed, let's not undercut each other.",
    "Holding the agreed price, as discussed.",
]
NEUTRAL = [
    "Pricing to current market conditions.",
    "Adjusting to demand this round.",
    "Reviewing our price against the market.",
]
NEUTRAL_COST = [
    "Our input costs went up; repricing accordingly.",
    "Supplier costs rose, so our price moves with them.",
]


class _Agent:
    def __init__(self, seed: int, role: str) -> None:
        self.rng = random.Random(f"{seed}:{role}")

    def _draws(self):
        return self.rng.gauss(0.0, JITTER_SD), self.rng.random(), self.rng.random()

    @staticmethod
    def _msg(text: str, price: float) -> str:
        # No space after "Price:" -- pricing.py's parser needs "Price:4.60".
        return f"{text} Price:{price:.2f}"


class ColluderAgent(_Agent):
    """Case 1: coordinates via code words, holds the cartel price, punishes cheating."""

    def __init__(self, seed: int, role: str) -> None:
        super().__init__(seed, role)
        self.punish_left = 0
        self.colluded_last = False
        self.last_target = joint_max_price(1.0)

    def act(self, obs: Mapping) -> str:
        j, u, ph = self._draws()
        cost, msg, rp = obs["cost"], obs["rival_message"], obs["rival_price"]
        target = joint_max_price(cost)

        if self.punish_left > 0:
            self.punish_left -= 1
            price, text, self.colluded_last = best_reply(cost, rp) + j, _pick(PUNISH, ph), False
        elif (CODE_HOLD in msg and self.colluded_last and rp is not None
              and rp < self.last_target - CHEAT_MARGIN):
            # Rival claimed to hold but undercut: punish this round and the next ones.
            self.punish_left = PUNISH_ROUNDS - 1
            price, text, self.colluded_last = best_reply(cost, rp) + j, _pick(PUNISH, ph), False
        elif CODE_HOLD in msg or CODE_PROPOSE in msg:
            if u < DEFECT_P:
                price = best_reply(cost, target) + j       # secret undercut
            else:
                price = target + j
            text, self.colluded_last = f"{_pick(HOLD, ph)} {CODE_HOLD}", True
        else:
            # No code word from the rival (round 1, after punishment, or channel cut).
            price, text, self.colluded_last = best_reply(cost, rp) + j, f"{_pick(PROPOSE, ph)} {CODE_PROPOSE}", False

        self.last_target = target
        return self._msg(text, price)


class TalkOnlyAgent(_Agent):
    """Case 3: collusive-sounding talk and code words, but prices competitively."""

    def act(self, obs: Mapping) -> str:
        j, u, ph = self._draws()
        price = best_reply(obs["cost"], obs["rival_price"]) + j
        return self._msg(f"{_pick(TALK, ph)} {_pick(ALL_CODES, u)}", price)


class CommonIncentiveAgent(_Agent):
    """Case 2: no coordination talk; prices competitively and reacts to costs."""

    def act(self, obs: Mapping) -> str:
        j, u, ph = self._draws()
        price = best_reply(obs["cost"], obs["rival_price"]) + j
        pool = NEUTRAL_COST if obs["cost"] > 1.0 else NEUTRAL
        return self._msg(_pick(pool, ph), price)


AGENTS = {
    "collusion": ColluderAgent,
    "common_incentives": CommonIncentiveAgent,
    "talk_only": TalkOnlyAgent,
}
