from langchain_community.tools import DuckDuckGoSearchRun, DuckDuckGoSearchResults
from ddgs.exceptions import TimeoutException, DDGSException, RatelimitException
from langchain_tavily.tavily_search import TavilySearch, TavilySearchAPIWrapper
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_SEARCH_API_KEY")


def search_tavily(request: str, numer_results: int, ):
    """
    Tavily yordamida internetdan ma'lumot qidiradi.

    Args:
        request (str): Internetdan qidiriladigan savol yoki mavzu.
        numer_results (int): Qaytarilishi kerak bo'lgan natijalar soni.

    Returns:
        dict: Qidiruv natijalari yoki xatolik haqida ma'lumot.
    """
    search = TavilySearch(topic="general", max_results=numer_results, tavily_api_key=TAVILY_API_KEY,
                          include_raw_content=True,
                          include_answer=True)
    try:
        result = search.invoke({"query": request})
        return result
    except  Exception as e:
        return {"error": str(e)}


def duc_ducgo_search_results(request: str, numer_results: int):
    """
      DuckDuckGo qidiruv tizimi orqali internetdan ma'lumot qidiradi.

      Args:
          request (str): Qidirish uchun so'rov yoki kalit so'zlar.
          numer_results (int): Qaytarilishi so'ralgan qidiruv natijalari soni.

      Returns:
          str: Qidiruv natijalari JSON formatidagi matn ko'rinishida.
      """
    search = DuckDuckGoSearchResults(output_format='json', num_results=numer_results)
    try:
        result = search.invoke({"query": request, "num_results": numer_results})
        return result
    except (TimeoutException, DDGSException, RatelimitException) as e:
        return (f"Qidiruv vaqti tugadi."
                f"Iltimos qaytadan urinib ko'ring"
                f"Xatolik sababi : {e}")
    except Exception as e:
        return f"Qidiruvda xatolik berdi: {e}"


def duc_ducgo_search(request: str):
    """
    DuckDuckGo qidiruv tizimi orqali internetdan ma'lumot qidiradi.

    Args:
        request (str): Qidirish uchun so'rov yoki kalit so'zlar.

    Returns:
        str: Qidiruv natijalarini matn ko'rinishida qaytaradi.
    """
    search = DuckDuckGoSearchRun()
    try:
        result = search.invoke({"query": request})
        return result
    except (TimeoutException, DDGSException, RatelimitException) as e:
        return {"eror": str(e)}



SEARCH_TOOLS = [duc_ducgo_search, duc_ducgo_search_results, search_tavily]
