"""
Agent T：專業科技新聞翻譯員
職責：將 Researcher 收集的原始新聞「完整翻譯」為繁體中文（台灣用語）
      不做任何篩選或重要性判斷，那是 Deep Researcher 的工作

翻譯欄位：title、description、summary、why_important
翻譯原則：
  - 專有名詞保留英文（模型名、公司名、縮寫）
  - 使用台灣慣用詞，不用中國用語
  - 保留英文原標題於 original_title，供後續英文關鍵字搜尋
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.graph.workflow import NewsState
from config.settings import settings


TRANSLATOR_SYSTEM_PROMPT = """你是一位資深 AI 科技媒體翻譯編輯，將英文新聞完整翻譯為台灣繁體中文。

## 核心原則

### 1. 專有名詞「絕對不翻譯」，保留英文原文
**AI 模型名稱（完整保留）：**
GPT-4o、GPT-4.5、o3、o4-mini、Claude 3.5、Claude 3.7、Gemini 2.0、Gemini Ultra、
Llama 3、Llama 4、Mistral、Grok、Phi-4、Qwen、DeepSeek、Sora、DALL-E、Whisper

**公司與組織名稱（完整保留）：**
OpenAI、Anthropic、Google DeepMind、NVIDIA、Meta AI、Microsoft、Apple、
Amazon AWS、Hugging Face、Stability AI、Midjourney、Cohere

**技術縮寫（保留英文，可在後方加中文說明）：**
LLM（大型語言模型）、API、GPU、TPU、RAG、RLHF、SFT、MoE、VLM、
AGI、ASI、AIGC、SaaS、MLOps

**產品名稱（完整保留）：**
ChatGPT、GitHub Copilot、Claude.ai、Gemini Advanced、Midjourney

### 2. 台灣用語（強制使用）
| 禁用（中國用語） | 使用（台灣用語） |
|----------------|----------------|
| 软件/软體 | 軟體 |
| 网络 | 網路 |
| 优化 | 最佳化 |
| 人工智能 | 人工智慧 |
| 应用程序/APP | 應用程式 |
| 数据 | 資料 |
| 算法 | 演算法 |
| 开源 | 開源 |
| 训练 | 訓練 |
| 推理 | 推論 |
| 芯片 | 晶片 |
| 算力 | 運算能力 |
| 落地 | 實際應用 |
| 赋能 | 賦能 |
| 迭代 | 迭代更新 |

### 3. 翻譯品質要求
- 忠實翻譯原文的完整語意，不省略、不壓縮、不改寫
- 所有數字、技術細節、引述內容必須完整保留
- 如果某個欄位已是繁體中文，原樣回傳，不做修改

## 輸出格式
JSON 陣列，每筆包含所有需要翻譯的欄位，僅輸出 JSON 不加其他文字：
[
  {
    "index": 0,
    "title_zh": "繁體中文標題",
    "description_zh": "繁體中文描述",
    "summary_zh": "繁體中文摘要",
    "why_important_zh": "繁體中文重要性說明"
  }
]"""


def _has_english(text: str) -> bool:
    """判斷文字是否含有需要翻譯的英文內容（英文字母佔比超過 15%）"""
    if not text:
        return False
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    return ascii_letters > len(text) * 0.15


def translator_node(state: NewsState) -> NewsState:
    """
    Translator Agent 節點
    完整翻譯 raw_news 所有文字欄位，不做篩選
    Deep Researcher 負責後續的重要性判斷
    """
    raw_news = state.get("raw_news", [])
    if not raw_news:
        return state

    # 建立待翻譯批次（只送含大量英文的項目，節省 token）
    to_translate = []
    for i, item in enumerate(raw_news):
        title = item.get("title", "")
        description = item.get("description", "")
        summary = item.get("summary", "")
        why = item.get("why_important", "")

        if _has_english(title) or _has_english(description) or _has_english(summary):
            to_translate.append({
                "index": i,
                "title": title,
                "description": description,
                "summary": summary,
                "why_important": why,
            })

    if not to_translate:
        return state  # 所有新聞已是繁體中文，直接跳過

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.1  # 翻譯要忠實，低 temperature
    )

    response = llm.invoke([
        SystemMessage(content=TRANSLATOR_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(to_translate, ensure_ascii=False))
    ])

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        translations = {t["index"]: t for t in json.loads(content)}
    except Exception:
        return state  # 翻譯失敗靜默降級，不中斷流程

    translated_news = []
    for i, item in enumerate(raw_news):
        if i not in translations:
            translated_news.append(item)
            continue

        t = translations[i]
        new_item = dict(item)
        new_item["original_title"] = item.get("title", "")  # 保留英文原標題供搜尋
        new_item["title"] = t.get("title_zh") or item.get("title", "")
        new_item["description"] = t.get("description_zh") or item.get("description", "")
        new_item["summary"] = t.get("summary_zh") or item.get("summary", "")
        if t.get("why_important_zh"):
            new_item["why_important"] = t["why_important_zh"]
        translated_news.append(new_item)

    return {
        **state,
        "raw_news": translated_news,
    }
