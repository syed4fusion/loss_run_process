"""HITL gate node.

Execution is interrupted before this node by LangGraph configuration.
On resume, this node applies the HITL decision into state for conditional routing.
"""

from app.pipeline.state import PipelineState


def hitl_gate_node(state: PipelineState) -> PipelineState:
    action = state.get("hitl_action")
    updated = {**state, "current_stage": "hitl_pending"}
    if action == "edit" and state.get("hitl_edit_content"):
        updated["final_summary"] = state["hitl_edit_content"]
    elif action == "approve" and state.get("draft_summary"):
        updated["final_summary"] = state["draft_summary"]
    elif action == "reject":
        updated["final_summary"] = None
        updated["hitl_edit_content"] = None
        updated["rejection_count"] = int(state.get("rejection_count", 0)) + 1
    return updated
