from langchain.agents import create_agent
from backend.prompts.DB_agent_prompt import DATABASE_AGENT_PROMPT
from backend.llm.llm import gemini_3_5_flash, ollama_qwen_2_5_coder
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from backend.tools.db_tools import DATABASE_TOOLS
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

db = SQLDatabase.from_uri(DB_URL)
sql = SQLDatabaseToolkit(db=db, llm=ollama_qwen_2_5_coder)
sql_toolkit_tools = sql.get_tools()


# print(sql_toolkit_tools)


def chat_db_agent(request, session_id):
    with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
        checkpointer.setup()
        agent = create_agent(model=gemini_3_5_flash, tools=DATABASE_TOOLS + sql_toolkit_tools,
                             system_prompt=DATABASE_AGENT_PROMPT,
                             checkpointer=checkpointer)
        result = agent.invoke({"messages": [{"role": "user", "content": request}]},
                              config={"configurable": {"thread_id": session_id}})
    return result['messages'][-1].content[0]['text']
