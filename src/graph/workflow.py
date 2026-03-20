"""
LangGraph 工作流定義
節點：researcher → translator → deep_researcher → writer
      → manager → media_generator → media_reviewer → publisher
"""
from typing import TypedDict
from langgraph.graph import StateGraph, END


class NewsState(TypedDict):
    """節點間共享的狀態"""
    raw_news: list[dict]          # Researcher 收集的原始新聞
    research_analysis: str        # Deep Researcher 的深度分析報告
    draft_article: str            # Writer 撰寫的草稿（已含 Humanizer + Editor）
    final_article: str            # Manager 審核通過的最終文章
    quality_score: float          # 品質評分（0-10）
    revision_count: int           # 修改次數（避免無限迴圈）
    metadata: dict                # 標題、日期、標籤、slug 等
    published_filename: str       # Publisher 寫入的發佈檔名（供 Job Summary 使用）
    error: str                    # 錯誤訊息（若有）
    # 媒體生成相關欄位
    media_decision: dict          # Manager 的媒體決定 {generate_image, generate_video, prompts}
    image_candidates: list[dict]  # [{prompt, path, score, suitable}, ...]
    video_candidates: list[dict]  # [{prompt, path, score, suitable}, ...]
    media_revision_count: int     # 媒體生成次數（上限 3）
    image_path: str               # 最終選定的圖片本地路徑
    video_path: str               # 最終選定的影片本地路徑（可為空）


def should_revise(state: NewsState) -> str:
    """
    條件邊：Manager 評分不足時退回 Writer 重寫
    最多重試 MAX_REVISION_COUNT 次
    若 error 非空則直接終止，不發佈
    """
    from config.settings import settings

    if state.get("error"):
        return END

    if (
        state["quality_score"] < settings.MIN_QUALITY_SCORE
        and state["revision_count"] < settings.MAX_REVISION_COUNT
    ):
        return "writer"
    return "media_generator"


def should_regenerate_media(state: NewsState) -> str:
    """
    條件邊：media_reviewer 審核後決定是否重新生成
    若任一媒體不合適且未達上限（3 次）→ 重新生成
    否則 → publisher
    """
    image_candidates = state.get("image_candidates", [])
    video_candidates = state.get("video_candidates", [])
    revision_count = state.get("media_revision_count", 0)

    latest_img = image_candidates[-1] if image_candidates else {}
    latest_vid = video_candidates[-1] if video_candidates else {}

    img_ok = latest_img.get("suitable", True)
    vid_ok = latest_vid.get("suitable", True) if video_candidates else True

    if (not img_ok or not vid_ok) and revision_count < 3:
        return "media_generator"
    return "publisher"


def build_workflow():
    """建立並編譯 LangGraph 工作流"""
    from src.agents.researcher import researcher_node
    from src.agents.translator import translator_node
    from src.agents.deep_researcher import deep_researcher_node
    from src.agents.writer import writer_node
    from src.agents.manager import manager_node
    from src.agents.media_generator import media_generator_node
    from src.agents.media_reviewer import media_reviewer_node
    from src.tools.publisher import publisher_node

    graph = StateGraph(NewsState)

    # 加入節點
    graph.add_node("researcher", researcher_node)
    graph.add_node("translator", translator_node)
    graph.add_node("deep_researcher", deep_researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("manager", manager_node)
    graph.add_node("media_generator", media_generator_node)
    graph.add_node("media_reviewer", media_reviewer_node)
    graph.add_node("publisher", publisher_node)

    # 定義線性邊
    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "translator")        # 收集 → 翻譯
    graph.add_edge("translator", "deep_researcher")   # 翻譯 → 深度研究
    graph.add_edge("deep_researcher", "writer")       # 深度研究 → 撰寫
    graph.add_edge("writer", "manager")
    graph.add_edge("media_generator", "media_reviewer")

    # 條件邊：品質不足 → 退回 Writer；通過 → 媒體生成（或直接終止）
    graph.add_conditional_edges(
        "manager",
        should_revise,
        {
            "writer": "writer",
            "media_generator": "media_generator",
            END: END,
        }
    )

    # 條件邊：媒體不合適且未達上限 → 重新生成；否則 → 發佈
    graph.add_conditional_edges(
        "media_reviewer",
        should_regenerate_media,
        {
            "media_generator": "media_generator",
            "publisher": "publisher",
        }
    )

    graph.add_edge("publisher", END)

    return graph.compile()


def build_article_workflow():
    """子工作流：跳過 Researcher，從 Translator 開始（用於多篇逐一發佈）"""
    from src.agents.translator import translator_node
    from src.agents.deep_researcher import deep_researcher_node
    from src.agents.writer import writer_node
    from src.agents.manager import manager_node
    from src.agents.media_generator import media_generator_node
    from src.agents.media_reviewer import media_reviewer_node
    from src.tools.publisher import publisher_node

    graph = StateGraph(NewsState)

    graph.add_node("translator", translator_node)
    graph.add_node("deep_researcher", deep_researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("manager", manager_node)
    graph.add_node("media_generator", media_generator_node)
    graph.add_node("media_reviewer", media_reviewer_node)
    graph.add_node("publisher", publisher_node)

    graph.set_entry_point("translator")
    graph.add_edge("translator", "deep_researcher")
    graph.add_edge("deep_researcher", "writer")
    graph.add_edge("writer", "manager")
    graph.add_edge("media_generator", "media_reviewer")

    graph.add_conditional_edges(
        "manager",
        should_revise,
        {
            "writer": "writer",
            "media_generator": "media_generator",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "media_reviewer",
        should_regenerate_media,
        {
            "media_generator": "media_generator",
            "publisher": "publisher",
        }
    )

    graph.add_edge("publisher", END)

    return graph.compile()


# 建立工作流實例
workflow = build_workflow()
