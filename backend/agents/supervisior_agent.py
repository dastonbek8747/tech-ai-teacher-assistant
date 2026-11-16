import os
from typing import Any, Dict, List, Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import BaseModel, Field

from backend.llm.llm import gemini_3_1_pro, gemini_3_5_flash, gemini_3_8_flash, groq_gpt_20b_vgg, groq_gpt_120b_oss
from backend.prompts.supervisior_agent_prompt import SUPERVISIOR_AGENT_PROMPT
from backend.tools.search_tools import SEARCH_TOOLS
from backend.tools.vision_tools import VISION_TOOLS

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
        supervisior_agent = create_agent(model=gemini_3_5_flash(), checkpointer=checker,
                                         system_prompt=SUPERVISIOR_AGENT_PROMPT, tools=VISION_TOOLS + SEARCH_TOOLS,
                                         response_format=GeneratedTasks)

        response = supervisior_agent.invoke({"messages": [{"role": "user", "content": request}]},
                                            config={"configurable": {"thread_id": str(session_id)}}, )
        content = response['messages'][-1].content
        if isinstance(content, GeneratedTasks):
            return content.model_dump()
        if isinstance(content, dict):
            return content
        if isinstance(content, list) and content and isinstance(content[0], dict):
            return content[0]
        return GeneratedTasks.model_validate_json(content).model_dump()
