"""In-memory VehicleAdapter with no simulator.

Every skill is recorded (and a simple position is updated) instead of flown.
This lets the whole pipeline - planner, agent, executor - run with no AirSim, no
GPU, no Ollama, which is how the tests verify that a given mission produces the
expected sequence of skills. It's also handy for developing coordination logic
later without launching the simulator.
"""

from ..control import navigation as nav
from ..core.enums import ActionType, SkillStatus
from ..core.models import SkillCommand, SkillResult, VehicleState


class MockVehicleAdapter:
    def __init__(self):
        self.log = []          # list of (vehicle_id, action, params)
        self._pos = {}         # vehicle_id -> [x, y, z]
        self._altitude = {}

    def get_state(self, vehicle_id: str) -> VehicleState:
        x, y, z = self._pos.get(vehicle_id, [0.0, 0.0, 0.0])
        return VehicleState(vehicle_id=vehicle_id, x=x, y=y, z=z)

    def execute_skill(self, vehicle_id: str, command: SkillCommand) -> SkillResult:
        self.log.append((vehicle_id, command.action, dict(command.params)))
        self._pos.setdefault(vehicle_id, [0.0, 0.0, 0.0])

        a, p = command.action, command.params
        if a == ActionType.ARM_TAKEOFF.value:
            self._pos[vehicle_id][2] = nav.ALTITUDE
            self._altitude[vehicle_id] = nav.ALTITUDE
        elif a == ActionType.FLY_TO.value:
            self._pos[vehicle_id] = [p["x"], p["y"], p["z"]]
            self._altitude[vehicle_id] = p["z"]
        elif a == ActionType.SET_ALTITUDE.value:
            self._pos[vehicle_id][2] = p["z"]
            self._altitude[vehicle_id] = p["z"]
        elif a == ActionType.LAND.value:
            self._pos[vehicle_id][2] = 0.0
        # directional moves / hover don't change our simple bookkeeping
        return SkillResult(SkillStatus.SUCCESS)

    def stop(self, vehicle_id: str) -> None:
        self.log.append((vehicle_id, "stop", {}))

    # convenience for tests
    def actions_for(self, vehicle_id: str):
        return [a for (vid, a, _p) in self.log if vid == vehicle_id]
