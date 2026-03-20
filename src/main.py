"""
主程式入口
整合所有模組，執行完整的 AI 新聞自動發佈流程

每次執行流程：
  1. Researcher 抓取並篩選今日 AI 新聞（最多 5 則，評分 ≥ 70/100）
  2. 對每則新聞逐一執行：Translator → Deep Researcher → Writer → Manager → Media → Publisher
  3. 品質評分 ≥ 6.0/10 才發佈，上限 5 篇/天
  4. Publisher 自動去重（同來源 URL 不重複發佈）
"""
import sys
import os
from datetime import datetime
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAX_ARTICLES_PER_RUN = None  # 從 settings 讀取，見 run_pipeline()


def setup_logging():
    from config.settings import settings
    os.makedirs(settings.LOGS_DIR, exist_ok=True)
    log_file = os.path.join(
        settings.LOGS_DIR,
        f"{datetime.now().strftime('%Y-%m-%d')}.log"
    )
    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    logger.add(log_file, level="DEBUG", rotation="1 day", retention="30 days")


def _write_job_summary(results: list[dict], error: str = "") -> None:
    """將執行結果寫入 GitHub Actions Job Summary（$GITHUB_STEP_SUMMARY）"""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    published = [r for r in results if r.get("published_filename")]

    if error:
        status = f"❌ 失敗：{error}"
    elif not results:
        status = "⚠️ 無可用新聞或全部為重複"
    else:
        status = f"✅ 成功發佈 {len(published)} 篇"

    lines = [
        f"## AI 新聞自動發佈報告 — {today}",
        "",
        "| 項目 | 結果 |",
        "|------|------|",
        f"| 發佈狀態 | {status} |",
        f"| 處理篇數 | {len(results)} 則 |",
        f"| 發佈篇數 | {len(published)} 篇 |",
        "",
    ]

    for i, r in enumerate(published, 1):
        fname = r.get("published_filename", "")
        score = r.get("quality_score", 0)
        title = r.get("metadata", {}).get("title", fname)
        image_path = r.get("image_path", "")
        video_path = r.get("video_path", "")
        media = "🖼️ 圖片" if image_path else ""
        if video_path:
            media = (media + " + 🎬 影片").strip(" +")
        lines += [
            f"### [{i}] {title}",
            f"- 品質分數：{score:.1f}/10",
            f"- 媒體：{media or '—'}",
            f"- 檔案：{fname}",
            "",
        ]

    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logger.warning(f"寫入 Job Summary 失敗：{e}")


def _make_initial_state() -> dict:
    return {
        "raw_news": [],
        "research_analysis": "",
        "draft_article": "",
        "final_article": "",
        "quality_score": 0.0,
        "revision_count": 0,
        "metadata": {},
        "published_filename": "",
        "error": "",
        "media_decision": {},
        "image_candidates": [],
        "video_candidates": [],
        "media_revision_count": 0,
        "image_path": "",
        "video_path": "",
    }


def run_pipeline() -> list[dict]:
    """
    執行完整發佈流水線：
      Researcher（一次） → 逐篇 Translator→DeepResearcher→Writer→Manager→Publisher
    回傳所有處理結果
    """
    # workflow 必須先載入（它會觸發 researcher 載入），避免循環導入
    from src.graph.workflow import build_article_workflow
    from src.agents.researcher import researcher_node
    from config.settings import settings
    from contextlib import nullcontext

    try:
        from langchain_community.callbacks import get_openai_callback
        cb_manager = get_openai_callback()
    except ImportError:
        get_openai_callback = None
        cb_manager = nullcontext()

    max_articles = settings.MAX_ARTICLES_PER_RUN

    with cb_manager as cb:
        # Step 1：Researcher 收集今日新聞
        logger.info("Researcher：收集並篩選今日 AI 新聞...")
        research_state = researcher_node(_make_initial_state())
        raw_news = research_state.get("raw_news", [])

        if not raw_news:
            err = research_state.get("error", "未找到 AI 相關新聞")
            logger.warning(f"Researcher 無結果：{err}")
            return []

        logger.info(
            f"Researcher 篩選出 {len(raw_news)} 則新聞，"
            f"開始逐篇處理（上限 {max_articles} 篇）"
        )

        article_workflow = build_article_workflow()
        results = []

        for i, news_item in enumerate(raw_news[:max_articles]):
            title_preview = news_item.get("title", "")[:60]
            score_preview = news_item.get("importance_score", 0)
            logger.info(
                f"[{i+1}/{min(len(raw_news), max_articles)}] "
                f"處理（重要性 {score_preview}）：{title_preview}"
            )

            article_state = {
                **_make_initial_state(),
                "raw_news": [news_item],
            }

            try:
                result = article_workflow.invoke(article_state)
            except Exception as e:
                logger.warning(f"  ✗ 例外：{e}")
                results.append({**article_state, "error": str(e), "published_filename": ""})
                continue

            results.append(result)

            error = result.get("error", "")
            published = result.get("published_filename", "")
            quality = result.get("quality_score", 0)

            if error and "重複" not in error:
                logger.warning(f"  ✗ 失敗：{error}")
            elif published:
                logger.success(f"  ✓ 發佈：{published}（品質 {quality:.1f}/10）")
            else:
                logger.info(f"  - 跳過（重複新聞或品質不足 {quality:.1f}/10）")

        published_count = sum(1 for r in results if r.get("published_filename"))
        logger.info(f"本次完成：{published_count}/{len(results)} 篇成功發佈")

    # Token 使用報告
    if get_openai_callback and cb is not None:
        logger.info("=" * 48)
        logger.info("=== Token 使用報告 ===")
        logger.info(f"  總 tokens      : {cb.total_tokens:>10,}")
        logger.info(f"  Prompt tokens  : {cb.prompt_tokens:>10,}")
        logger.info(f"  Completion     : {cb.completion_tokens:>10,}")
        logger.info(f"  預估費用       : ${cb.total_cost:>9.4f} USD")
        logger.info("=" * 48)

    return results


def main():
    setup_logging()
    logger.info(
        f"=== AI 新聞自動發佈系統啟動 "
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ==="
    )

    from config.settings import settings
    try:
        settings.validate()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    results = []
    error_msg = ""
    try:
        results = run_pipeline()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"執行失敗：{e}")
    finally:
        _write_job_summary(results, error=error_msg)

    if error_msg:
        sys.exit(1)


if __name__ == "__main__":
    main()
