from langchain_groq import ChatGroq
from langchain_openrouter import ChatOpenRouter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_llama_3_1_8b = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.1-8b-instant"
)
groq_llama_3_3_70b = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile"
)
groq_gpt_120b_oss = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-120b"
)
groq_gpt_20b_vgg = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-20b"
)
groq_safety_gpt_20b = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-safeguard-20b"
)
groq_qwen_3_8_27b = ChatGroq(
    api_key=GROQ_API_KEY,
    model="qwen/qwen3.8-27b"
)

gemini_3_8_flash = ChatGoogleGenerativeAI(
    api_key=GEMINI_API_KEY,
    model="gemini-3.8-flash"
)
gemini_3_5_flash = ChatGoogleGenerativeAI(
    api_key=GEMINI_API_KEY,
    model="gemini-3.5-flash-lite"
)
gemini_3_1_pro = ChatGoogleGenerativeAI(
    api_key=GEMINI_API_KEY,
    model="gemini-3.1-pro-preview"
)

openrouter_apodex_1_1_mini = ChatOpenRouter(
    api_key=OPENROUTER_API_KEY,
    model="apodex/apodex-1.1-mini:free"
)
openrouter_dots3 = ChatOpenRouter(
    api_key=OPENROUTER_API_KEY,
    model="dots-studio/dots-3-note-preview:free"
)
openrouter_gemma = ChatOpenRouter(
    api_key=OPENROUTER_API_KEY,
    model="google/gemma-4-31b-it:free"
)

ollama_qwen_2_5_coder = ChatOllama(model="qwen2.5-coder:latest")
ollama_qwen3_8 = ChatOllama(model="qwen3:8b")
