"""
全域設定 - 從環境變數讀取所有設定
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    # 低成本任務用 mini（翻譯、humanize、edit、審核、媒體審核）
    OPENAI_CHEAP_MODEL: str = os.getenv("OPENAI_CHEAP_MODEL", "gpt-4o-mini")

    # Search
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "5"))

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")
    GITHUB_POSTS_PATH: str = os.getenv("GITHUB_POSTS_PATH", "_posts")

    # HuggingFace（選用：圖片/影片生成）
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")

    # Output
    OUTPUT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    LOGS_DIR: str = os.path.join(OUTPUT_DIR, "logs")

    # 個人網頁整合（本地開發用）
    # 將 ai-news.json 寫入個人網頁 public/ 目錄，供 npm run dev 即時預覽
    # 線上自動更新已由 publisher 在同一個 commit 處理，不需額外設定
    # 設定範例：PERSONAL_SITE_PUBLIC_DIR=D:\個人網頁\public
    PERSONAL_SITE_PUBLIC_DIR: str = os.getenv("PERSONAL_SITE_PUBLIC_DIR", "")

    # Quality Control
    MIN_QUALITY_SCORE: float = float(os.getenv("MIN_QUALITY_SCORE", "6.0"))
    MAX_REVISION_COUNT: int = int(os.getenv("MAX_REVISION_COUNT", "2"))
    # 每次執行最多發佈篇數（預設 3，省 token；最多 5）
    MAX_ARTICLES_PER_RUN: int = int(os.getenv("MAX_ARTICLES_PER_RUN", "3"))

    def validate(self):
        """啟動時驗證必要設定"""
        required = {
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "TAVILY_API_KEY": self.TAVILY_API_KEY,
            "GITHUB_TOKEN": self.GITHUB_TOKEN,
            "GITHUB_REPO": self.GITHUB_REPO,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"缺少必要的環境變數：{', '.join(missing)}")


settings = Settings()
