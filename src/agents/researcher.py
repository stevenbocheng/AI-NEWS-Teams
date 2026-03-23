"""
Agent A：趨勢研究員
基於 data-scraper-agent skill (SKILL.md)

三層架構：COLLECT → ENRICH → PASS
  COLLECT：RSS 多來源 + Tavily 搜尋
  ENRICH：規則預篩（關鍵字過濾 + URL 去重）→ LLM 內容評分 → Python 綜合評分
  PASS：輸出結構化新聞列表給 Deep Researcher

評分架構（四維度）：
  Final Score = (content_score × source_weight + recency_bonus + keyword_bonus) / 25 × 100
  - content_score (0-10)：LLM 評估內容重要性，唯一需要 LLM 的部分
  - source_weight (0.8-1.0)：媒體可信度，靜態表，Python 計算
  - recency_bonus (0-10)：線性時效衰減，Python 計算
  - keyword_bonus (0-5)：熱門關鍵字加分，Python 計算
  閾值：final_score ≥ 60 才進入後續流程
"""
import json
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
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

# ─────────────────────────────────────────────
# 評分參數（Python 負責的部分）
# ─────────────────────────────────────────────
_CUTOFF_HOURS = 48  # 只保留 48 小時內的新聞

# 媒體可信度加權（乘數）
SOURCE_WEIGHTS: dict[str, float] = {
    "MIT Tech Review":  1.00,  # 學術深度最高
    "Ars Technica AI":  0.95,
    "VentureBeat AI":   0.95,
    "The Verge AI":     0.90,
    "TechCrunch AI":    0.85,
    "Tavily":           0.80,  # 搜尋補充，品質較不確定
}
_DEFAULT_SOURCE_WEIGHT = 0.85

# 關鍵字加分（標題比對）
_KEYWORD_BONUS_TIERS: list[tuple[list[str], float]] = [
    (["gpt-5", "gpt-4", "claude", "gemini", "llama", "mistral", "openai", "anthropic", "deepmind"], 3.0),
    (["funding", "acquisition", "regulation", "nvidia", "台灣", "taiwan", "open source", "open-source"], 2.0),
    (["benchmark", "research", "paper", "launch", "release", "發布", "發表"], 1.0),
]
_KEYWORD_BONUS_MAX = 5.0

# 評分公式最大原始分（用於正規化）：10 × 1.0 + 10 + 5 = 25
_RAW_SCORE_MAX = 25.0
_FINAL_SCORE_THRESHOLD = 60  # 正規化後 ≥ 60 才進入後續流程


def _recency_bonus(pub_date_str: str) -> float:
    """48 小時內線性從 10 衰減到 0，超過 48 小時得 0"""
    if not pub_date_str:
        return 0.0
    try:
        pub_dt = datetime.fromisoformat(pub_date_str)
        age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
        if age_hours >= _CUTOFF_HOURS:
            return 0.0
        return round(10.0 * (1 - age_hours / _CUTOFF_HOURS), 1)
    except Exception:
        return 0.0


def _keyword_bonus(title: str) -> float:
    """標題含熱門關鍵字加分，最多 5 分"""
    title_lower = title.lower()
    total = 0.0
    for keywords, bonus in _KEYWORD_BONUS_TIERS:
        if any(kw in title_lower for kw in keywords):
            total += bonus
    return min(total, _KEYWORD_BONUS_MAX)


def _compute_final_score(content_score: float, source: str, pub_date: str, title: str) -> float:
    """
    綜合評分公式：
    raw = content_score × source_weight + recency_bonus + keyword_bonus
    final = raw / 25 × 100
    """
    weight = SOURCE_WEIGHTS.get(source, _DEFAULT_SOURCE_WEIGHT)
    raw = content_score * weight + _recency_bonus(pub_date) + _keyword_bonus(title)
    return round(raw / _RAW_SCORE_MAX * 100, 1)


# ─────────────────────────────────────────────
# LLM Prompt（只問內容重要性，不問日期/來源）
# ─────────────────────────────────────────────
RESEARCHER_SYSTEM_PROMPT = """你是 AI 新聞內容重要性評估員。

對每則新聞的「內容本身」評分（0-10），只看內容，不考慮日期與來源：
- 10：技術突破或重大產品發布（新模型架構、能力大幅躍進）
- 7-9：有意義的技術進展、值得關注的公司重大動態
- 4-6：一般業界消息、有討論度但不突出
- 0-3：農場文、廣告、無實質技術內容、模糊標題

輸出 JSON，格式如下，不要有任何其他文字：
{"scores": [{"url": "來源網址", "score": 8, "reason": "10字內說明"}]}"""


