import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver

from backend.llm.llm import *
from backend.prompts.lesson_agent_prompt import LESSON_AGENT_PROMPT
from backend.tools import search_tools

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")


def chat_lesson_agent(request: str, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
        checkpointer.setup()
        agent = create_agent(model=gemini_3_5_flash(), system_prompt=LESSON_AGENT_PROMPT, tools=[],
                             checkpointer=checkpointer)
        response = agent.invoke({"messages": [{"role": "user", "content": request}]},
                                config={"configurable": {"thread_id": str(session_id)}})
        return response['messages'][-1].content


