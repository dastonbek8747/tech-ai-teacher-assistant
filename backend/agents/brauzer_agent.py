import asyncio
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.agent_toolkits.playwright.toolkit import PlayWrightBrowserToolkit
from langchain_groq import ChatGroq
from playwright.async_api import async_playwright

load_dotenv()

# LLM
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-20b"
)

# System prompt
prompt = """
Sen professional Browser Agent va aqlli dasturchisan.

Vazifalaring:
- Brauzerni boshqarish.
- Saytlarga kirish va ularni tahlil qilish.
- YouTube, Google va boshqa saytlarda navigatsiya qilish.
- Saytdagi matnlar va havolalarni olish.
- Kerakli elementlarni CSS selector orqali aniqlash.
- Foydalanuvchi topshiriqlarini browser tools orqali bajarish.

Qoidalar:
- Har doim o'zbek tilida javob ber.
- Brauzer bilan bog'liq topshiriqlarda mavjud tool'lardan foydalan.
- Foydalanuvchiga nima qilayotganingni tushunarli izohla.
- Bajarilmagan ishni bajarildi deb aytma.
"""


async def main():
    async with async_playwright() as p:

        # Chromium brauzerini ochish
        browser = await p.chromium.launch(
            headless=False
        )

        # Browser toolkit
        toolkit = PlayWrightBrowserToolkit.from_browser(
            async_browser=browser
        )

        tools = toolkit.get_tools()

        print("\nBrowser Agent ishga tushdi!")
        print(f"Mavjud tool'lar soni: {len(tools)}")

        for tool in tools:
            print(f"- {tool.name}")

        # Agent
        agent = create_agent(
            model=llm,
            system_prompt=prompt,
            tools=tools
        )

        try:
            while True:

                usr_input = input("\nENTER : ").strip()

                if not usr_input:
                    continue

                if usr_input.lower() in ["exit", "quit"]:
                    break

                response = await agent.ainvoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": usr_input
                            }
                        ]
                    },
                    config={
                        "configurable": {
                            "thread_id": "exampleuser"
                        }
                    }
                )

                print("\nAGENT:")
                print(response["messages"][-1].content)

        finally:
            await browser.close()

