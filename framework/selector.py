from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .attack import Attack
from .device import DeviceState

logger = logging.getLogger(__name__)


class Selector(ABC):
    """Strategy interface for choosing which attack to run."""

    @abstractmethod
    def select(self, attacks: list[Attack], state: DeviceState) -> Attack | None: ...


class ProbabilitySelector(Selector):
    """
    Default selector: filters compatible attacks, then picks the one with the
    highest estimated success probability (product of stage probabilities).
    Ties are broken by fewest stages (simpler attack preferred).

    Non-destructive attacks are preferred over destructive ones at equal rank
    to avoid side effects when a safer option exists.
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
