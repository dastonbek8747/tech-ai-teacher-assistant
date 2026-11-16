from langgraph.graph.state import END, START, StateGraph

from backend.agents.chat_agent import chat_aget
from backend.agents.DB_agent import chat_db_agent
from backend.agents.document_agent import chat_doc_agent
from backend.agents.game_agent import chat_game_agent
from backend.agents.lesson_agent import chat_lesson_agent
from backend.agents.research_agent import chat_research_agent
from backend.agents.supervisior_agent import chat_supervisor_agent
from backend.graph.states import GeneralStates


def routing_node(state: GeneralStates) -> GeneralStates:
    """Ask the supervisor which specialist agent should run next."""
    response = chat_supervisor_agent(
        request=state["request"], session_id=state["session_id"]
    )
    state["next_agent"] = response["next_agent"]
    state["agent_task"] = response["agent_task"]
    state["feedback"] = response.get("feedback", "")
    state["approved_agent_answer"] = response.get("approved", False)
    state["retry_count"] = response.get("retry_count", 0)
    state["max_retry_count"] = response.get("max_retry_count", 1)
    return state


def _task_text(state: GeneralStates) -> str:
    tasks = state.get("agent_task") or []
    parts = []
    for task in tasks:
        if isinstance(task, dict):
            parts.append(str(task.get("description") or task))
        else:
            parts.append(str(task))
    return "\n".join(parts) if parts else state["request"]


def running_task_node(state: GeneralStates) -> GeneralStates:
    """Dispatch the planned task to the specialist agent chosen by the supervisor."""
    agent = state["next_agent"]
    session_id = state["session_id"]
    task_text = _task_text(state)

    if agent == "research_agent":
        state["answer"] = chat_research_agent(request=task_text, session_id=session_id)
    elif agent == "lesson_agent":
        state["answer"] = chat_lesson_agent(request=task_text, session_id=session_id)
    elif agent == "document_agent":
        state["answer"] = chat_doc_agent(request=task_text, session_id=session_id)
    elif agent == "game_agent":
        state["answer"] = chat_game_agent(
            request=task_text, session_id=session_id, information=state["request"]
        )
    elif agent == "db_agent":
        state["answer"] = chat_db_agent(request=task_text, session_id=session_id)
    else:
        state["answer"] = chat_aget(request=task_text, session_id=session_id)

    return state


def evaluator_node(state: GeneralStates) -> GeneralStates:
    """Mark the answer as approved and keep the answer in state."""
    state["approved_agent_answer"] = True
    state["feedback"] = "ok"
    return state


def build_graph():
    """Build and compile the LangGraph multi-agent workflow."""
    graph = StateGraph(GeneralStates)
    graph.add_node("routing", routing_node)
    graph.add_node("running_task", running_task_node)
    graph.add_node("evaluator", evaluator_node)

    graph.add_edge(START, "routing")
    graph.add_edge("routing", "running_task")
    graph.add_edge("running_task", "evaluator")
    graph.add_edge("evaluator", END)

    return graph.compile()

