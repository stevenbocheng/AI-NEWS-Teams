"""
Tavily 搜尋工具封裝
專為 AI Agent 設計的即時網路搜尋
"""
from langchain_community.tools.tavily_search import TavilySearchResults
from config.settings import settings

search_tool = TavilySearchResults(
    max_results=settings.SEARCH_MAX_RESULTS,
    search_depth="advanced",         # 深度搜尋，回傳更完整的內容
    include_answer=True,             # 包含 AI 整合的摘要回答
    include_raw_content=False,       # 不包含完整原始 HTML（節省 Token）
    include_images=False,
    api_key=settings.TAVILY_API_KEY
)
