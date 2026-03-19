"""
主程式入口
整合所有模組，執行完整的 AI 新聞自動發佈流程
"""
import sys
import os
from datetime import datetime
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# 確保 src 路徑可用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_logging():
    """配置日誌"""
    from config.settings import settings

    os.makedirs(settings.LOGS_DIR, exist_ok=True)
    log_file = os.path.join(
        settings.LOGS_DIR,
        f"{datetime.now().strftime('%Y-%m-%d')}.log"
    )

    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    logger.add(log_file, level="DEBUG", rotation="1 day", retention="30 days")


def _write_job_summary(result: dict, error: str = "") -> None:
    """將執行結果寫入 GitHub Actions Job Summary（$GITHUB_STEP_SUMMARY）
    本機執行時環境變數不存在，靜默跳過。
    """
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    metadata = result.get("metadata", {})
    review = metadata.get("_review", {})
    scores = review.get("scores", {})
    issues = review.get("issues", [])
    quality_score = result.get("quality_score", 0.0)
    raw_news = result.get("raw_news", [])
    published_filename = result.get("published_filename", "")
    image_path = result.get("image_path", "")
    video_path = result.get("video_path", "")

    # 發佈狀態
    if error:
        status = f"❌ 失敗：{error}"
    elif not published_filename:
        status = "⚠️ 跳過（重複新聞）"
    else:
        status = "✅ 成功"

    # 媒體狀態
    media_status = "—"
    if image_path and video_path:
        media_status = "🖼️ 圖片 + 🎬 影片"
    elif image_path:
        media_status = "🖼️ 圖片"
    elif video_path:
        media_status = "🎬 影片"
    elif result.get("media_decision"):
        media_status = "⚠️ 生成失敗或未設定 HF_TOKEN"

    lines = [
        f"## AI 新聞自動發佈報告 — {today}",
        "",
        "| 項目 | 結果 |",
        "|------|------|",
        f"| 收集新聞數 | {len(raw_news)} 則 |",
        f"| 文章品質分數 | {quality_score:.1f} / 10 |",
        f"| 發佈狀態 | {status} |",
        f"| 發佈檔案 | {published_filename or '—'} |",
        f"| 媒體生成 | {media_status} |",
        "",
    ]

    if scores:
        score_map = {
            "content_quality": "內容品質",
            "language_quality": "語言品質",
            "format_compliance": "格式規範",
            "title_appeal": "標題吸引力",
            "human_writing": "AI 寫作痕跡",
        }
        lines += [
            "### 品質評分細項",
            "| 維度 | 分數 |",
            "|------|------|",
        ]
        for key, label in score_map.items():
            val = scores.get(key, "—")
            lines.append(f"| {label} | {val}/10 |")
        lines.append("")

    if issues:
        lines.append("### 發現的問題")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")

    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logger.warning(f"寫入 Job Summary 失敗：{e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
def run_workflow():
    """執行 LangGraph 工作流（含指數退避重試）"""
    from src.graph.workflow import workflow, NewsState

    initial_state: NewsState = {
        "raw_news": [],
        "research_analysis": "",
        "draft_article": "",
        "final_article": "",
        "quality_score": 0.0,
        "revision_count": 0,
        "metadata": {},
        "published_filename": "",
        "error": "",
        # 媒體生成欄位
        "media_decision": {},
        "image_candidates": [],
        "video_candidates": [],
        "media_revision_count": 0,
        "image_path": "",
        "video_path": "",
    }

    logger.info("開始執行 AI 新聞自動發佈流程...")
    result = workflow.invoke(initial_state)

    error = result.get("error", "")
    if error:
        # 授權/永久性錯誤不重試（重試也沒用）
        non_retryable = ("403", "401", "404")
        if any(k in error for k in non_retryable):
            return result  # 直接回傳，讓 main() 處理
        raise RuntimeError(f"工作流執行失敗：{error}")

    return result


def main():
    setup_logging()
    logger.info(f"=== AI 新聞自動發佈系統啟動 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ===")

    # 驗證設定
    from config.settings import settings
    try:
        settings.validate()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # 執行工作流
    result = {}
    error_msg = ""
    try:
        result = run_workflow()
        score = result.get("quality_score", 0)
        published = result.get("published_filename", "")
        if published:
            logger.success(f"發佈成功！文章品質評分：{score:.1f}/10 → {published}")
        else:
            logger.info(f"跳過發佈（重複新聞）。品質評分：{score:.1f}/10")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"最終失敗（已重試 3 次）：{e}")
    finally:
        _write_job_summary(result, error=error_msg)

    if error_msg:
        sys.exit(1)


if __name__ == "__main__":
    main()
