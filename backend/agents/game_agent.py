from langchain.agents import create_agent
from backend.prompts.game_agent_prompt import GAME_AGENT_PROMPTS
from backend.tools.langchain_toolkits import FILE_MANAGMENT_TOOLS
from backend.llm.llm import openrouter_apodex_1_1_mini, gemini_3_8_flash, groq_gpt_20b_vgg, openrouter_gemma, \
    gemini_3_5_flash
from langgraph.checkpoint.postgres import PostgresSaver


def chat_game_agent_prompt(request: str, session_id):
    with PostgresSaver.from_conn_string("postgresql://user:***REMOVED***@localhost:5432/1212") as checpointer:
        checpointer.setup()
        game_agent = create_agent(system_prompt=GAME_AGENT_PROMPTS, tools=FILE_MANAGMENT_TOOLS,
                                  checkpointer=checpointer,
                                  model=gemini_3_5_flash)
        response = game_agent.invoke({"messages": [{'role': 'user', 'content': f"{request}"}]},
                                     config={"configurable": {'thread_id': f"{session_id}"}})
        return response['messages'][-1].content


while True:
    user_request = r = input("REQUEST : ")
    if user_request in ('exit', 'quit'):
        break
    natija = chat_game_agent_prompt(request=user_request, session_id="exampleuser")
    print(natija)
