"""
Agent A2：深度研究員
整合 deep-research skill（ECC 版 + awesome-llm-apps 版合併）

流程（嚴格遵守 deep-research 品質規則）：
  1. 將新聞主題拆解為 3-5 個子問題（含來源可信度目標）
  2. 每個子問題執行獨立 Tavily 搜尋（多關鍵字變體）
  3. 為每個來源標注可信度等級（高/中/一般）
  4. 去重並建立編號來源清單
  5. 合成：每個聲明必須有來源支撐，標記不確定資訊
  6. 輸出結構化研究報告供 Writer 使用

品質規則（merged ECC + awesome-llm-apps）：
  - 每個聲明必須有來源，格式：[聲明]（[來源]）或 [1][2] 編號
  - 只有一個來源時標記為「未交叉驗證」
  - 優先近 12 個月的資料
  - 找不到資訊時直接說「資料不足」
  - 明確區分事實、推論、觀點
  - 標注來源可信度：高（學術/官方）/ 中（科技媒體）/ 一般
  - 列出 Areas of Consensus、Areas of Debate
  - 列出資訊缺口（Gaps）
"""
import json
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.tools.search import search_tool
from src.graph.workflow import NewsState
from config.settings import settings


# ---------------------------------------------------------------------------
# 來源可信度分類（awesome-llm-apps SKILL 的 Source Evaluation Criteria）
# ---------------------------------------------------------------------------

_HIGH_CREDIBILITY = {
    "nature.com", "science.org", "arxiv.org", "openai.com", "anthropic.com",
    "deepmind.com", "research.google", "microsoft.com", "mit.edu", "stanford.edu",
    "reuters.com", "apnews.com", "bbc.com", "nytimes.com", "wsj.com",
    "ieee.org", "acm.org", "nejm.org", "science.org",
}

_MEDIUM_CREDIBILITY = {
    "techcrunch.com", "venturebeat.com", "wired.com", "theverge.com",
    "arstechnica.com", "technologyreview.mit.edu", "zdnet.com",
    "ithome.com.tw", "bnext.com.tw", "inside.com.tw", "technews.tw",
    "cw.com.tw", "businessweekly.com.tw", "blocktempo.com",
}


def _get_credibility(url: str) -> str:
    """根據網域判斷來源可信度等級"""
    try:
        domain = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return "一般（建議自行驗證）"

    if any(domain == h or domain.endswith("." + h) for h in _HIGH_CREDIBILITY):
        return "高（學術/官方/可信媒體）"
    if any(domain == m or domain.endswith("." + m) for m in _MEDIUM_CREDIBILITY):
        return "中（科技媒體）"
    return "一般（建議自行驗證）"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PLANNER_PROMPT = """你是深度研究規劃師。給你一組 AI 新聞，請規劃 3-5 個研究子問題，讓我能對這則新聞做全面深度分析。

子問題應涵蓋不同角度，例如：
- 技術原理：這項技術如何運作？有何限制？
- 市場影響：誰受益？誰受威脅？市場規模？
- 競爭格局：競爭者是誰？現有解法比較？
- 批評與風險：有哪些疑慮、倫理爭議、技術限制？
- 台灣視角：對台灣科技業、用戶、政策有何影響？

輸出 JSON：
{
  "topic": "核心主題一句話",
  "sub_questions": [
    {
      "question": "子問題1",
      "search_query_en": "英文搜尋詞",
      "search_query_zh": "中文搜尋詞",
      "credibility_target": "優先學術來源" 或 "優先新聞來源" 或 "綜合來源"
    }
  ]
}"""


