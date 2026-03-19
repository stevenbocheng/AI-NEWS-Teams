# 📅 專案計畫書：全自動 AI 科技新聞網站營運團隊

**版本：** v1.0
**建立日期：** 2026-03-19
**技術棧：** Python 3.10+ · LangChain · LangGraph · GitHub Actions
**目標網站：** `stevenbocheng.github.io`

---

## 一、專案總覽

### 終極目標
打造一個由多個 AI Agent 組成的自動化新聞發佈系統。每天定時抓取並篩選熱門 AI 科技新聞，經繁體中文（台灣慣用語）校正後，自動排版成符合靜態網站格式的 Markdown 文章，並推送到 `stevenbocheng.github.io`。

### 架構圖

```
┌─────────────────────────────────────────────────────┐
│                 LangGraph Workflow                   │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │Researcher│──▶│  Writer  │──▶│   Manager    │    │
│  │  Agent   │   │  Agent   │   │   Agent      │    │
│  └──────────┘   └──────────┘   └──────────────┘    │
│       │               │               │             │
│  Tavily API      LangChain LLM   品質審核 + 輸出     │
│                                       │             │
│                              ┌────────▼───────┐     │
│                              │  GitHub Pages  │     │
│                              │  Auto Publish  │     │
│                              └────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 核心技術選型

| 技術 | 用途 | 說明 |
|------|------|------|
| **LangChain** | Agent 基礎框架 | 工具整合、Prompt 管理、LLM 呼叫 |
| **LangGraph** | 多 Agent 工作流 | 有向圖狀態機、條件路由、錯誤重試 |
| **Tavily API** | AI 搜尋引擎 | 即時網路搜尋，專為 LLM 設計 |
| **OpenAI GPT-4o** | 主要 LLM | 文章生成、品質審核 |
| **Pydantic** | 結構化輸出 | 強制約束 LLM 輸出格式 |
| **GitPython** | Git 自動化 | 自動 commit 與 push |
| **GitHub Actions** | 雲端排程 | 每日定時觸發，零人工介入 |

---

## 二、專案目錄結構

```
ai-news-automation/
├── .github/
│   └── workflows/
│       └── daily-news.yml          # GitHub Actions 自動排程
│
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── researcher.py           # Agent A：趨勢研究員
│   │   ├── writer.py               # Agent B：內容主編
│   │   └── manager.py              # Agent C：品質守門員
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py               # Tavily 搜尋工具封裝
│   │   └── publisher.py            # GitHub 發佈工具
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   └── workflow.py             # LangGraph 工作流定義
│   │
│   └── utils/
│       ├── __init__.py
│       ├── formatter.py            # Markdown + Front Matter 生成
│       ├── language_filter.py      # 台灣慣用語過濾器
│       └── file_manager.py         # 檔案命名與管理
│
├── config/
│   └── settings.py                 # 全域設定（從環境變數讀取）
│
├── output/                         # 本地暫存生成的 .md 文章
│   └── .gitkeep
│
├── tasks/                          # 細項任務追蹤
│   ├── TASKS.md                    # 主任務清單
│   ├── phase1/
│   ├── phase2/
│   ├── phase3/
│   └── phase4/
│
├── docs/
│   └── architecture.md             # 架構說明文件
│
├── tests/
│   ├── test_researcher.py
│   ├── test_writer.py
│   └── test_formatter.py
│
├── requirements.txt
├── .env.example
├── .gitignore
├── PLAN.md                         # 本計畫書
└── README.md
```

---

## 三、四階段執行計畫

---

### 🔵 第一階段：基礎建設與環境驗證 (Day 1-2)

**目標：** 建立開發環境，驗證 LangChain + Tavily 基本功能。

#### 1.1 環境配置
- [ ] 安裝 Python 3.10+ 並建立 venv 虛擬環境
- [ ] 安裝核心依賴套件（見 requirements.txt）
- [ ] 配置 `.env` 檔案（OpenAI Key、Tavily Key）
- [ ] 初始化 Git repository 並連結遠端

#### 1.2 第一個 LangChain Agent
- [ ] 建立 `src/tools/search.py`：封裝 `TavilySearchResults` 工具
- [ ] 建立基本 LangChain Agent（`create_react_agent`）
- [ ] 測試任務：「搜尋今日台灣與全球 AI 科技頭條，列出前三名」
- [ ] 觀察並記錄 ReAct 思考鏈（Thought → Action → Observation）

#### 1.3 驗收標準
- Agent 能自主決定搜尋關鍵字並回傳整理後的新聞列表
- 搜尋結果包含標題、來源、摘要

---

### 🟡 第二階段：多 Agent 協作工作流 (Day 3-5)

**目標：** 用 LangGraph 建立「研究 → 撰寫 → 審核」線性工作流。

#### 2.1 Agent A - 趨勢研究員 (Researcher)
```
System Prompt 重點：
- 只挑選「具備技術突破」或「高社群討論度」的真實新聞
- 排除農場文、廣告文、重複性內容
- 每次搜尋 3-5 篇，輸出結構化的新聞資料（標題、URL、摘要、重要性評分）
```

#### 2.2 Agent B - 內容主編 (Writer)
```
System Prompt 重點：
- 將研究員提供的資料改寫為完整文章
- 包含：吸睛標題、前言摘要（150字內）、重點條列（3-5點）、結語
- 語氣：專業但易懂，適合台灣科技讀者
- 輸出：完整 Markdown 格式
```

#### 2.3 Agent C - 品質守門員 (Manager)
```
System Prompt 重點：
- 台灣慣用語過濾（智能→智慧、軟件→軟體、優化→最佳化、網絡→網路）
- 事實查核：確認文中技術術語正確
- 格式驗證：確認 Markdown 語法無誤
- 評分機制：內容分數 < 7/10 則退回 Writer 重寫
```

#### 2.4 LangGraph 狀態機設計
```python
# 節點（Nodes）
nodes = ["researcher", "writer", "manager", "publisher"]

