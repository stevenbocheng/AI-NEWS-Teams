"""
Media Reviewer：LLM 媒體品質審核節點
評估圖片/影片的生成 prompt 與文章主題的契合度（0-10 分）
不需視覺能力，純文字審核 prompt 是否合適
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger
from src.graph.workflow import NewsState
from config.settings import settings

REVIEWER_SYSTEM_PROMPT = """你是一位媒體內容審核員，負責評估圖片/影片的生成 prompt 是否與文章主題匹配。

## 評分標準

### 圖片 prompt（0-10 分）
- 10 分：prompt 準確反映文章核心主題，視覺化概念清晰，商業風格適合科技新聞
- 7-9 分：主題相關，但細節不夠精確
- 4-6 分：過於籠統，與文章主題弱相關
- 0-3 分：與文章主題無關，或包含不適當內容

### 影片 prompt（0-10 分）
- 10 分：動態視覺概念與文章主題高度契合，適合短影片呈現
- 7-9 分：主題相關，但動態表現不夠具體
- 4-6 分：靜態感強，不適合影片格式
- 0-3 分：與文章主題無關

## 判斷是否合適
- suitable=true：分數 >= 6
- suitable=false：分數 < 6

## 輸出格式（必須是合法 JSON）
{
  "image_score": 8,
  "image_suitable": true,
  "video_score": 0,
  "video_suitable": true,
  "reason": "圖片 prompt 精確描述了 AI 晶片主題；無影片需審核"
}

注意：若無對應媒體（prompt 為空字串），該項 score=0、suitable=true（視為不需審核，直接通過）"""


def media_reviewer_node(state: NewsState) -> NewsState:
    """
    Media Reviewer 節點
    審核最新一次生成的圖片/影片 prompt 是否合適
    並從所有 candidates 中挑選最高分者設定為最終路徑
    """
    image_candidates = list(state.get("image_candidates", []))
    video_candidates = list(state.get("video_candidates", []))
    media_decision = state.get("media_decision", {})
    metadata = state.get("metadata", {})

    # 若無任何候選，直接跳過
    if not image_candidates and not video_candidates:
        return state

    latest_img = image_candidates[-1] if image_candidates else {}
    latest_vid = video_candidates[-1] if video_candidates else {}

    image_prompt = latest_img.get("prompt", "")
    video_prompt = latest_vid.get("prompt", "")

    title = metadata.get("title", "")
    tags = metadata.get("tags", [])

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.1,
    )

    user_content = (
        f"文章標題：{title}\n"
        f"文章標籤：{', '.join(tags)}\n\n"
        f"圖片 prompt：{image_prompt or '（無）'}\n"
        f"影片 prompt：{video_prompt or '（無）'}"
    )

    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=f"請審核以下媒體 prompt 並輸出 JSON：\n\n{user_content}"),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        result = json.loads(content)
    except Exception as e:
        logger.warning(f"媒體審核 JSON 解析失敗：{e}，預設通過")
        result = {
            "image_score": 7, "image_suitable": True,
            "video_score": 7, "video_suitable": True,
            "reason": "解析失敗，預設通過",
        }

    img_score = result.get("image_score", 0)
    img_suitable = result.get("image_suitable", True)
    vid_score = result.get("video_score", 0)
    vid_suitable = result.get("video_suitable", True)
    reason = result.get("reason", "")

    logger.info(
        f"媒體審核結果 — 圖片：{img_score}/10（{'✓' if img_suitable else '✗'}）"
        f" 影片：{vid_score}/10（{'✓' if vid_suitable else '✗'}）— {reason}"
    )

    # 更新最新候選的分數與 suitable 標記
    if image_candidates:
        image_candidates[-1]["score"] = img_score
        image_candidates[-1]["suitable"] = img_suitable

    if video_candidates:
        video_candidates[-1]["score"] = vid_score
        video_candidates[-1]["suitable"] = vid_suitable

    # 從所有 candidates 挑最高分（有效路徑才算）
    valid_imgs = [c for c in image_candidates if c.get("path")]
    valid_vids = [c for c in video_candidates if c.get("path")]

    best_img = max(valid_imgs, key=lambda x: x.get("score", 0), default={})
    best_vid = max(valid_vids, key=lambda x: x.get("score", 0), default={})

    image_path = best_img.get("path", "")
    video_path = best_vid.get("path", "")

    return {
        **state,
        "image_candidates": image_candidates,
        "video_candidates": video_candidates,
        "image_path": image_path,
        "video_path": video_path,
    }
