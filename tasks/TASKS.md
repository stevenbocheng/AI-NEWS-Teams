# 任務清單 - 全自動 AI 科技新聞網站營運團隊

> 狀態標記：`[ ]` 未開始 · `[~]` 進行中 · `[x]` 已完成 · `[!]` 阻塞中

---

## Phase 1：基礎建設與環境驗證 (Day 1-2)

### P1-T1：專案初始化
- [ ] **P1-T1-1** 建立 Python 3.10+ 虛擬環境 (`python -m venv venv`)
- [ ] **P1-T1-2** 建立 `requirements.txt` 並安裝所有依賴
- [ ] **P1-T1-3** 建立 `.env.example` 檔案，列出所有必要的環境變數
- [ ] **P1-T1-4** 建立 `.gitignore`（排除 `.env`, `venv/`, `output/`, `__pycache__/`）
- [ ] **P1-T1-5** 初始化 git repository，建立第一個 commit

### P1-T2：API 金鑰配置
- [ ] **P1-T2-1** 申請 Tavily API Key（https://tavily.com）
- [ ] **P1-T2-2** 準備 OpenAI API Key
- [ ] **P1-T2-3** 建立本地 `.env` 檔案並填入金鑰
- [ ] **P1-T2-4** 建立 `config/settings.py`，使用 `python-dotenv` 讀取環境變數

### P1-T3：基本搜尋工具測試
- [ ] **P1-T3-1** 建立 `src/tools/search.py`，封裝 `TavilySearchResults`
- [ ] **P1-T3-2** 建立最簡單的 LangChain ReAct Agent 測試腳本
- [ ] **P1-T3-3** 執行測試：搜尋「今日 AI 科技新聞」
- [ ] **P1-T3-4** 記錄並分析 Agent 的 ReAct 思考鏈輸出

**P1 驗收：** Agent 能自主搜尋並回傳 3 則新聞摘要

---

## Phase 2：多 Agent 協作工作流 (Day 3-5)

### P2-T1：Researcher Agent
- [ ] **P2-T1-1** 建立 `src/agents/researcher.py`
- [ ] **P2-T1-2** 撰寫 Researcher System Prompt（附新聞篩選標準）
- [ ] **P2-T1-3** 定義輸出格式：`list[NewsItem]`（標題、URL、摘要、重要性評分）
- [ ] **P2-T1-4** 測試：確認能過濾農場文，只輸出高品質新聞

### P2-T2：Writer Agent
- [ ] **P2-T2-1** 建立 `src/agents/writer.py`
- [ ] **P2-T2-2** 撰寫 Writer System Prompt（文章格式規範）
- [ ] **P2-T2-3** 定義文章結構：標題 + 前言 + 重點條列 + 結語
- [ ] **P2-T2-4** 測試：輸入 3 則新聞，輸出一篇完整 Markdown 文章

### P2-T3：Manager Agent
- [ ] **P2-T3-1** 建立 `src/agents/manager.py`
- [ ] **P2-T3-2** 撰寫 Manager System Prompt（品質審核標準 + 評分機制）
- [ ] **P2-T3-3** 建立 `src/utils/language_filter.py`（台灣慣用語對照表）
- [ ] **P2-T3-4** 測試：輸入含有大陸用語的文章，確認能正確偵測並替換
- [ ] **P2-T3-5** 測試退回機制：低分文章能退回 Writer 重寫

### P2-T4：LangGraph 工作流
- [ ] **P2-T4-1** 建立 `src/graph/workflow.py`
- [ ] **P2-T4-2** 定義 `NewsState` TypedDict（節點間共享的狀態）
- [ ] **P2-T4-3** 建立 StateGraph，加入所有節點
- [ ] **P2-T4-4** 定義條件邊：Manager 評分 < 7 → 退回 Writer（最多 2 次）
- [ ] **P2-T4-5** 整合測試：執行完整三節點工作流
- [ ] **P2-T4-6** 加入 LangSmith 追蹤（選用，用於 debug）

**P2 驗收：** LangGraph 能完整執行 Researcher→Writer→Manager 流程

---

## Phase 3：結構化輸出與 Markdown 格式化 (Day 6-8)

### P3-T1：Pydantic 輸出模型
- [ ] **P3-T1-1** 建立 `ArticleOutput` Pydantic 模型（含所有欄位驗證）
- [ ] **P3-T1-2** 建立 `NewsItem` Pydantic 模型（Researcher 輸出格式）
- [ ] **P3-T1-3** 整合到 Writer Agent，使用 `with_structured_output()` 強制格式化
- [ ] **P3-T1-4** 測試：確認 LLM 輸出 100% 符合 Pydantic schema