SYNTHESIZER_PROMPT = """你是 AI 科技深度研究分析師，根據多輪搜尋結果合成一份供台灣媒體撰稿人使用的研究報告。

嚴格遵守以下品質規則：
1. 每個聲明必須有來源，使用編號引用格式：「[聲明內容] [1]」或「[聲明內容]（[來源名稱] [2]）」
2. 只有一個來源的資訊，標注「*未交叉驗證*」
3. 優先使用近 12 個月的資料，舊資料須標注年份
4. 找不到可靠資訊時直接說「資料不足，建議撰稿時省略」
5. 明確區分：事實 vs. 推論（「根據現有資料推測…」）vs. 觀點（「X 方認為…」）
6. 來源可信度等級：高（學術/官方）、中（科技媒體）、一般（建議自行驗證）

輸出格式（繁體中文）：

# [主題]：深度研究報告
*生成時間：[今天日期] | 來源數：[N] | 信心等級：高/中/低*

## 執行摘要
[3-5 句話概述核心發現]

## 主要發現
- **[發現1]**：[簡要說明] [1]
- **[發現2]**：[簡要說明] [2]
- **[發現3]**：[簡要說明] [3]

## 1. 技術背景
[技術原理，含具體來源引用，200字內]

## 2. 市場與產業影響
[具體數據與影響分析，含來源]

## 3. 競爭格局
[主要玩家比較，含來源]

## 4. 批評與風險
[疑慮、限制、爭議，有不同觀點時並陳]

## 5. 台灣視角
[對台灣科技業/用戶/政策的具體影響]

## 共識領域（Areas of Consensus）
[多個來源一致認同的觀點]

## 爭議領域（Areas of Debate）
[來源之間存在分歧或不確定的觀點]

## 關鍵洞察（給撰稿人）
- [最值得深入的獨特角度]
- [讀者最可能想知道的問題]
- [一個反直覺或容易被忽略的面向]

## 資訊缺口（Gaps）
[列出找不到可靠資料的面向，讓撰稿人避免無中生有]

## 來源清單
[N 個來源，格式如下，已提供在輸入中]"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _plan_sub_questions(llm: ChatOpenAI, raw_news: list[dict]) -> dict:
    """Step 1：規劃 3-5 個研究子問題"""
    news_text = json.dumps(raw_news[:3], ensure_ascii=False, indent=2)
    messages = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=f"請為以下新聞規劃深度研究子問題：\n\n{news_text}")
    ]
    response = llm.invoke(messages)
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return {
            "topic": "AI 科技動態",
            "sub_questions": [
                {"question": "技術原理", "search_query_en": "AI technology details", "search_query_zh": "人工智慧 技術", "credibility_target": "優先學術來源"},
                {"question": "產業影響", "search_query_en": "AI industry impact 2026", "search_query_zh": "AI 產業影響", "credibility_target": "綜合來源"},
                {"question": "台灣視角", "search_query_en": "AI Taiwan impact", "search_query_zh": "AI 台灣", "credibility_target": "優先新聞來源"},
            ]
        }


def _search_sub_question(sq: dict) -> tuple[str, list[dict]]:
    """Step 2：每個子問題執行多關鍵字搜尋，並標注來源可信度

    Returns:
        tuple: (formatted_text, source_list)
            source_list items: {"title": str, "url": str, "credibility": str, "snippet": str}
    """
    results_parts = []
    source_list = []

    for query in [sq.get("search_query_en", ""), sq.get("search_query_zh", "")]:
        if not query:
            continue
        try:
            results = search_tool.invoke(query)
            if isinstance(results, list):
                for r in results[:3]:
                    title = r.get("title", "")
                    url = r.get("url", "")
                    content = r.get("content", "")[:400]
                    if title and url:
                        credibility = _get_credibility(url)
                        results_parts.append(
                            f"**{title}**\n來源：{url}\n可信度：{credibility}\n{content}"
                        )
                        source_list.append({
                            "title": title,
                            "url": url,
                            "credibility": credibility,
                            "snippet": content[:150],
                        })
        except Exception:
            pass

    question = sq.get("question", "")
    if results_parts:
        text = f"### {question}\n\n" + "\n\n---\n\n".join(results_parts)
    else:
        text = f"### {question}\n\n資料不足"

    return text, source_list


def _deduplicate_sources(all_sources: list[dict]) -> list[dict]:
    """去除重複 URL，保留首次出現的來源"""
    seen_urls = set()
    unique = []
    for src in all_sources:
        url = src.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(src)
    return unique


def _format_source_list(sources: list[dict]) -> str:
    """將來源清單格式化為編號列表，提供給 LLM 參考"""
    lines = []
    for i, src in enumerate(sources, 1):
        title = src.get("title", "未知標題")
        url = src.get("url", "")
        credibility = src.get("credibility", "一般")
        snippet = src.get("snippet", "")
        lines.append(f"[{i}] {title} — {url}\n    可信度：{credibility}\n    摘要：{snippet}")
    return "\n\n".join(lines) if lines else "無可用來源"


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def deep_researcher_node(state: NewsState) -> NewsState:
    """
    Deep Researcher Agent 節點

    deep-research 工作流（ECC + awesome-llm-apps 合併版）：
      Plan sub-questions → Multi-source search with credibility tagging
      → Deduplicate sources → Synthesize with quality rules + consensus/debate/gaps
    """
    raw_news = state.get("raw_news", [])
    if not raw_news:
        return {**state, "research_analysis": "無原始新聞，跳過深度研究。"}

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.2
    )

    # Step 1：拆解子問題
    plan = _plan_sub_questions(llm, raw_news)
    sub_questions = plan.get("sub_questions", [])

    # Step 2：每個子問題獨立搜尋（最多 4 個，控制成本）
    search_result_texts = []
    all_sources: list[dict] = []

    for sq in sub_questions[:4]:
        result_text, source_list = _search_sub_question(sq)
        search_result_texts.append(result_text)
        all_sources.extend(source_list)

    # Step 3：去重來源並建立編號清單
    unique_sources = _deduplicate_sources(all_sources)
    formatted_sources = _format_source_list(unique_sources)

    all_results = "\n\n".join(search_result_texts)
    topic = plan.get("topic", "AI 科技動態")

    # Step 4：合成研究報告（遵守品質規則）
    from datetime import date
    today = date.today().isoformat()

    messages = [
        SystemMessage(content=SYNTHESIZER_PROMPT),
        HumanMessage(content=(
            f"今天日期：{today}\n"
            f"研究主題：{topic}\n\n"
            f"原始新聞：\n{json.dumps(raw_news[:3], ensure_ascii=False)}\n\n"
            f"子問題搜尋結果：\n{all_results}\n\n"
            f"來源清單（請使用此編號引用，勿自行發明來源）：\n{formatted_sources}"
        ))
    ]

    response = llm.invoke(messages)

    return {
        **state,
        "research_analysis": response.content,
        "error": ""
    }
