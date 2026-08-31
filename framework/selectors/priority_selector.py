from __future__ import annotations

import logging

from ..attack import Attack
from ..device import DeviceState
from ..selector import Selector

logger = logging.getLogger(__name__)


class PrioritySelector(Selector):
    """
    Picks the compatible attack with the lowest priority number (1 beats 2 beats 3).
    An attack with priority=0 is treated as unranked and ranks last.

    Tie-break within the same priority level: higher estimated success probability wins.
    """

    def select(self, attacks: list[Attack], state: DeviceState) -> Attack | None:
        compatible = [a for a in attacks if a.is_compatible(state)]
        logger.debug("%d/%d attacks compatible for priority selection", len(compatible), len(attacks))
        if not compatible:
            return None

        ranked = sorted(
            compatible,
            # unranked (0) goes to the back; within same priority higher prob wins
            key=lambda a: (a.priority if a.priority > 0 else float("inf"),
                           -a.estimated_success_probability),
        )
        winner = ranked[0]
        logger.debug("priority winner: '%s' (priority=%d)", winner.id, winner.priority)
        return winner
