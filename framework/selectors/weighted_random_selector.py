from __future__ import annotations

import logging
import random

from ..attack import Attack
from ..device import DeviceState
from ..selector import Selector

logger = logging.getLogger(__name__)


class WeightedRandomSelector(Selector):
    """
    Randomly samples one compatible attack, weighted by estimated success probability.

    Higher-probability attacks are more likely to be chosen but not guaranteed —
    useful for adding non-determinism to attack campaigns.
    """

    def select(self, attacks: list[Attack], state: DeviceState) -> Attack | None:
        compatible = [a for a in attacks if a.is_compatible(state)]
        logger.debug("%d/%d attacks compatible for weighted selection", len(compatible), len(attacks))
        if not compatible:
            return None
        weights = [a.estimated_success_probability for a in compatible]
        winner = random.choices(compatible, weights=weights, k=1)[0]
        logger.debug("weighted random winner: '%s'", winner.id)
        return winner
