from __future__ import annotations

import logging

from ..attack import Attack
from ..device import DeviceState
from ..selector import Selector

logger = logging.getLogger(__name__)


class ProbabilitySelector(Selector):
    """
    Default selector: picks the compatible attack with the highest estimated
    success probability (product of stage probabilities).

    Tie-breaks: fewest stages wins, then non-destructive over destructive.
    """

    def select(self, attacks: list[Attack], state: DeviceState) -> Attack | None:
        compatible = [a for a in attacks if a.is_compatible(state)]
        logger.debug("%d/%d attacks compatible with %s / iOS %s",
                     len(compatible), len(attacks), state.model, state.ios_version)
        if not compatible:
            return None
        winner = max(
            compatible,
            key=lambda a: (
                a.estimated_success_probability,
                -len(a.stages),
                0 if a.is_destructive else 1,
            ),
        )
        logger.debug("winner: '%s' (p=%.2f)", winner.id, winner.estimated_success_probability)
        return winner
