"""LLM factory.

Every model is created lazily through a getter, so importing this module never
requires an API key. A missing key only raises when that specific model is used.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and add your key."
        )
    return value


@lru_cache(maxsize=None)
def _groq(model: str):
    from langchain_groq import ChatGroq

    return ChatGroq(api_key=_require("GROQ_API_KEY"), model=model)


@lru_cache(maxsize=None)
def _gemini(model: str):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(api_key=_require("GEMINI_API_KEY"), model=model)


@lru_cache(maxsize=None)
def _openrouter(model: str):
    from langchain_openrouter import ChatOpenRouter

    return ChatOpenRouter(api_key=_require("OPENROUTER_API_KEY"), model=model)


@lru_cache(maxsize=None)
def _ollama(model: str):
    from langchain_ollama import ChatOllama

    return ChatOllama(model=model)


# --- Groq ---
def groq_llama_3_1_8b():
    return _groq("llama-3.1-8b-instant")


def groq_llama_3_3_70b():
    return _groq("llama-3.3-70b-versatile")


def groq_gpt_120b_oss():
    return _groq("openai/gpt-oss-120b")


def groq_gpt_20b_vgg():
    return _groq("openai/gpt-oss-20b")


# --- Google Gemini ---
def gemini_3_8_flash():
    return _gemini("gemini-3.8-flash")


def gemini_3_5_flash():
    return _gemini("gemini-3.5-flash-lite")


def gemini_3_1_pro():
    return _gemini("gemini-3.1-pro-preview")


# --- OpenRouter ---
def openrouter_apodex_1_1_mini():
    return _openrouter("apodex/apodex-1.1-mini:free")


def openrouter_gemma():
    return _openrouter("google/gemma-4-31b-it:free")


# --- Ollama (local) ---
def ollama_qwen_2_5_coder():
    return _ollama("qwen2.5-coder:latest")


def ollama_qwen3_8():
    return _ollama("qwen3:8b")
