# Multi-Stage Attack Orchestrator

A framework for selecting, running, and managing multi-stage attacks against mobile devices, together with a C-based device simulator and a full test suite.

---

## Quick start

```bash
# Build the C simulator
make -C simulator

# Install Python dependencies
pip install pytest

# Run all tests (unit + integration)
pytest tests/ -v
```

---

## Architecture

```
framework/          Core Python library (no I/O of its own)
  device.py         Device ABC + DeviceState dataclass + error types
  stage.py          Stage & StageResult dataclasses
  attack.py         Attack dataclass + compatibility check
  selector.py       Selector ABC + ProbabilitySelector (default)
  orchestrator.py   Orchestrator — selects + runs an attack
  extractor.py      Extractor — reads files after a successful attack

client/             Concrete Device implementations
  fake_device.py    In-memory FakeDevice (fast unit tests, no subprocess)
  tcp_client.py     SimulatedDeviceClient — speaks the TCP protocol

simulator/
  simulator.c       C TCP server that behaves like a locked mobile device
  Makefile

tests/
  conftest.py       Shared fixtures: FakeDevice, attack registry, C subprocess
  test_selector.py  Unit — selection logic
  test_orchestrator.py  Unit — run/failure/connection-drop logic
  test_extractor.py     Unit — file extraction
  test_integration.py   Integration — real C simulator over TCP
```

The `Device` ABC is the central seam. `framework/` codes against it; `client/` implements it. This means the unit tests never touch the network and the integration tests require no mocking.

---

## Design decisions

### 1. Attack selection strategy

**The question:** several attacks may be compatible with the same device. Which one runs?

**Alternatives I considered:**

| Strategy | Pros | Cons |
|---|---|---|
| Priority table (fixed order) | Auditable, deterministic | Requires manual maintenance as new attacks are added |
| Highest combined success probability | Principled, data-driven | Ignores cost/time/destructiveness |
| Weighted score (prob + time + destructiveness) | Most realistic | Requires calibrated weights |

**What I implemented:** `ProbabilitySelector` — filters compatible attacks, then picks by:
1. Highest estimated success probability (product of all stage probabilities)
2. Tie-break: fewest stages (simpler attack preferred)
3. Second tie-break: non-destructive over destructive

The selector is a pluggable strategy (`Selector` ABC), so a `PrioritySelector` or `WeightedSelector` can be swapped in with one constructor argument. The default gives a concrete, explainable answer and shows extensibility.

**Why probability over a priority table:** A table would require knowing upfront which attack to prefer for each device family. Probability makes the ranking emerge from the attack definitions themselves, which scales better as the attack catalogue grows.

**Why non-destructive preferred at equal rank:** On a real device, a destructive attack that wipes on failure raises the stakes considerably. All else being equal, try the safer path first.

### 2. Stage failure semantics

**The question:** what happens when a stage fails?

**Decision:** abort the chain immediately on the first stage failure. No retry, no automatic fallback to a different attack.

**Why:** a failed stage on a real device may have mutated device state — for example, an incorrect unlock attempt increments a wipe counter, or a partial flash puts the device in DFU mode. Silently retrying a different attack after that is dangerous. The `Orchestrator` returns an `AttackOutcome` that tells the caller exactly which stage failed and why; the caller can decide whether a retry or fallback is safe given that information.

This is documented explicitly in `Orchestrator`'s docstring.

### 3. No auto-fallback

A deliberate consequence of the failure policy above: the orchestrator tries the top-ranked attack and returns. It does not loop through the attack list on failure. This keeps the `Orchestrator` stateless between calls and puts the retry/escalation policy in the caller, where device-specific context lives.

### 4. Extraction as a separate layer

Extraction (`Extractor`) is built on top of the `Device` interface, not baked into the attack. The attack gives you a working `Device` connection; the `Extractor` uses it. This means:
- An attack doesn't need to know what will be extracted.
- `extract_all` works the same way whether the device is a `FakeDevice` or `SimulatedDeviceClient`.
- The protocol must support `LIST` + `READ`, not just `READ` — a constraint I designed into the simulator from the start.

