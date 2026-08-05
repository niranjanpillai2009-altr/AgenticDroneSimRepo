"""Core data types and the two adapter/planner-facing interfaces.

Nothing here talks to AirSim or an LLM directly - these are the plain data
structures that flow between the agent, the planner, and the simulator adapter.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable

from .enums import SkillStatus


@dataclass
class VehicleState:
    """A snapshot of one drone's state, returned by the adapter."""
    vehicle_id: str
    x: float
    y: float
    z: float                 # NED: negative is up
    armed: bool = False


@dataclass
class SkillCommand:
    """One action for a drone to perform, e.g. fly_straight for 5 seconds."""
    action: str              # an ActionType value
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """The outcome of executing a SkillCommand."""
    status: SkillStatus
    message: str = ""


@dataclass
class AgentContext:
    """Everything a planner needs to decide what a drone should do.

    In the open-loop baseline this is just the drone id and the operator's
    instruction. It is a dataclass (not a bare string) so later work can add
    belief state, teammate knowledge, mission state, etc. without changing the
    planner interface.
    """
    vehicle_id: str
    instruction: str


@dataclass
class AgentDecision:
    """A planner's output: the sequence of skills the drone should perform."""
    plan: List[SkillCommand] = field(default_factory=list)
    source: str = ""         # which planner produced this (for logging)


# --- The two interfaces the whole architecture is built around ---


@runtime_checkable
class VehicleAdapter(Protocol):
    """The ONLY way agent/control code touches the simulator.

    Agents never call arbitrary AirSim methods - they go through an
    implementation of this protocol (AirSimVehicleAdapter, MockVehicleAdapter).
    """

    def get_state(self, vehicle_id: str) -> VehicleState:
        ...

    def execute_skill(self, vehicle_id: str, command: SkillCommand) -> SkillResult:
        ...

    def stop(self, vehicle_id: str) -> None:
        ...
