from langchain.agents import create_agent
from backend.prompts.lesson_agent_prompt import LESSON_AGENT_PROMPT
from backend.llm.llm import gemini_3_8_flash
from langgraph.checkpoint.postgres import PostgresSaver
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
    checkpointer.setup()
    agent = create_agent(model=gemini_3_8_flash, tools=[], checkpointer=checkpointer, system_prompt=LESSON_AGENT_PROMPT)
    while True:
        user_inp = input("Enter your command: ")
        if user_inp in ("exit", "quit"):
            break
        result = agent.invoke({"messages": [{"role": "user", "content": f"{user_inp}"}]},
                              config={"configurable": {"thread_id": "daston12345"}})
        print(result['messages'][-1].content[0]['text'])
