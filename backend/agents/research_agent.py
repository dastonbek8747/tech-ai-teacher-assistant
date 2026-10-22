from langchain.agents import create_agent
from backend.prompts.research_agent_prompt import RESEARCH_AGENT_PROMPT
from backend.tools.search_tools import SEARCH_TOOLS
from backend.llm.llm import gemini_3_5_flash
from langgraph.checkpoint.postgres import PostgresSaver
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")


def chat_research_agent(request, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
        checkpointer.setup()
        agent = create_agent(model=gemini_3_5_flash, tools=SEARCH_TOOLS, system_prompt=RESEARCH_AGENT_PROMPT,
                             checkpointer=checkpointer)

        result = agent.invoke({"messages": [{"role": "user", "content": f"{request}"}]},
                              config={"configurable": {"thread_id": session_id}})
        return result["messages"][-1].content[0]['text']
