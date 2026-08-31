"""
Attack catalogue — all known attack definitions for the orchestrator.

priority field: lower int = higher priority; 0 = unranked (used by PrioritySelector).
compatible_models: empty list means compatible with any model.
"""
from framework.attack import Attack
from framework.stage import Stage

ATTACKS: list[Attack] = [
    Attack(
        id="bootrom_exploit",
        name="Bootrom Exploit",
        stages=[
            Stage(id="s0", name="USB handshake",        success_probability=0.95),
            Stage(id="s1", name="Bootrom overflow",     success_probability=0.85),
            Stage(id="s2", name="Privilege escalation", success_probability=0.90),
        ],
        compatible_models=["iPhone14,2", "iPhone14,3"],
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
        is_destructive=False,
        priority=1,
    ),
    Attack(
        id="jailbreak_unc0ver",
        name="unc0ver Jailbreak",
        stages=[
            Stage(id="s0", name="Kernel exploit",    success_probability=0.88),
            Stage(id="s1", name="Filesystem remount", success_probability=0.77),
        ],
        compatible_models=["iPhone13,4", "iPhone14,2"],
        min_ios=(15, 0),
        max_ios=(16, 9),
        min_battery=15,
        is_destructive=False,
        priority=2,
    ),
    Attack(
        id="bruteforce_pin",
        name="Bruteforce PIN",
        stages=[
            Stage(id="s0", name="Throttle bypass", success_probability=0.55),
        ],
        compatible_models=[],   # empty = any model
        min_ios=(15, 0),
        max_ios=(17, 9),
        min_battery=5,
        is_destructive=False,
        priority=2,
    ),
    Attack(
        id="checkm8",
        name="checkm8",
        stages=[
            Stage(id="s0", name="DFU mode trigger", success_probability=0.80),
            Stage(id="s1", name="Heap overflow",    success_probability=0.75),
        ],
        compatible_models=["iPhone14,2", "iPhone13,4"],
        min_ios=(15, 0),
        max_ios=(17, 9),
        min_battery=10,
        is_destructive=True,
        priority=3,
    ),
]
