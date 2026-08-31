from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .attack import Attack
from .device import Device, DeviceState, ConnectionLostError, DeviceError
from .selector import Selector
from .selectors import ProbabilitySelector

logger = logging.getLogger(__name__)


@dataclass
class AttackOutcome:
    attack: Attack | None
    success: bool
    failed_stage: int | None = None
    error: Exception | None = None


class Orchestrator:
    """
    Selects and executes an attack against a device.

    Failure policy: the run aborts on the first stage failure and does NOT
    automatically fall back to another attack. A failed stage may have mutated
    device state (e.g. incremented a wipe counter), so silently retrying a
    different attack is unsafe. The caller receives the outcome and decides.
    """

    def __init__(
        self,
        device: Device,
        attacks: list[Attack],
        selector: Selector | None = None,
    ) -> None:
        self.device = device
        self.attacks = attacks
        self.selector = selector or ProbabilitySelector()

    def run(self, state: DeviceState | None = None) -> AttackOutcome:
        if state is None:
            state = self.device.get_state()
            logger.info("device state: model=%s ios=%s battery=%d%%",
                        state.model, state.ios_version, state.battery_level)

        attack = self.selector.select(self.attacks, state)
        if attack is None:
            logger.warning("no compatible attack found for this device state")
            return AttackOutcome(
                attack=None,
                success=False,
                error=DeviceError("no compatible attack found for this device state"),
            )

        logger.info("selected attack '%s' (p=%.2f, %d stage%s)",
                    attack.name, attack.estimated_success_probability,
                    len(attack.stages), "s" if len(attack.stages) != 1 else "")

        for i, stage in enumerate(attack.stages):
            logger.info("  stage %d '%s' — running...", i, stage.name)
            try:
                result = self.device.run_stage(attack.id, i)
            except ConnectionLostError as exc:
                logger.error("  stage %d '%s' — connection lost: %s", i, stage.name, exc)
                return AttackOutcome(attack=attack, success=False, failed_stage=i, error=exc)

            if not result.success:
                logger.warning("  stage %d '%s' — FAILED%s", i, stage.name,
                               f": {result.reason}" if result.reason else "")
                return AttackOutcome(attack=attack, success=False, failed_stage=i)

            logger.info("  stage %d '%s' — SUCCESS", i, stage.name)

        logger.info("attack '%s' completed successfully", attack.name)
        return AttackOutcome(attack=attack, success=True)
