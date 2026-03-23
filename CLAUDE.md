# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

全自動 AI 科技新聞系統。8 個 AI Agent 以 LangGraph StateGraph 串接，每日台灣時間 08:00 由 GitHub Actions 自動觸發，從新聞蒐集到發布全程無人工介入。

## 常用指令

```bash
# 本地執行完整流水線
python src/main.py

# 建立虛擬環境（首次）
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env           # 填入 OPENAI_API_KEY, TAVILY_API_KEY, GITHUB_REPO
```

必要環境變數（`config/settings.py` 的 `validate()` 會在啟動時檢查）：
- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `GITHUB_REPO`（格式：`username/repo`）

選用：`HF_TOKEN`（未設定時媒體生成自動跳過）、`PERSONAL_SITE_PUBLIC_DIR`（本地預覽用）

## 架構

### LangGraph 工作流（`src/graph/workflow.py`）

主流程：`researcher → translator → deep_researcher → writer → manager → media_generator → media_reviewer → publisher`

- **條件路由 1**（`should_revise`）：Manager 評分 < `MIN_QUALITY_SCORE`（預設 6.0）且 `revision_count < MAX_REVISION_COUNT`（預設 2）→ 退回 writer；否則 → media_generator
- **條件路由 2**（`should_regenerate_media`）：媒體審核不通過且 `media_revision_count < 3` → 重新生成；否則 → publisher
- `build_article_workflow()`：子工作流，從 translator 開始（跳過 researcher），用於多篇逐一處理

所有 Agent 共享 `NewsState` TypedDict（15 個欄位），每個 Agent 只讀寫自己負責的欄位。

### 雙模型策略

| 模型 | 用途 |
|------|------|
| `OPENAI_MODEL`（gpt-4o） | 創意寫作、深度分析（researcher、deep_researcher、writer） |
| `OPENAI_CHEAP_MODEL`（gpt-4o-mini） | 翻譯、humanizer、editor、審核、媒體審核 |

### Writer Agent 三步流程（`src/agents/writer.py`）

1. **article-writing skill**：具體數字開場、禁用炒作詞彙、直接務實語氣
2. **humanizer-zh-tw skill**：去除 24 種 AI 寫作模式
3. **editor skill**：Copy Editing + Line Editing，精簡冗詞

### Researcher Agent 評分架構（`src/agents/researcher.py`）

```
Final Score = (content_score × source_weight + recency_bonus + keyword_bonus) / 25 × 100
```
- `content_score`（0-10）：唯一需要 LLM 的部分
- `source_weight`、`recency_bonus`、`keyword_bonus`：Python 靜態計算
- 閾值：`final_score ≥ 60` 才進入後續流程；每次最多發布 `MAX_ARTICLES_PER_RUN`（預設 3）篇

### 關鍵設定（`config/settings.py`）

`Settings` 類別為單例，全專案透過 `from config.settings import settings` 存取。所有值均可透過環境變數覆蓋。

## Skills 目錄

`.agents/skills/` 存放 Skill 規範文件（SKILL.md），定義每個 Agent 的職責與限制：
- `deep-research`、`humanizer-zh-tw`、`article-writing`、`editor` 為 Writer/Deep Researcher 使用的 prompt 規範
- `.claude/skills/` 為 Claude Code 的 skill symlink（由 `npx skills` 管理）

新增或修改 Agent 行為時，先更新對應的 SKILL.md，再修改 `src/agents/` 的實作。

## 部署

GitHub Actions（`.github/workflows/daily-news.yml`）：
- 排程：每日 UTC 00:00（台灣時間 08:00）
- 執行後自動 `git push` 發布 `_posts/`、`_data/`、`public/` 的變更
- Secrets 需在 GitHub repo 設定：`OPENAI_API_KEY`、`TAVILY_API_KEY`、`HF_TOKEN`
- 執行日誌上傳為 Artifact，保留 30 天
