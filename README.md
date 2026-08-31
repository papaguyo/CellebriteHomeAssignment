# Multi-Stage Attack Orchestrator

A framework for selecting and running multi-stage unlock attacks
against mobile devices, plus a C device simulator to run them
against and a test suite covering both.

---

## Quick start

On a fresh clone a virtualenv will be created, dependencies will be installed and the C simulator will be built. No other setup required.

```bash
./start.sh
```

```bash
./demo_all.sh      # runs happy path, stage failure, and connection drop back to back
```

```bash
./interactive.sh   # arrow-key menu: choose selector strategy, pick attack, or run tests
```

Some addition tags.

```bash
./start.sh --fail-stage 1        # force stage 1 to fail
./start.sh --drop-after-stage 0  # simulate the connection dying mid-chain
./start.sh --probabilistic       # roll against each stage's success_probability instead of forcing success
./start.sh --selector priority   # use the priority-based selector instead of the default
```

**Tests:**

```bash
pytest tests/ -v                 # everything
pytest tests/test_selector.py tests/test_orchestrator.py tests/test_extractor.py -v   # unit only, no simulator needed
```

---

## Architecture

```
framework/          Core library, no I/O of its own
  device.py          Device ABC, DeviceState, error types
  stage.py           Stage & StageResult
  attack.py           Attack dataclass + compatibility check
  selector.py         Selector ABC (strategy interface)
  selectors/
    probability_selector.py      Highest estimated success probability (default)
    priority_selector.py         Fixed priority ranking per attack
    weighted_random_selector.py  Random, weighted by probability
  orchestrator.py     Picks an attack, runs it
  extractor.py        Reads files off a device once an attack succeeds

attacks.py           The attack catalogue

client/
  fake_device.py       In-memory Device, used for unit tests
  tcp_client.py         Talks the real protocol to the C simulator

simulator/
  simulator.c           C TCP server, acts like a locked device
  Makefile

tests/
  conftest.py
  test_selector.py, test_orchestrator.py, test_extractor.py   # unit
  test_integration.py                                          # against the real C binary

start.sh / interactive.sh / demo_all.sh   # entry points (create venv, build sim, run)
```

The `Device` ABC is the whole point of this layout —
`framework/` only ever talks to that interface. Unit tests run
against `FakeDevice` with zero mocking, and integration tests run
the exact same code against a real socket.

---

## Design decisions

**Picking an attack.** Several attacks can be compatible with the
same device, so something has to rank them. I went back and forth
between a hand-maintained priority table and something derived from
the attack data itself, and landed on the latter.

`ProbabilitySelector` ranks compatible attacks by estimated success
probability (product of stage probabilities), breaks ties by fewest
stages, then prefers non-destructive attacks over destructive ones.
A stage that wipes the device on failure raises the stakes enough
that, all else equal, it should go last.

A table would work too and would be more auditable, but it means
someone has to remember to update it every time a new attack gets
added, that felt like the wrong default.
I kept it pluggable via strategy design pattern
(`Selector` is an ABC) and also implemented `PrioritySelector` and
`WeightedRandomSelector`, since the "right" answer depends on what
the operator cares about more, probability or auditability, and
that's not something the framework should force.

**Stage failure.** The chain aborts on the first failed stage - no
retry, no automatic fallback to another attack. A failed stage can
leave the device in a different state than it started in (a wrong
unlock attempt can bump a wipe counter, a partial flash can drop the
device into DFU mode), so quietly trying something else afterward
isn't safe without knowing what actually happened.

`Orchestrator.run()` returns which stage failed and why, and leaves
it to the caller to decide whether to retry, escalate, or stop,
that decision needs device-specific context the orchestrator
doesn't have.

**Extraction is separate from attacks.** `Extractor` just uses a
working `Device` connection, it doesn't know or care how that
connection was obtained. This is also why the protocol has `LIST`
in addition to `READ`. `extract_all` needs to walk the filesystem,
not just read a path it's handed.

**Simulator is single-threaded, one connection at a time.** Real
attacks are inherently sequential. one process one device, so
there's no reason to complicate the simulator with concurrency, and
it makes the connection drop tests much easier to reason about.

**Failure modes are scripted via flags**, not left to chance:
`--fail-stage N` and `--drop-after-stage N` make integration tests
deterministic. Random probability rolls are also supported
(`--probabilistic`) for the demo, but the tests don't rely on them.

---

## Protocol

Newline-delimited text commands, single-line JSON responses. File
bytes are sent raw after a `{"size": N}` header rather than
base64-encoded, no reason to inflate every extraction by 33% for
no benefit.

| Client sends | Server responds |
|---|---|
| `GET_STATE\n` | `{"battery":80,"ios_version":"16.5","model":"iPhone14,2","is_locked":true}\n` |
| `RUN_STAGE <attack_id> <stage_idx>\n` | `{"status":"SUCCESS"}\n` or `{"status":"FAIL","reason":"..."}\n` |
| `LIST <path>\n` | `{"files":["contacts.db","media","logs"]}\n` |
| `READ <path>\n` | `{"size":N}\n` then exactly N raw bytes |
| `QUIT\n` | connection closes |

Text/JSON over a custom binary format mostly because I wanted to
poke at it with `nc` while debugging. that turned out to be worth
it.

**Simulator flags:** `--port`, `--model`, `--ios`, `--battery`, `--locked`, `--fail-stage`, `--drop-after-stage`, `--sim-files <dir>` (serve a real directory instead of the built-in fake files).

```bash
./simulator/simulator --model "iPhone15,2" --ios "17.0" --battery 12
./simulator/simulator --drop-after-stage 0

nc localhost 9000
GET_STATE
RUN_STAGE my_attack 0
LIST /
READ /contacts.db
QUIT
```

---

## Test coverage

| File | Covers | Against |
|---|---|---|
| `test_selector.py` | Ranking, tie-breaking, compatibility filtering | pure logic |
| `test_orchestrator.py` | Success path, failure at each stage, connection drop, no compatible attack | `FakeDevice` |
| `test_extractor.py` | `read()`, `extract_all()`, subtree extraction, empty device | `FakeDevice` |
| `test_integration.py` | Same scenarios as above, but for real: full round trip, scripted failures, connection drop mid-chain, `extract_all` over the wire | real C binary |

Integration tests build the binary once per session and spawn a fresh subprocess on a random port per test, so they can run in parallel.

---

## What I'd add with more time

* Retry logic per stage, but only for stages explicitly marked
  idempotent. Anything that touches a wipe counter shouldn't get
  auto-retried.

* Running attacks against a fleet of devices at once. The framework
  is already stateless per device, so wrapping `Orchestrator.run()`
  in a thread pool isn't a big leap.

* A small REST API so orchestration can be triggered remotely
  instead of only from a script.

* An audit log, persisting every run outcome (attack chosen,
  per-stage results, files pulled). This is the one I'd actually
  prioritize first, it's the kind of thing that matters in a
  forensic context and right now this doesn't address it at all.