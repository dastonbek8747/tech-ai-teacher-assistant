from dotenv import load_dotenv
from langchain.agents import create_agent
from backend.llm.llm import gemini_3_8_flash
from langgraph.checkpoint.postgres import PostgresSaver
from backend.prompts.supervisior_agent_prompt import SUPERVISIOR_AGENT_PROMPT
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")


def chat_supervisor_agent(request, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checker:
        checker.setup()
        supervisior_agent = create_agent(model=gemini_3_8_flash, tools=[], checkpointer=checker,
                                         system_prompt=SUPERVISIOR_AGENT_PROMPT)
        response = supervisior_agent.invoke({"messages": [{"role": "user", "content": request}]},
                                            config={"configurable": {"thread_id": session_id}})
        return response['messages'][-1].content[0]['text']
