# AgenticDroneSimRepo

A multi-agent UAV simulation framework. An operator gives drones instructions,
a planner turns each into a validated sequence of flight actions, and the drones
execute in a CARLA-Air / AirSim simulator.

This repo is the restructured successor to the flat-script open-loop baseline
(tagged `v0.1-open-loop-baseline` in the original repo). This version keeps the
**same flight behavior** but organizes it behind clean interfaces so the next
phase - persistent agents, peer communication, task allocation, fault tolerance -
can be built on top.

## The two interfaces everything is built around

- **`MissionPlanner`** (`agentic_uav/planners/base_planner.py`)
  `decide(context: AgentContext) -> AgentDecision`.
  Implemented by Gemini, Llama, Mistral, and a deterministic rule policy - the
  agent doesn't know or care which it holds.

- **`VehicleAdapter`** (`agentic_uav/core/models.py`)
  `get_state`, `execute_skill`, `stop`.
  Agents never call AirSim directly. Implemented by `AirSimVehicleAdapter`
  (real sim) and `MockVehicleAdapter` (no sim, used by the tests).

## Layout

```
agentic_uav/
  core/          data types (models), enums, clock, events
  simulator/     VehicleAdapter impls (airsim, mock), scenario setup
  control/       skills, action executor, navigation constants, safety (stub)
  agents/        drone agent, rule policy, belief state (stub), fallbacks (stub)
  coordination/  message bus, network model, task allocation, roles  (all stubs)
  planners/      MissionPlanner interface + gemini/llama/mistral/rule
  experiments/   mission runner, metrics (stub), logging
configs/         missions / networks / vehicles / experiments
scripts/         run_single_mission.py, run_batch.py (stub), analyze (stub)
tests/           behavior-preservation test (mock adapter)
docs/
```

Modules marked *(stub)* are placeholders for the next phase (communication,
faults, roles, metrics). The refactor added structure, not new behavior.

## Quick start

Run a mission with no simulator and no LLM (fast, deterministic):
```
python scripts/run_single_mission.py --planner rule --adapter mock --drones 1
```

Verify behavior preservation:
```
python tests/test_behavior_preservation.py
```

Fly for real (simulator running, models pulled - see docs/ARCHITECTURE.md and the
baseline SETUP guide):
```
python scripts/run_single_mission.py --planner gemini
python scripts/run_single_mission.py --planner mistral --drones 2
```

Planners: `gemini | llama | mistral | rule`. Adapters: `airsim | mock`.
