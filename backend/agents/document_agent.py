from backend.prompts.document_agent_prompt import DOCUMENT_AGENT_PROMPT
from backend.tools.langchain_toolkits import TOOLS
from backend.llm.llm import gemini_3_8_flash
from langchain.agents import create_agent
from backend.tools.word_file_tools import WORD_TOOLS
from backend.tools.excell_file_tools import EXCEL_TOOLS
from backend.tools.power_point_file_tools import POWERPOINT_TOOLS
from langgraph.checkpoint.postgres import PostgresSaver

DOC_TOOLS = POWERPOINT_TOOLS + TOOLS + WORD_TOOLS + EXCEL_TOOLS


def chat_doc_agent(request: str, session_id):
    with PostgresSaver.from_conn_string(conn_string="postgresql://user:***REMOVED***@localhost:5432/1212") as checkpointer:
        checkpointer.setup()

        doc_agent = create_agent(model=gemini_3_8_flash, tools=TOOLS, system_prompt=DOCUMENT_AGENT_PROMPT,
                                 checkpointer=checkpointer)

        response = doc_agent.invoke({"messages": [{"role": "user", "content": f"{request}"}]},
                                    config={"configurable": {"thread_id": f"{session_id}"}})
        return response['messages'][-1].content[0]['text']
