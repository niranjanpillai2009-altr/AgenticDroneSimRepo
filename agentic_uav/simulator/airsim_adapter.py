"""AirSim implementation of VehicleAdapter.

All the actual AirSim calls from the open-loop baseline live here and nowhere
else. The flight behavior (velocities, the fixed-heading strafing, the
fast-then-gentle landing, per-drone ground-level recording) is reproduced
exactly - this file is a refactor of the baseline's execute_* methods, not a
rewrite of them.

Threading note: AirSim's RPC client is not safe to share across threads. When
drones fly concurrently (one thread each) they would step on each other through
a single shared connection. So this adapter keeps ONE MultirotorClient PER
VEHICLE - the same thing the baseline's Multiple.py did by creating a client per
drone thread.
"""

import threading
import time

import airsim

from ..control import navigation as nav
from ..core.enums import ActionType, SkillStatus
from ..core.models import SkillCommand, SkillResult, VehicleState


class AirSimVehicleAdapter:
    def __init__(self):
        # A setup client used single-threaded before drones fly (connection
        # check, listing/spawning vehicles).
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()

        self._clients = {}          # vehicle_id -> its own MultirotorClient
        self._clients_lock = threading.Lock()
        self._altitude = {}         # vehicle_id -> current hold altitude
        self._ground_z = {}         # vehicle_id -> ground level at takeoff

    def _client_for(self, vehicle_id):
        """One client per vehicle, so concurrent drones don't share a socket."""
        c = self._clients.get(vehicle_id)
        if c is None:
            with self._clients_lock:
                c = self._clients.get(vehicle_id)
                if c is None:
                    c = airsim.MultirotorClient()
                    c.confirmConnection()
                    self._clients[vehicle_id] = c
        return c

    # --- VehicleAdapter interface ---

    def get_state(self, vehicle_id: str) -> VehicleState:
        c = self._client_for(vehicle_id)
        s = c.getMultirotorState(vehicle_name=vehicle_id)
        p = s.kinematics_estimated.position
        return VehicleState(vehicle_id=vehicle_id, x=p.x_val, y=p.y_val, z=p.z_val)

    def execute_skill(self, vehicle_id: str, command: SkillCommand) -> SkillResult:
        try:
            self._dispatch(vehicle_id, command)
            return SkillResult(SkillStatus.SUCCESS)
        except Exception as e:
            return SkillResult(SkillStatus.FAILURE, str(e))

    def stop(self, vehicle_id: str) -> None:
        c = self._client_for(vehicle_id)
        try:
            c.armDisarm(False, vehicle_name=vehicle_id)
            c.enableApiControl(False, vehicle_name=vehicle_id)
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
        c = self._client_for(vid)
        c.enableApiControl(True, vehicle_name=vid)
        c.armDisarm(True, vehicle_name=vid)
        # record ground level before takeoff (terrain varies; drone doesn't
        # collide with it, so landing needs this)
        self._ground_z[vid] = self.get_state(vid).z
        c.takeoffAsync(vehicle_name=vid).join()
        c.moveToZAsync(nav.ALTITUDE, nav.CLIMB_SPEED, vehicle_name=vid).join()
        self._altitude[vid] = nav.ALTITUDE

    def _fly_to(self, vid, x, y, z):
        c = self._client_for(vid)
        c.moveToPositionAsync(x, y, z, nav.FLY_TO_SPEED, vehicle_name=vid).join()
        self._altitude[vid] = z

    def _move(self, vid, action, duration):
        c = self._client_for(vid)
        vx, vy = nav.direction_velocity(action)
        z = self._altitude.get(vid, nav.ALTITUDE)
        c.moveByVelocityZAsync(
            vx=vx, vy=vy, z=z, duration=duration,
            drivetrain=airsim.DrivetrainType.MaxDegreeOfFreedom,
            yaw_mode=airsim.YawMode(is_rate=False, yaw_or_rate=0),
            vehicle_name=vid,
        ).join()
        c.hoverAsync(vehicle_name=vid).join()

    def _hover(self, vid, duration):
        c = self._client_for(vid)
        c.hoverAsync(vehicle_name=vid).join()
        time.sleep(duration)

    def _set_altitude(self, vid, z):
        c = self._client_for(vid)
        self._altitude[vid] = z
        c.moveToZAsync(z, nav.CLIMB_SPEED, vehicle_name=vid).join()

    def _land(self, vid):
        c = self._client_for(vid)
        ground = self._ground_z.get(vid, 0.0)
        # fast descent to a few metres above the recorded ground
        c.moveToZAsync(ground - nav.LAND_FAST_ABOVE, nav.LAND_FAST_SPEED,
                       vehicle_name=vid).join()
        # settle to kill momentum, then a slow gentle final approach
        c.hoverAsync(vehicle_name=vid).join()
        time.sleep(nav.LAND_SETTLE_SECS)
        c.moveToZAsync(ground, nav.LAND_SLOW_SPEED, vehicle_name=vid).join()
        c.armDisarm(False, vehicle_name=vid)
        self._altitude[vid] = 0.0