# 邊（Edges）
edges = [
    ("researcher", "writer"),      # 研究完成 → 撰寫
    ("writer", "manager"),          # 撰寫完成 → 審核
    ("manager", "writer"),          # 品質不足 → 退回重寫（條件邊）
    ("manager", "publisher"),       # 審核通過 → 發佈
]

# 狀態（State）
class NewsState(TypedDict):
    raw_news: list[dict]            # 研究員收集的原始新聞
    draft_article: str              # 主編撰寫的草稿
    final_article: str              # 審核通過的最終文章
    quality_score: float            # 品質評分
    revision_count: int             # 修改次數（避免無限迴圈）
    metadata: dict                  # 標題、日期、標籤等
```

#### 2.5 驗收標準
- 三個 Agent 能串聯協作，資料在節點間完整傳遞
- Manager 退回機制正常運作（最多重試 2 次）

---

### 🟠 第三階段：結構化輸出與 Markdown 格式化 (Day 6-8)

**目標：** 讓產出完全符合 GitHub Pages 發佈規格。

#### 3.1 Pydantic 結構化輸出模型
```python
class ArticleOutput(BaseModel):
    title: str                      # 文章標題
    slug: str                       # URL 友善的檔名
    date: str                       # YYYY-MM-DD 格式
    categories: list[str]           # 分類標籤
    tags: list[str]                 # 文章標籤
    description: str                # SEO 描述（150字內）
    content: str                    # 完整 Markdown 內容
    sources: list[str]              # 參考來源 URL 列表
```

#### 3.2 Front Matter 自動生成
```yaml
---
title: "2026年最新 AI 突破：GPT-5 正式發佈"
date: 2026-03-19
categories: [AI, 科技新聞]
tags: [GPT-5, OpenAI, 大型語言模型]
description: "本文整理 2026-03-19 最重要的 AI 科技新聞..."
---
```

#### 3.3 標準化檔案命名
```
格式：YYYY-MM-DD-{slug}.md
範例：2026-03-19-ai-news-summary.md
```

#### 3.4 language_filter.py 詞彙對照表
```python
TAIWAN_TERMS = {
    "智能": "智慧",
    "軟件": "軟體",
    "硬件": "硬體",
    "優化": "最佳化",
    "網絡": "網路",
    "視頻": "影片",
    "鏈接": "連結",
    "登錄": "登入",
    "賬號": "帳號",
    "數據": "資料",
    "算法": "演算法",
    "雲計算": "雲端運算",
    "應用程序": "應用程式",
    "開源": "開放原始碼",
}
```

#### 3.5 驗收標準
- 輸出的 `.md` 檔案可直接放入 Jekyll/Hugo `_posts` 目錄並正常渲染
- 所有中國大陸用語均被替換為台灣慣用語

---

### 🔴 第四階段：GitHub 整合與全自動化部署 (Day 9-14)

**目標：** 打通最後一哩路，實現零人工介入的每日自動發佈。

#### 4.1 GitHub 發佈工具 (publisher.py)
```python
# 使用 GitPython 自動化 Git 操作
1. clone / pull 最新的 stevenbocheng.github.io repo
2. 將生成的 .md 複製到 _posts/ 目錄
3. git add, git commit -m "Auto-publish: {date} AI News"
4. git push（使用 GitHub Token 認證）
```

#### 4.2 GitHub Actions Workflow (daily-news.yml)
```yaml
排程設定：每天早上 08:00 UTC+8（00:00 UTC）自動觸發
環境變數：OPENAI_API_KEY, TAVILY_API_KEY, GITHUB_TOKEN
步驟：Setup Python → Install deps → Run main.py → 自動 push 文章
```

#### 4.3 安全性配置
- 所有 API Key 存入 GitHub Repository Secrets
- `.env` 加入 `.gitignore`，絕不 commit 金鑰
- GitHub Token 使用最小權限原則（只給 `repo` 寫入權限）

#### 4.4 錯誤處理與監控
- API 呼叫失敗：指數退避重試（最多 3 次）
- 文章品質不足：跳過當日發佈並發送通知
- GitHub push 失敗：記錄錯誤日誌並保留本地備份

#### 4.5 驗收標準
- GitHub Actions 可在雲端自動執行完整流程
- 每天 08:00 網站自動更新一篇 AI 科技新聞
- 失敗時有錯誤通知機制

---

## 四、技術風險與對策

| 風險 | 可能性 | 影響 | 對策 |
|------|--------|------|------|
| API Rate Limit | 中 | 高 | 加入重試機制 + 備用 API |
| LLM 幻覺（Hallucination） | 中 | 高 | Manager Agent 事實查核 + 來源引用 |
| 台灣慣用語漏改 | 低 | 中 | 靜態詞彙表 + LLM 二次審核 |
| GitHub Actions 超時 | 低 | 中 | 設定 30 分鐘超時限制 |
| 搜尋結果品質差 | 中 | 中 | 多關鍵字輪換策略 |

---

## 五、成功指標（KPI）

| 指標 | 目標值 | 衡量方式 |
|------|--------|----------|
| 自動化率 | 100% | 人工介入次數 = 0 |
| 每日發佈成功率 | ≥ 95% | GitHub Actions 成功執行次數 |
| 文章品質評分 | ≥ 8/10 | Manager Agent 評分 |
| 台灣慣用語準確率 | 100% | 詞彙過濾覆蓋率 |
| 搜尋新聞時效性 | 24 小時內 | 新聞發布時間 vs. 文章發布時間 |
