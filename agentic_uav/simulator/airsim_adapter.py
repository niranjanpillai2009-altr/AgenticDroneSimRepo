"""AirSim implementation of VehicleAdapter.

All the actual AirSim calls from the open-loop baseline live here and nowhere
else. The flight behavior (velocities, the fixed-heading strafing, the
fast-then-gentle landing, per-drone ground-level recording) is reproduced
exactly - this file is a refactor of the baseline's execute_* methods, not a
rewrite of them.
"""

import time

import airsim

from ..control import navigation as nav
from ..core.enums import ActionType, SkillStatus
from ..core.models import SkillCommand, SkillResult, VehicleState


class AirSimVehicleAdapter:
    def __init__(self):
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        # per-vehicle flight state kept by the adapter, not the agent
        self._altitude = {}   # vehicle_id -> current hold altitude
        self._ground_z = {}   # vehicle_id -> ground level recorded at takeoff

    # --- VehicleAdapter interface ---

    def get_state(self, vehicle_id: str) -> VehicleState:
        s = self.client.getMultirotorState(vehicle_name=vehicle_id)
        p = s.kinematics_estimated.position
        return VehicleState(vehicle_id=vehicle_id, x=p.x_val, y=p.y_val, z=p.z_val)

    def execute_skill(self, vehicle_id: str, command: SkillCommand) -> SkillResult:
        try:
            self._dispatch(vehicle_id, command)
            return SkillResult(SkillStatus.SUCCESS)
        except Exception as e:
            return SkillResult(SkillStatus.FAILURE, str(e))

    def stop(self, vehicle_id: str) -> None:
        try:
            self.client.armDisarm(False, vehicle_name=vehicle_id)
            self.client.enableApiControl(False, vehicle_name=vehicle_id)
        except Exception:
            pass

    # --- dispatch ---

    def _dispatch(self, vid, command):
        action = command.action
        p = command.params

        if action == ActionType.ARM_TAKEOFF.value:
            self._arm_takeoff(vid)
        elif action == ActionType.FLY_TO.value:
            self._fly_to(vid, p["x"], p["y"], p["z"])
        elif action in (ActionType.FLY_STRAIGHT.value, ActionType.FLY_BACKWARD.value,
                        ActionType.FLY_LEFT.value, ActionType.FLY_RIGHT.value):
            self._move(vid, action, p["duration"])
        elif action == ActionType.HOVER.value:
            self._hover(vid, p["duration"])
        elif action == ActionType.SET_ALTITUDE.value:
            self._set_altitude(vid, p["z"])
        elif action == ActionType.LAND.value:
            self._land(vid)
        else:
            raise ValueError(f"unknown action '{action}'")

    # --- flight primitives (baseline behavior) ---

    def _arm_takeoff(self, vid):
        self.client.enableApiControl(True, vehicle_name=vid)
        self.client.armDisarm(True, vehicle_name=vid)
        # record ground level before takeoff (terrain varies; drone doesn't
        # collide with it, so landing needs this)
        self._ground_z[vid] = self.get_state(vid).z
        self.client.takeoffAsync(vehicle_name=vid).join()
        self.client.moveToZAsync(nav.ALTITUDE, nav.CLIMB_SPEED,
                                 vehicle_name=vid).join()
        self._altitude[vid] = nav.ALTITUDE

    def _fly_to(self, vid, x, y, z):
        self.client.moveToPositionAsync(x, y, z, nav.FLY_TO_SPEED,
                                        vehicle_name=vid).join()
        self._altitude[vid] = z

    def _move(self, vid, action, duration):
        vx, vy = nav.direction_velocity(action)
        z = self._altitude.get(vid, nav.ALTITUDE)
        self.client.moveByVelocityZAsync(
            vx=vx, vy=vy, z=z, duration=duration,
            drivetrain=airsim.DrivetrainType.MaxDegreeOfFreedom,
            yaw_mode=airsim.YawMode(is_rate=False, yaw_or_rate=0),
            vehicle_name=vid,
        ).join()
        self.client.hoverAsync(vehicle_name=vid).join()

    def _hover(self, vid, duration):
        self.client.hoverAsync(vehicle_name=vid).join()
        time.sleep(duration)

    def _set_altitude(self, vid, z):
        self._altitude[vid] = z
        self.client.moveToZAsync(z, nav.CLIMB_SPEED, vehicle_name=vid).join()

    def _land(self, vid):
        ground = self._ground_z.get(vid, 0.0)
        # fast descent to a few metres above the recorded ground
        self.client.moveToZAsync(ground - nav.LAND_FAST_ABOVE, nav.LAND_FAST_SPEED,
                                 vehicle_name=vid).join()
        # settle to kill momentum, then a slow gentle final approach
        self.client.hoverAsync(vehicle_name=vid).join()
        time.sleep(nav.LAND_SETTLE_SECS)
        self.client.moveToZAsync(ground, nav.LAND_SLOW_SPEED, vehicle_name=vid).join()
        self.client.armDisarm(False, vehicle_name=vid)
        self._altitude[vid] = 0.0
