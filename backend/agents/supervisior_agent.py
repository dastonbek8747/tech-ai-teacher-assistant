from dotenv import load_dotenv
from langchain.agents import create_agent
from typing import Literal
from backend.llm.llm import gemini_3_8_flash, groq_gpt_120b_oss, groq_gpt_20b_vgg, gemini_3_5_flash, gemini_3_1_pro
from langgraph.checkpoint.postgres import PostgresSaver
from backend.prompts.supervisior_agent_prompt import SUPERVISIOR_AGENT_PROMPT
from backend.tools.vision_tools import VISION_TOOLS
from backend.tools.search_tools import SEARCH_TOOLS
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")


class GeneratedTasks(BaseModel):
    next_agent: Literal[
        "game_agent", "research_agent", "db_agent", "document_agent", "lesson_agent", "chat_agent"] = Field(
        description="Keyingi agentga o'tkazish")
    agent_task: List[Dict[str, Any]]
    feedback: str
    approved: bool
    retry_count: int
    max_retry_count: int


def chat_supervisor_agent(request, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checker:
        checker.setup()
        supervisior_agent = create_agent(model=gemini_3_5_flash, checkpointer=checker,
                                         system_prompt=SUPERVISIOR_AGENT_PROMPT, tools=VISION_TOOLS + SEARCH_TOOLS,
                                         response_format=GeneratedTasks)

        response = supervisior_agent.invoke({"messages": [{"role": "user", "content": request}]},
                                            config={"configurable": {"thread_id": str(session_id)}}, )
        return response['messages'][-1].content
