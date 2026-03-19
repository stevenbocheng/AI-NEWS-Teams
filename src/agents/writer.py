"""
Agent B：內容主編
整合三個 skill：

  Step 1：撰寫草稿（article-writing skill）
    - 以具體事實/數據開場，不用套語
    - 禁用詞列表
    - 直接、低炒作的語氣

  Step 2：Humanizer（kevintsai1202/Humanizer-zh-TW）
    - 去除 AI 寫作痕跡

  Step 3：Editor（editor skill）
    - Copy Editing + Line Editing
    - 精簡冗詞、主動語態、段落流暢度
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.graph.workflow import NewsState
from config.settings import settings


# ─────────────────────────────────────────────
# Step 1：Writer Prompt
# 整合 article-writing skill (SKILL.md)
# ─────────────────────────────────────────────
WRITER_SYSTEM_PROMPT = """你是一位為台灣讀者撰寫 AI 科技新聞的主編。

## 寫作核心規則（article-writing skill）

1. **以具體事物開場**：第一段必須是一個具體的事實、數字、例子，或引用。禁止用抽象概念開場。
   - ❌「在人工智慧快速發展的今天……」
   - ✅「OpenAI 在週三發佈的技術報告顯示，GPT-5 在數學推理測試中的得分比前代高出 43%。」

2. **先給事實，再解釋**：每個段落先放證據，再說意義。不要先鋪墊再給重點。

3. **用具體數字**：有數字就用數字。「大幅提升」→「提升 43%」。

4. **禁用詞彙（一律不用）**：
   - 套語：「在……快速演進的今天」「這標誌著……」「隨著……的到來」
   - 炒作：「顛覆性」「革命性」「改變遊戲規則」「尖端」「創新突破」
   - 過渡詞：「此外」「不僅如此」「值得注意的是」「毋庸置疑」「顯而易見」
   - AI 套語：「深入探討」「至關重要」「充滿活力」「不斷演進的佈局」「多元面向」

5. **每個段落一個主題**：不要在同一段混入多個論點。

6. **語氣**：直接、務實、低炒作。像在跟一位懂科技的朋友說話，不像在寫公關稿。

## 文章結構

```
# [標題]（20字以內，含核心關鍵字，不用驚嘆號）

[前言：150字內，第一句就給最重要的事實]

## 重點整理
- [具體事實 1]
- [具體事實 2]
- [具體事實 3]（3-5 點）

## [主題一：技術背景]
[從研究報告中取出技術細節，有來源引用]

## [主題二：產業影響]
[具體影響，點名受益者/受威脅者]

## 不同聲音
[若有批評或質疑，併陳，不隱藏]

## 對台灣的意義
[具體說明，100字內]

## 參考來源
[列出研究報告提供的來源 URL]
```

## 不能做的事
- 不能捏造數字、公司聲明、或研究員的話
- 研究報告說「資料不足」的部分，就省略，不要填補
- 不能寫「未來展望」類的空泛結論，用具體的下一步代替"""


# ─────────────────────────────────────────────
# Step 2：Humanizer Prompt
# kevintsai1202/Humanizer-zh-TW skill
# ─────────────────────────────────────────────
HUMANIZER_SYSTEM_PROMPT = """你是文字編輯，去除繁體中文文章中的 AI 寫作痕跡，使文字更自然。

保留核心資訊與 Markdown 結構。修正以下問題：

**高頻 AI 詞彙（刪除或替換）：**
「此外」「至關重要」「深入探討」「強調」「持久的」「充滿活力的」「關鍵性的」
「彰顯」「展示了」「寶貴的」「標誌著」「見證了」「是……的體現」「奠定基礎」
「開創性的」「著名的」「令人讚嘆的」「迷人的」

**句子問題：**
- 模糊歸因「業界報告顯示」「專家認為」→ 具體來源或刪除
- 否定式排比「不僅……而且」→ 直接陳述
- 三段式並列 → 改為兩項
- 填充短語「值得注意的是」→ 直接說

**風格問題：**
- 破折號（—）過多 → 只在必要時用
- 粗體過多 → 只標重要術語
- 句子長度要有變化

直接輸出修改後完整文章，不需說明更改了什麼。"""


# ─────────────────────────────────────────────
# Step 3：Editor Prompt
# editor skill (SKILL.md)
# ─────────────────────────────────────────────
EDITOR_SYSTEM_PROMPT = """你是繁體中文文字編輯，執行 Copy Editing + Line Editing。只改語言，不加新內容。

**精簡度（Concision）：**
「由於……的事實」→「因為」
「在……情況下」→「如果」
「具有……的能力」→「能」
「進行……的操作」→ 直接用動詞
「做出決定」→「決定」、「進行討論」→「討論」

**主動語態：**
「被……所採用」→「採用」
「受到……的影響」→「影響了」

**一致性：**
- 同一技術名稱前後統一（不要一下「大型語言模型」一下「LLM」混用）
- 代名詞「它」指向明確

**段落流暢：**
- 相鄰段落要有自然銜接
- 長句（超過 50 字）若能拆就拆
- 不要連續 3 個以上的短句

直接輸出完整文章，不列修改清單，不增加新內容。"""


# ─────────────────────────────────────────────
# 輔助函式
# ─────────────────────────────────────────────
def _humanize(llm: ChatOpenAI, draft: str) -> str:
    messages = [
        SystemMessage(content=HUMANIZER_SYSTEM_PROMPT),
        HumanMessage(content=f"請去除以下文章中的 AI 寫作痕跡：\n\n{draft}")
    ]
    return llm.invoke(messages).content


def _edit(llm: ChatOpenAI, text: str) -> str:
    messages = [
        SystemMessage(content=EDITOR_SYSTEM_PROMPT),
        HumanMessage(content=f"請對以下文章進行 Copy Editing 與 Line Editing：\n\n{text}")
    ]
    return llm.invoke(messages).content


# ─────────────────────────────────────────────
# 主節點
# ─────────────────────────────────────────────
def writer_node(state: NewsState) -> NewsState:
    """
    Writer Agent 節點
    輸入：research_analysis（深度研究報告，優先）或 raw_news（備用）
    輸出：draft_article（三步驟處理後）
    """
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.7
    )

    research_analysis = state.get("research_analysis", "")
    raw_news = state.get("raw_news", [])
    revision_count = state.get("revision_count", 0)

    source_content = research_analysis if research_analysis else str(raw_news)
    source_label = "深度研究分析報告" if research_analysis else "原始新聞資料"

    revision_note = ""
    if revision_count > 0:
        revision_note = (
            f"\n\n【重寫說明】第 {revision_count} 次修改。"
            "請特別注意：用具體數字替換模糊說法，確認每個聲明都有來源。"
        )

    # Step 1：article-writing skill 撰稿
    messages = [
        SystemMessage(content=WRITER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"請根據以下{source_label}，撰寫一篇完整的 AI 科技新聞文章：\n\n"
            f"{source_content}{revision_note}"
        ))
    ]
    draft = llm.invoke(messages).content

    # Step 2：Humanizer - 去除 AI 寫作痕跡
    humanized = _humanize(llm, draft)

    # Step 3：Editor - 語言精簡與流暢度
    edited = _edit(llm, humanized)

    return {
        **state,
        "draft_article": edited,
        "revision_count": revision_count + 1
    }
