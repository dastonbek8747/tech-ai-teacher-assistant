from langgraph.graph import StateGraph, START, END
from typing import List, Literal, Annotated, TypedDict, Any
from backend.agents.chat_agent import chat_aget
from backend.agents.DB_agent import chat_db_agent
from pydantic import BaseModel
from backend.llm.llm import gemini_3_5_flash
from backend.agents.document_agent import chat_doc_agent
from backend.agents.game_agent import chat_game_agent
from backend.agents.lesson_agent import chat_lesson_agent
from backend.agents.research_agent import chat_research_agent
from backend.agents.supervisior_agent import chat_supervisor_agent


class Selection(BaseModel):
    request: str
    next_agent: Literal["chat", "supervisior"]


llm_structed = gemini_3_5_flash.with_structured_output(Selection)


class GeneralState(TypedDict):
    request: str
    session_id: str
    chat_agent_answer: str
    db_agent_answer: List[dict[str, Any]]
    document_agent_answer: List[dict[str, Any]]
    game_agent_answer: List[dict[str, Any]]
    lesson_agent_answer: List[dict[str, Any]]
    research_agent_answer: List[dict[str, Any]]
    supervisor_agent_answer: List[dict[str, Any]]
    additional_recommendations: str
    results_agents_answers: List[dict[str, Any]]
    finally_anser: str


graph = StateGraph(GeneralState)


def chat_node(state: GeneralState) -> dict:
    request = state['request']
    response = chat_aget(request=request, session_id=state['session_id'])
    return {"chat_agent_answer": response}


def supervisior_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_supervisor_agent(request=requests, session_id=state['session_id'])
    return {"supervisor_agent_answer": response}


def doc_agent_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_doc_agent(request=requests, session_id=state['session_id'])
    return {"document_agent_answer": response}


def game_agent_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_game_agent(request=requests, session_id=state['session_id'])
    return {"game_agent_answer": response}


def chat_lesson_agent_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_lesson_agent(request=requests, session_id=state['session_id'])
    return {"chat_lesson_agent_answer": response}


def research_agent_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_research_agent(request=requests, session_id=state['session_id'])
    return {"research_agent_answer": response}


def supervisor_agent_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_supervisor_agent(request=requests, session_id=state['session_id'])
    return {"supervisor_agent_answer": response}


def db_agent_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_db_agent(request=requests, session_id=state['session_id'])
    return {"db_agent_answer": response}


# xaritani yarataman
graph.add_conditional_edges()

app = graph.add_edge(START)
