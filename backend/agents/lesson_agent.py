from langchain.agents import create_agent
from backend.prompts.lesson_agent_prompt import LESSON_AGENT_PROMPT
from backend.llm.llm import gemini_3_8_flash
from langgraph.checkpoint.postgres import PostgresSaver
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")


def chat_lesson_agent(request, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
        checkpointer.setup()
        agent = create_agent(model=gemini_3_8_flash, tools=[], checkpointer=checkpointer,
                             system_prompt=LESSON_AGENT_PROMPT)

        result = agent.invoke({"messages": [{"role": "user", "content": f"{request}"}]},
                              config={"configurable": {"thread_id": session_id}})
        return result['messages'][-1].content[0]['text']