### P3-T2：Front Matter 生成器
- [ ] **P3-T2-1** 建立 `src/utils/formatter.py`
- [ ] **P3-T2-2** 實作 `generate_front_matter()` 函式（輸出 YAML 格式）
- [ ] **P3-T2-3** 實作 `generate_filename()` 函式（YYYY-MM-DD-slug.md 格式）
- [ ] **P3-T2-4** 測試：確認生成的 Front Matter 符合 Jekyll/Hugo 規範

### P3-T3：語言過濾器強化
- [ ] **P3-T3-1** 完善 `language_filter.py` 詞彙對照表（至少 30 組詞彙）
- [ ] **P3-T3-2** 實作 `filter_taiwan_terms()` 函式（支援正則表達式）
- [ ] **P3-T3-3** 加入邊緣案例處理（如：詞彙在英文術語中出現時不替換）
- [ ] **P3-T3-4** 撰寫單元測試：`tests/test_language_filter.py`

### P3-T4：檔案管理器
- [ ] **P3-T4-1** 建立 `src/utils/file_manager.py`
- [ ] **P3-T4-2** 實作 `save_article()` 函式（寫入 output/ 目錄）
- [ ] **P3-T4-3** 實作重複文章偵測（避免同日同主題重複發佈）

**P3 驗收：** 系統能產出可直接部署的標準 `.md` 文章檔案

---

## Phase 4：GitHub 整合與全自動化部署 (Day 9-14)

### P4-T1：GitHub 發佈工具
- [ ] **P4-T1-1** 建立 `src/tools/publisher.py`
- [ ] **P4-T1-2** 使用 GitPython 實作 `clone_repo()` 函式
- [ ] **P4-T1-3** 實作 `publish_article()` 函式（複製 .md 到 `_posts/`）
- [ ] **P4-T1-4** 實作自動化 git commit + push（使用 GitHub Token 認證）
- [ ] **P4-T1-5** 測試：在測試 repo 驗證完整 push 流程

### P4-T2：主程式入口
- [ ] **P4-T2-1** 建立 `src/main.py`（整合所有模組的入口點）
- [ ] **P4-T2-2** 加入完整錯誤處理（try/except + 日誌記錄）
- [ ] **P4-T2-3** 加入指數退避重試機制（API 失敗時）
- [ ] **P4-T2-4** 加入執行日誌輸出（記錄每次執行的結果）

### P4-T3：GitHub Actions 配置
- [ ] **P4-T3-1** 建立 `.github/workflows/daily-news.yml`
- [ ] **P4-T3-2** 設定 cron 排程：每天 00:00 UTC（台灣時間 08:00）
- [ ] **P4-T3-3** 配置 GitHub Repository Secrets（OPENAI_API_KEY, TAVILY_API_KEY）
- [ ] **P4-T3-4** 設定 workflow permissions（允許寫入 contents）
- [ ] **P4-T3-5** 測試：手動觸發 workflow，確認完整流程成功

### P4-T4：安全性與監控
- [ ] **P4-T4-1** 確認 `.env` 已加入 `.gitignore`（不 commit 金鑰）
- [ ] **P4-T4-2** 審查 GitHub Token 權限（最小權限原則）
- [ ] **P4-T4-3** 設定 workflow 失敗通知（GitHub Actions → Email）
- [ ] **P4-T4-4** 建立執行日誌記錄機制（output/logs/ 目錄）

### P4-T5：整合測試與上線
- [ ] **P4-T5-1** 執行完整端對端測試（從搜尋到發佈）
- [ ] **P4-T5-2** 確認 `stevenbocheng.github.io` 文章正常渲染
- [ ] **P4-T5-3** 等待第一次自動排程成功執行
- [ ] **P4-T5-4** 記錄上線後 7 天的執行結果

**P4 驗收：** GitHub Actions 連續 3 天自動成功發佈文章

---

## 任務統計

| 階段 | 任務數 | 預估天數 |
|------|--------|----------|
| Phase 1 | 12 | Day 1-2 |
| Phase 2 | 15 | Day 3-5 |
| Phase 3 | 12 | Day 6-8 |
| Phase 4 | 15 | Day 9-14 |
| **總計** | **54** | **14 天** |
