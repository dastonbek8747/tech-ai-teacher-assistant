import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver

from backend.llm.llm import (
    gemini_3_5_flash,
    groq_gpt_20b_vgg,
    openrouter_apodex_1_1_mini,
    openrouter_gemma,
)
from backend.prompts.game_agent_prompt import GAME_AGENT_PROMPTS
from backend.tools.langchain_toolkits import FILE_MANAGMENT_TOOLS

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")


def chat_game_agent(request: str, session_id,information):
    with PostgresSaver.from_conn_string(DB_URL) as checpointer:
        checpointer.setup()
        game_agent = create_agent(system_prompt=GAME_AGENT_PROMPTS, tools=FILE_MANAGMENT_TOOLS,
                                  checkpointer=checpointer,
                                  model=gemini_3_5_flash())
        response = game_agent.invoke({"messages": [{'role': 'user', 'content': f"{request}+{information}"}]},
                                     config={"configurable": {'thread_id': f"{session_id}"}})
        return response['messages'][-1].content

