from states import GeneralStates
from langgraph.graph.state import StateGraph, START, END
from backend.agents.DB_agent import chat_db_agent
from backend.agents.lesson_agent import chat_lesson_agent
from backend.agents.chat_agent import chat_aget
from backend.agents.game_agent import chat_game_agent
from backend.agents.document_agent import chat_doc_agent
from backend.agents.lesson_agent import chat_lesson_agent
from backend.agents.research_agent import chat_research_agent
from backend.agents.supervisior_agent import chat_supervisor_agent


def routing_node(state: GeneralStates) -> GeneralStates:
    request = state['request']
    session_id = state['session_id']

    response = chat_supervisor_agent(request=request, session_id=session_id)

    state['next_agent'] = response['next_agent']
    state['agent_task'] = response['agent_task']

    return state


def running_task_node(state: GeneralStates) -> GeneralStates:
    agent = state['next_agent']
    task = state['agent_task']
    if agent=="research_agent":


def evalutor_node(state: GeneralStates) -> GeneralStates:
    pass
