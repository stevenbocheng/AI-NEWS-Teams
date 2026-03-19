"""
Agent C：品質守門員
審核文章品質、校正台灣慣用語、生成 metadata
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.graph.workflow import NewsState
from src.utils.language_filter import filter_taiwan_terms
from config.settings import settings

MANAGER_SYSTEM_PROMPT = """你是一位嚴格的繁體中文科技媒體總編輯，負責最終品質把關，並決定文章的媒體配置。

## 評分規則（5 個維度，每項 0-10 分，最終取平均）

### 1. 內容品質（0-10 分）
- 10 分：有具體數據、明確技術細節、清楚說明對讀者的影響
- 7-9 分：資訊正確但部分細節模糊
- 4-6 分：內容空洞、泛泛而談、缺乏實質資訊
- 0-3 分：資訊錯誤、或幾乎沒有實質內容

### 2. 語言品質（0-10 分）
- 10 分：流暢自然、無任何大陸用語、無語病
- 7-9 分：整體流暢，偶有1-2處用詞不夠精準
- 4-6 分：有明顯大陸用語（智能/軟件/優化/網絡等）或語句不通順
- 0-3 分：大量大陸用語或語句嚴重不通順

### 3. 格式規範（0-10 分）
- 10 分：結構完整（標題/前言/重點/分析/結語/來源），Markdown 語法無誤
- 7-9 分：結構大致完整，但缺少 1 個段落
- 4-6 分：缺少 2 個以上段落，或 Markdown 語法有錯誤
- 0-3 分：格式混亂或完全不符合規範

### 4. 標題吸引力（0-10 分）
- 10 分：包含具體關鍵字、20 字以內、有新聞價值感
- 7-9 分：標題合理但缺乏吸引力
- 4-6 分：標題過於籠統（如「AI 最新進展」）或超過 20 字
- 0-3 分：標題完全不符合新聞標題格式

### 5. AI 寫作痕跡（0-10 分）
- 10 分：讀起來像真人撰寫，無任何 AI 腔調
- 7-9 分：偶有 1-2 個 AI 慣用詞（「此外」「至關重要」「彰顯」等）
- 4-6 分：明顯 AI 腔調，有三段式法則、誇大意義、模糊歸因等問題
- 0-3 分：充滿 AI 套語，完全像機器產出

## 媒體決策規則

審核完文章後，依新聞重要性決定媒體配置：

- **generate_image=true**：有實質技術內容、值得視覺化的文章（絕大多數文章）
- **generate_image=false**：純人事任命、純政策聲明、或文章品質不足不值得發佈
- **generate_video=true**：重大發布（主要模型/產品發表）、突破性研究成果、重要產業事件
- **generate_video=false**：一般更新、小幅改進、分析評論類文章

圖片 prompt 格式：Business technology concept illustration about {30字以內的主題描述},
modern flat design, professional, neutral colors, corporate style,
absolutely no text, no logos, no watermarks, high quality

影片 prompt 格式：與圖片 prompt 相同結構，但強調動態視覺概念（如光流、數據流動、介面互動等）

## 輸出格式（必須是合法 JSON）

{
  "scores": {
    "content_quality": 8,
    "language_quality": 9,
    "format_compliance": 8,
    "title_appeal": 7,
    "human_writing": 8
  },
  "quality_score": 8.0,
  "issues": ["具體問題描述1", "具體問題描述2"],
  "corrected_article": "（已校正的完整文章 Markdown 內容）",
  "metadata": {
    "title": "文章標題（與文章內標題一致）",
    "slug": "article-title-in-english-kebab-case",
    "categories": ["AI", "科技新聞"],
    "tags": ["具體技術名稱", "公司名稱"],
    "description": "給搜尋引擎看的文章描述，150字以內，不含 Markdown 語法"
  },
  "media_decision": {
    "generate_image": true,
    "generate_video": false,
    "image_prompt": "Business technology concept illustration about ...",
    "video_prompt": "",
    "reason": "一般科技新聞，配圖即可；非重大突破，不需影片"
  }
}

注意：
- quality_score = scores 五項的平均值，自行計算
- 即使有小問題，也直接在 corrected_article 中修正，不退回重寫
- 只有 quality_score < {min_score} 且屬於根本性問題（內容錯誤/格式崩壞）才退回
- issues 列表要具體，例如「第三段使用了『優化』應改為『最佳化』」而非「有大陸用語」
- 不需要影片時，video_prompt 填空字串 ""，generate_video=false"""


def manager_node(state: NewsState) -> NewsState:
    """Manager Agent 節點"""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.1  # 審核時需要一致性，降低隨機性
    )

    draft = state.get("draft_article", "")

    # 先用靜態詞彙表做一輪過濾
    pre_filtered = filter_taiwan_terms(draft)

    prompt = MANAGER_SYSTEM_PROMPT.replace("{min_score}", str(settings.MIN_QUALITY_SCORE))

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"請審核以下文章並輸出 JSON 結果：\n\n{pre_filtered}")
    ]

    response = llm.invoke(messages)

    # 解析 JSON 輸出
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        # 優先使用 LLM 計算的平均分，fallback 到自行計算
        quality_score = float(result.get("quality_score", 0))
        if quality_score == 0 and "scores" in result:
            scores = result["scores"].values()
            quality_score = sum(scores) / len(scores) if scores else 0.0

        final_article = result.get("corrected_article", pre_filtered)
        metadata = result.get("metadata", {})
        issues = result.get("issues", [])
        scores = result.get("scores", {})
        media_decision = result.get("media_decision", {})

    except (json.JSONDecodeError, ValueError):
        quality_score = 5.0
        final_article = pre_filtered
        metadata = {}
        issues = ["JSON 解析失敗，使用預設評分"]
        scores = {}
        media_decision = {}

    return {
        **state,
        "final_article": final_article,
        "quality_score": quality_score,
        "media_decision": media_decision,
        "metadata": {
            **metadata,
            "_review": {"scores": scores, "issues": issues}  # 供 debug 用
        }
    }
