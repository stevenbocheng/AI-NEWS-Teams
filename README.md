# 全自動 AI 科技新聞網站營運團隊

> 由多個 AI Agent 組成的自動化新聞發佈系統，每日定時抓取 AI 科技新聞並發佈至 `stevenbocheng.github.io`

## 技術棧

- **Python 3.10+** · **LangChain** · **LangGraph**
- **Tavily API**（AI 搜尋）· **OpenAI GPT-4o**（LLM）
- **GitHub Actions**（排程）· **GitPython**（自動部署）

## 快速開始

```bash
# 1. 複製專案
git clone <this-repo>
cd ai-news-automation

# 2. 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 配置環境變數
cp .env.example .env
# 編輯 .env 填入 API 金鑰

# 5. 執行
python src/main.py
```

## 環境變數

```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
GITHUB_TOKEN=ghp_...
GITHUB_REPO=stevenbocheng/stevenbocheng.github.io
```

## 文件

- [計畫書](PLAN.md) - 詳細的四階段執行計畫
- [任務清單](tasks/TASKS.md) - 54 個細項任務追蹤
- [架構說明](docs/architecture.md) - 系統架構與設計決策

## 工作流程

```
GitHub Actions (每日 08:00 台灣時間)
    ↓
Researcher Agent (Tavily 搜尋 AI 新聞)
    ↓
Writer Agent (撰寫繁體中文文章)
    ↓
Manager Agent (品質審核 + 台灣慣用語校正)
    ↓
Publisher (自動 push 到 GitHub Pages)
```
