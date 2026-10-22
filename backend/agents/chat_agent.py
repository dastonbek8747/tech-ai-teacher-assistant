from backend.llm.llm import gemini_3_8_flash
from backend.prompts.chat_agent_promp import CHAT_AGENT_PROMPT
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")


def chat_aget(request: str, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
        checkpointer.setup()
        agent = create_agent(checkpointer=checkpointer, model=gemini_3_8_flash, system_prompt=CHAT_AGENT_PROMPT,
                             tools=[])
        response = agent.invoke({"messages": [{"role": "user", "content": request}]},
                                config={"configurable": {"thread_id": session_id}})
        return response['messages'][-1].content



