from langgraph.graph import StateGraph, START, END
from typing import List, Literal, Annotated, TypedDict, Any
from backend.agents.chat_agent import chat_aget
from backend.agents.DB_agent import chat_db_agent
from pydantic import BaseModel
from backend.llm.llm import gemini_3_5_flash, groq_gpt_120b_oss, gemini_3_1_pro, groq_qwen_3_8_27b
from backend.agents.document_agent import chat_doc_agent
from backend.agents.game_agent import chat_game_agent
from backend.agents.lesson_agent import chat_lesson_agent
from backend.agents.research_agent import chat_research_agent
from backend.agents.supervisior_agent import chat_supervisor_agent
from langchain_core.prompts import ChatPromptTemplate


class Selection(BaseModel):
    request: str
    next_agent: Literal["chat", "supervisior"]


class GeneralState(TypedDict):
    request: str
    session_id: str
    chat_agent_answer: str


llm_structured = groq_qwen_3_8_27b.with_structured_output(Selection)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
        Sen TeachFlow AI uchun yo'naltiruvchi agentsan.

        Foydalanuvchining asl maqsadini aniqlab, tegishli yo'nalishni tanla.

        Qoidalar:
        - Oddiy suhbat, salomlashish, tushuntirish va umumiy savollar:
          next_agent = "chat"
        - Dars rejasi, o'yin, hujjat, jadval yaratish,
          ma'lumot qidirish yoki maxsus agent talab qiladigan vazifalar:
          next_agent = "supervisior"

        request maydoniga foydalanuvchining asl so'rovini yoz.
        Faqat belgilangan strukturaga mos natija qaytar.
        """
    ),
    ("human", "{request}")
])

selection_chain = prompt | llm_structured


def selection_agent(request) -> str:
    resp = selection_chain.invoke(
        {
            "request": "salom sen nimalar qila olasan !"})
    return resp.next_agent


def router_agent():


graph = StateGraph(GeneralState)


def chat_node(state: GeneralState) -> dict:
    request = state['request']
    response = chat_aget(request=request, session_id=state['session_id'])
    return {"chat_agent_answer": response}


def supervisior_node(state: GeneralState) -> dict:
    requests = state['request']
    response = chat_supervisor_agent(request=requests, session_id=state['session_id'])
    return {"supervisor_agent_answer": response}


graph.add_node("selection_agent", selection_agent)

graph.add_conditional_edges()
