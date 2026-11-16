import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langgraph.checkpoint.postgres import PostgresSaver

from backend.llm.llm import gemini_3_5_flash, ollama_qwen_2_5_coder
from backend.prompts.DB_agent_prompt import DATABASE_AGENT_PROMPT
from backend.tools.db_tools import DATABASE_TOOLS

load_dotenv()


def chat_db_agent(request, session_id):
    """Run the database agent. Requires DATABASE_URL to be set."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")

    db = SQLDatabase.from_uri(db_url)
    sql_toolkit = SQLDatabaseToolkit(db=db, llm=ollama_qwen_2_5_coder())
    sql_toolkit_tools = sql_toolkit.get_tools()

    with PostgresSaver.from_conn_string(db_url) as checkpointer:
        checkpointer.setup()
        agent = create_agent(
            model=gemini_3_5_flash(),
            tools=DATABASE_TOOLS + sql_toolkit_tools,
            system_prompt=DATABASE_AGENT_PROMPT,
            checkpointer=checkpointer,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": request}]},
            config={"configurable": {"thread_id": session_id}},
        )
    return result["messages"][-1].content
