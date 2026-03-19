"""
Agent A：趨勢研究員
基於 data-scraper-agent skill (SKILL.md)

三層架構：COLLECT → ENRICH → PASS
  COLLECT：RSS 多來源 + Tavily 搜尋
  ENRICH：規則預篩（關鍵字過濾 + URL 去重）→ LLM 重要性評分
  PASS：輸出結構化新聞列表給 Deep Researcher
"""
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.tools.search import search_tool
from src.graph.workflow import NewsState
from config.settings import settings

# ─────────────────────────────────────────────
# RSS 新聞來源（免費、即時、高品質 AI 新聞）
# ─────────────────────────────────────────────
RSS_SOURCES = [
    ("VentureBeat AI",     "https://venturebeat.com/category/ai/feed/"),
    ("MIT Tech Review",    "https://www.technologyreview.com/feed/"),
    ("The Verge AI",       "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("TechCrunch AI",      "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Ars Technica AI",    "https://feeds.arstechnica.com/arstechnica/technology-lab"),
]

# 規則預篩：至少包含一個關鍵字
REQUIRED_KEYWORDS = [
    "ai", "artificial intelligence", "llm", "gpt", "claude", "gemini",
    "machine learning", "deep learning", "openai", "anthropic", "google deepmind",
    "nvidia", "大型語言模型", "人工智慧", "生成式", "模型"
]

# 排除詞（農場文指標）
BLOCKED_KEYWORDS = [
    "sponsored", "advertisement", "buy now", "discount", "sale",
    "crypto", "bitcoin", "nft", "meme"
]

RESEARCHER_SYSTEM_PROMPT = """你是一位 AI 科技新聞篩選專家，負責從大量新聞中挑出最值得深入報導的。

評分標準（0-100 分）：
- 90+：技術突破、重大產品發佈、影響整個產業的政策
- 70-89：有意義的技術進展、值得關注的公司動態
- 50-69：一般業界消息、有討論度但不突出
- <50：農場文、舊聞、重複報導 → 排除

輸出 JSON 格式：
{
  "selected": [
    {
      "title": "新聞標題",
      "url": "來源網址",
      "source": "媒體名稱",
      "summary": "100字內繁體中文摘要",
      "importance_score": 85,
      "category": "模型發佈|產業動態|研究突破|政策法規|台灣視角",
      "why_important": "20字內說明為何值得報導"
    }
  ]
}

只回傳分數 ≥ 70 的新聞，最多 5 則，按重要性排序。"""


# ─────────────────────────────────────────────
# COLLECT 層：RSS + Tavily
# ─────────────────────────────────────────────
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-news-bot/1.0)"}


def _fetch_rss(name: str, url: str) -> list[dict]:
    """抓取單一 RSS 來源"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        items = []
        for item in root.findall(".//item")[:10]:  # 每個來源最多取 10 則
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "").strip()
            pub   = item.findtext("pubDate", "").strip()
            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": name,
                    "description": desc[:300],
                    "pub_date": pub,
                    "date_found": datetime.now(timezone.utc).date().isoformat(),
                })
        return items
    except Exception:
        return []


def _fetch_tavily() -> list[dict]:
    """Tavily 搜尋補充（覆蓋 RSS 可能漏掉的台灣新聞）"""
    try:
        results = search_tool.invoke("AI 人工智慧 科技新聞 2026 最新")
        if isinstance(results, list):
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "source": "Tavily",
                    "description": r.get("content", "")[:300],
                    "date_found": datetime.now(timezone.utc).date().isoformat(),
                }
                for r in results if r.get("title") and r.get("url")
            ]
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────
# ENRICH 層：規則預篩 + URL 去重
# ─────────────────────────────────────────────
def _is_relevant(item: dict) -> bool:
    """規則預篩：比 LLM 快 100 倍，先砍掉明顯不相關的"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    if any(kw in text for kw in BLOCKED_KEYWORDS):
        return False
    return any(kw in text for kw in REQUIRED_KEYWORDS)


def _deduplicate(items: list[dict]) -> list[dict]:
    """URL 去重：同一篇文章可能來自多個 RSS 來源"""
    seen_urls = set()
    result = []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            result.append(item)
    return result


# ─────────────────────────────────────────────
# 主節點
# ─────────────────────────────────────────────
def researcher_node(state: NewsState) -> NewsState:
    """
    Researcher Agent 節點
    COLLECT → 規則預篩 → 去重 → LLM 重要性評分 → 輸出 raw_news
    """
    # Step 1：COLLECT - RSS 多來源 + Tavily
    all_items = []
    for name, url in RSS_SOURCES:
        all_items.extend(_fetch_rss(name, url))
    all_items.extend(_fetch_tavily())

    # Step 2：規則預篩（快速，在 LLM 之前）
    filtered = [item for item in all_items if _is_relevant(item)]

    # Step 3：URL 去重
    deduped = _deduplicate(filtered)

    if not deduped:
        return {**state, "raw_news": [], "revision_count": 0, "error": "未找到任何 AI 相關新聞"}

    # Step 4：LLM 重要性評分（批次處理，節省 token）
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.1
    )

    # 最多送 20 則給 LLM 評分（data-scraper-agent 建議批次）
    candidates = deduped[:20]
    news_text = "\n".join(
        f"{i+1}. [{item['source']}] {item['title']}\n   URL: {item['url']}\n   摘要: {item['description'][:150]}"
        for i, item in enumerate(candidates)
    )

    messages = [
        SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
        HumanMessage(content=f"請從以下新聞中篩選出最重要的 AI 科技新聞：\n\n{news_text}")
    ]

    import json
    response = llm.invoke(messages)
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        result = json.loads(content)
        selected = result.get("selected", [])
    except (json.JSONDecodeError, ValueError):
        # fallback：直接用前 5 則
        selected = [
            {"title": item["title"], "url": item["url"],
             "source": item["source"], "summary": item["description"],
             "importance_score": 70, "category": "產業動態"}
            for item in candidates[:5]
        ]

    return {
        **state,
        "raw_news": selected,
        "revision_count": 0,
        "research_analysis": "",
        "error": ""
    }
