"""Tech AI — Streamlit chat front end.

Talks to the FastAPI backend (`POST /chat`). The backend routes each message
through a supervisor agent and one specialist agent (lesson, research,
document, game or database).
"""
import os
import uuid

import requests
import streamlit as st

API_BASE = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Tech AI Teacher Assistant", page_icon="🎓", layout="centered")
st.title("🎓 Tech AI — Teacher Assistant")
st.caption("Multi-agent study helper: lessons, research, documents, games and your database.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

AGENT_LABELS = {
    "lesson_agent": "Lesson Agent",
    "research_agent": "Research Agent",
    "document_agent": "Document Agent",
    "game_agent": "Game Agent",
    "db_agent": "Database Agent",
    "chat_agent": "Chat Agent",
}

with st.sidebar:
    st.header("Session")
    st.code(st.session_state.session_id, language=None)
    st.write("Backend:", API_BASE)
    if st.button("New conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.markdown(
        "**Try asking**\n"
        "- Explain Present Simple for beginners, then make a 10-question quiz\n"
        "- Write study notes about photosynthesis\n"
        "- Find the latest facts about the James Webb telescope"
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("agent"):
            st.caption(f"Answered by: {AGENT_LABELS.get(message['agent'], message['agent'])}")

prompt = st.chat_input("Ask your study question…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                response = requests.post(
                    f"{API_BASE}/chat",
                    json={"request": prompt, "session_id": st.session_state.session_id},
                    timeout=180,
                )
                response.raise_for_status()
                data = response.json()
                answer = data.get("answer", "")
                agent = data.get("next_agent", "")
            except requests.RequestException as exc:
                answer = f"Could not reach the backend: {exc}"
                agent = ""

        st.markdown(answer)
        if agent:
            st.caption(f"Answered by: {AGENT_LABELS.get(agent, agent)}")

    st.session_state.messages.append({"role": "assistant", "content": answer, "agent": agent})
