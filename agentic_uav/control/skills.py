"""Canonical definition of the drone action set.

This is the single source of truth for which actions exist and what parameters
each needs. The planners import it to build their output schema and to validate
plans; the adapter imports it to know what to execute. Keeping it in one place
means the LLM's allowed vocabulary and the executable vocabulary can never drift
apart.
"""

from ..core.enums import ActionType

# action -> list of required parameter names. These are the eight actions the
# planner may emit (ARM_TAKEOFF is added by the agent, not by the planner).
ACTION_PARAMS = {
    ActionType.FLY_TO.value: ["x", "y", "z"],
    ActionType.FLY_STRAIGHT.value: ["duration"],
    ActionType.FLY_BACKWARD.value: ["duration"],
    ActionType.FLY_LEFT.value: ["duration"],
    ActionType.FLY_RIGHT.value: ["duration"],
    ActionType.HOVER.value: ["duration"],
    ActionType.SET_ALTITUDE.value: ["z"],
    ActionType.LAND.value: [],
}

# The action names a planner is allowed to produce.
PLANNER_ACTIONS = list(ACTION_PARAMS.keys())


def build_plan_schema():
    """JSON schema forcing an LLM to return {"plan": [ ...steps... ]}.

    Same schema the baseline used - it stops small local models from collapsing
    a multi-step request into a single action object.
    """
    return {
        "type": "object",
        "properties": {
            "plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": PLANNER_ACTIONS},
                        "params": {"type": "object"},
                    },
                    "required": ["action", "params"],
                },
            }
        },
        "required": ["plan"],
    }