### 5. Simulator design choices

**Single-threaded accept loop:** The simulator handles one connection at a time. Real device interactions are inherently sequential (one Python process, one device, one attack at a time), so this is correct, simpler, and easier to reason about for connection-drop tests.

**Scripted failure modes via CLI flags:** `--fail-stage N` and `--drop-after-stage N` make integration test scenarios reproducible without relying on probability. Tests that need specific failure points pass the right flag; tests that need success use the default simulator.

**Hardcoded in-memory file tree:** The default simulator has a small fixed set of fake files so `extract_all` tests don't need to set up a real directory. The `--sim-files <dir>` flag exists for more realistic scenarios.

---

## Protocol

Text-based, newline-delimited commands. Responses are single-line JSON. Binary file content uses a length-prefix envelope after the JSON header line.

| Client sends | Server responds |
|---|---|
| `GET_STATE\n` | `{"battery":80,"ios_version":"16.5","model":"iPhone14,2","is_locked":true}\n` |
| `RUN_STAGE <attack_id> <stage_idx>\n` | `{"status":"SUCCESS"}\n` or `{"status":"FAIL","reason":"..."}\n` |
| `LIST <path>\n` | `{"files":["contacts.db","media","logs"]}\n` |
| `READ <path>\n` | `{"size":N}\n` followed by exactly N bytes (no trailing newline) |
| `QUIT\n` | server closes the connection |

**Why text/JSON over binary:** Easier to debug with `nc` or `telnet`, easier to document, no endianness concerns. File content uses a binary envelope because file data is arbitrary bytes.

**Simulator CLI flags:**

| Flag | Description |
|---|---|
| `--port <n>` | TCP port (default 9000) |
| `--model <str>` | Device model string |
| `--ios <str>` | iOS version string |
| `--battery <n>` | Battery percentage |
| `--locked <0\|1>` | is_locked flag |
| `--fail-stage <n>` | Force stage index n to return FAIL |
| `--drop-after-stage <n>` | Drop TCP connection after completing stage n |
| `--sim-files <dir>` | Serve real files from this directory root |

---

## Running the simulator manually

```bash
# Default configuration
./simulator/simulator

# iPhone 15 on iOS 17, low battery
./simulator/simulator --model "iPhone15,2" --ios "17.0" --battery 12

# Fail every stage 1
./simulator/simulator --fail-stage 1

# Drop connection after stage 0 completes
./simulator/simulator --drop-after-stage 0
```

Connect with:

```bash
nc localhost 9000
GET_STATE
RUN_STAGE my_attack 0
LIST /
READ /contacts.db
QUIT
```

---

## Test coverage

| File | What it tests | Device |
|---|---|---|
| `test_selector.py` | Selection logic, tie-breaking, compatibility filtering | None (pure logic) |
| `test_orchestrator.py` | Success path, stage failure at each position, connection drop, no-attack case | FakeDevice |
| `test_extractor.py` | `read()`, `extract_all()`, subtree extraction, empty device | FakeDevice |
| `test_integration.py` | Full round-trips, scripted failures, connection drop, extract_all | Real C binary |

The integration tests compile the binary once per session and spin up a fresh subprocess per test with a random port, so they can run in parallel without port conflicts.

---

## What I'd add with more time

- **Retry logic per stage** as an optional Attack-level parameter (e.g. `max_retries=2`), only safe to use when the stage is marked idempotent.
- **Weighted selector** combining probability, estimated duration, and destructiveness with tunable weights.
- **Concurrent multi-device orchestration** — the framework is already stateless per device, so wrapping `Orchestrator.run()` in a `ThreadPoolExecutor` is straightforward.
- **Structured logging** throughout the orchestration loop so failed chains produce a complete audit trail.
