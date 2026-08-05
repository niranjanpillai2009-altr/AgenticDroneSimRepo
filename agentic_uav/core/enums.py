"""Enumerations shared across the system."""

from enum import Enum


class ActionType(str, Enum):
    """The skills a drone can perform.

    ARM_TAKEOFF encapsulates the fixed startup sequence (arm, record ground
    level, take off, climb to cruise altitude) that the open-loop baseline ran
    automatically before executing a plan. The rest map one-to-one to the eight
    actions the planner is allowed to emit.
    """
    ARM_TAKEOFF = "arm_takeoff"
    FLY_TO = "fly_to"
    FLY_STRAIGHT = "fly_straight"
    FLY_BACKWARD = "fly_backward"
    FLY_LEFT = "fly_left"
    FLY_RIGHT = "fly_right"
    HOVER = "hover"
    SET_ALTITUDE = "set_altitude"
    LAND = "land"


class SkillStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class PlannerType(str, Enum):
    GEMINI = "gemini"
    LLAMA = "llama"
    MISTRAL = "mistral"
    RULE = "rule"
