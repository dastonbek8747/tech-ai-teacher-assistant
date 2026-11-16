import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver

from backend.llm.llm import gemini_3_5_flash, gemini_3_8_flash
from backend.prompts.document_agent_prompt import DOCUMENT_AGENT_PROMPT
from backend.tools.excell_file_tools import EXCEL_TOOLS
from backend.tools.langchain_toolkits import FILE_MANAGMENT_TOOLS
from backend.tools.power_point_file_tools import POWERPOINT_TOOLS
from backend.tools.word_file_tools import WORD_TOOLS

load_dotenv()

DOC_TOOLS = POWERPOINT_TOOLS + FILE_MANAGMENT_TOOLS + WORD_TOOLS + EXCEL_TOOLS
DB_URL = os.getenv("DATABASE_URL")


def chat_doc_agent(request: str, session_id):
    with PostgresSaver.from_conn_string(conn_string=DB_URL) as checkpointer:
        checkpointer.setup()

        doc_agent = create_agent(model=gemini_3_5_flash(), tools=DOC_TOOLS, system_prompt=DOCUMENT_AGENT_PROMPT,
                                 checkpointer=checkpointer)
        response = doc_agent.invoke({"messages": [{"role": "user", "content": request}]},
                                    config={"configurable": {"thread_id": session_id}})
    return response['messages'][-1].content[0]['text']
