import logging
from time import perf_counter

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from app.pipeline.state import PipelineState
from app.pipeline.nodes.ingest import ingest_node
from app.pipeline.nodes.extract import extract_node
from app.pipeline.nodes.normalize import normalize_node
from app.pipeline.nodes.analytics import analytics_node
from app.pipeline.nodes.redflags import redflag_node
from app.pipeline.nodes.summary import summary_node
from app.pipeline.nodes.hitl_gate import hitl_gate_node
from app.pipeline.nodes.deliver import deliver_node

_CHECKPOINTER_CONTEXTS = []
logger = logging.getLogger(__name__)


def _timed_node(node_name: str, node_fn):
    def _wrapped(state: PipelineState) -> PipelineState:
        start = perf_counter()
        try:
            return node_fn(state)
        finally:
            elapsed = perf_counter() - start
            logger.info(
                "Stage timing: job=%s stage=%s elapsed=%.3fs",
                state.get("job_id"),
                node_name,
                elapsed,
            )

    return _wrapped


def route_hitl(state: PipelineState) -> str:
    action = state.get("hitl_action")
    if action == "reject":
        return "summary"
    if action in ("approve", "edit"):
        return "deliver"
    return "end"


def build_graph(database_url: str):
    # SqliteSaver expects a raw sqlite connection string (path only)
    db_path = database_url.replace("sqlite:///", "")
    checkpointer_ctx = SqliteSaver.from_conn_string(db_path)
    checkpointer = checkpointer_ctx.__enter__()
    _CHECKPOINTER_CONTEXTS.append(checkpointer_ctx)

    graph = StateGraph(PipelineState)

    graph.add_node("ingest", _timed_node("ingest", ingest_node))
    graph.add_node("extract", _timed_node("extract", extract_node))
    graph.add_node("normalize", _timed_node("normalize", normalize_node))
    graph.add_node("analytics", _timed_node("analytics", analytics_node))
    graph.add_node("redflags", _timed_node("redflags", redflag_node))
    graph.add_node("summary", _timed_node("summary", summary_node))
    graph.add_node("hitl_gate", _timed_node("hitl_gate", hitl_gate_node))
    graph.add_node("deliver", _timed_node("deliver", deliver_node))

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "normalize")
    graph.add_edge("normalize", "analytics")
    graph.add_edge("analytics", "redflags")
    graph.add_edge("redflags", "summary")
    graph.add_edge("summary", "hitl_gate")
    graph.add_conditional_edges(
        "hitl_gate",
        route_hitl,
        {"deliver": "deliver", "summary": "summary", "end": END},
    )
    graph.add_edge("deliver", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_gate"],
    )