# ─────────────────────────────────────────────
# COLLECT 層：RSS + Tavily
# ─────────────────────────────────────────────
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-news-bot/1.0)"}


def _fetch_rss(name: str, url: str) -> list[dict]:
    """抓取單一 RSS 來源，只保留 48 小時內的文章"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=_CUTOFF_HOURS)
        items = []
        for item in root.findall(".//item")[:10]:  # 每個來源最多取 10 則
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "").strip()
            pub   = item.findtext("pubDate", "").strip()
            if not (title and link):
                continue
            # 日期過濾：48 小時內才保留
            pub_dt = None
            if pub:
                try:
                    pub_dt = parsedate_to_datetime(pub)
                    if pub_dt < cutoff:
                        continue  # 太舊，跳過
                except Exception:
                    pass  # 日期解析失敗則保留（寧可多取）
            items.append({
                "title": title,
                "url": link,
                "source": name,
                "description": desc[:300],
                "pub_date": pub_dt.isoformat() if pub_dt else "",
                "date_found": now.date().isoformat(),
            })
        return items
    except Exception:
        return []


def _fetch_tavily() -> list[dict]:
    """Tavily 搜尋補充（覆蓋 RSS 可能漏掉的台灣新聞）"""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = search_tool.invoke(f"AI artificial intelligence news {today}")
        if isinstance(results, list):
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "source": "Tavily",
                    "description": r.get("content", "")[:300],
                    "pub_date": "",
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
    COLLECT → 規則預篩 → 去重 → 時間排序 → LLM 內容評分 → Python 綜合評分 → 輸出 raw_news
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

    # Step 4：按發布時間降序排序，確保最新文章優先進入 LLM 候選池
    deduped.sort(key=lambda x: x.get("pub_date", ""), reverse=True)

    # Step 5：LLM 內容評分（只評估內容重要性，0-10）
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0   # 評分任務需要確定性輸出
    )

    candidates = deduped[:20]
    # LLM 只需要標題和摘要，不需要日期/來源（Python 已處理）
    news_text = "\n".join(
        f"{i+1}. 標題：{item['title']}\n   URL：{item['url']}\n   摘要：{item['description'][:150]}"
        for i, item in enumerate(candidates)
    )

    messages = [
        SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
        HumanMessage(content=f"請評估以下新聞的內容重要性：\n\n{news_text}")
    ]

    response = llm.invoke(messages)
    content_scores: dict[str, float] = {}  # url → content_score
    try:
        raw = response.content
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        result = json.loads(raw)
        for entry in result.get("scores", []):
            url = entry.get("url", "")
            score = float(entry.get("score", 0))
            if url:
                content_scores[url] = max(0.0, min(10.0, score))
    except (json.JSONDecodeError, ValueError, TypeError):
        # fallback：所有候選給 content_score = 5（中等）
        for item in candidates:
            content_scores[item["url"]] = 5.0

    # Step 6：Python 綜合評分（四維度合併）
    scored = []
    for item in candidates:
        url = item["url"]
        content_score = content_scores.get(url, 5.0)
        final_score = _compute_final_score(
            content_score=content_score,
            source=item["source"],
            pub_date=item.get("pub_date", ""),
            title=item["title"],
        )
        if final_score >= _FINAL_SCORE_THRESHOLD:
            scored.append({
                "title": item["title"],
                "url": url,
                "source": item["source"],
                "summary": item["description"],
                "importance_score": final_score,
                "category": "產業動態",   # Translator 後由 Deep Researcher 精確分類
                "why_important": "",
                "pub_date": item.get("pub_date", ""),
            })

    # 按最終分數降序，最多取 5 則
    scored.sort(key=lambda x: x["importance_score"], reverse=True)
    selected = scored[:5]

    # fallback：若全部低於閾值，取分數最高的前 3 則（確保流程不中斷）
    if not selected:
        for item in candidates:
            url = item["url"]
            content_score = content_scores.get(url, 5.0)
            final_score = _compute_final_score(
                content_score=content_score,
                source=item["source"],
                pub_date=item.get("pub_date", ""),
                title=item["title"],
            )
            scored.append({
                "title": item["title"],
                "url": url,
                "source": item["source"],
                "summary": item["description"],
                "importance_score": final_score,
                "category": "產業動態",
                "why_important": "",
                "pub_date": item.get("pub_date", ""),
            })
        scored.sort(key=lambda x: x["importance_score"], reverse=True)
        selected = scored[:3]

    return {
        **state,
        "raw_news": selected,
        "revision_count": 0,
        "research_analysis": "",
        "error": ""
    }
