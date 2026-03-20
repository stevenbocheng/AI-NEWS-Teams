"""
GitHub 發佈工具
將生成的文章與 ai-news.json 寫入本地 repo 目錄，由 workflow 的 git push 完成發佈。

功能：
  - 重複發佈偵測：比對 _data/published_log.json，來源 URL 重複則跳過
  - 寫入 _posts/ 文章、public/ai-news.json、public/assets/ 媒體
"""
import json
import os
import shutil
from datetime import datetime
from loguru import logger
from src.graph.workflow import NewsState
from src.utils.formatter import generate_front_matter, generate_filename
from config.settings import settings

PUBLISHED_LOG_PATH = "_data/published_log.json"
PERSONAL_FEED_FILENAME = "ai-news.json"
PERSONAL_FEED_MAX_ARTICLES = 30
GITHUB_SITE_BASE = "https://stevenbocheng.github.io"

# Repo 根目錄（Actions 環境下 = 工作目錄；本地開發下 = 專案根目錄）
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build_feed_json(published_log: list[dict]) -> dict:
    """published_log 轉成前端所需的 feed JSON 結構"""
    recent = list(reversed(published_log))[:PERSONAL_FEED_MAX_ARTICLES]
    articles = []
    for entry in recent:
        date_str = entry.get("date", "")
        slug = entry.get("slug", "")
        image_path = entry.get("image", "")

        url = GITHUB_SITE_BASE
        if date_str and slug:
            parts = date_str.split("-")
            if len(parts) == 3:
                url = f"{GITHUB_SITE_BASE}/{parts[0]}/{parts[1]}/{parts[2]}/{slug}/"

        image_url = f"{GITHUB_SITE_BASE}{image_path}" if image_path else ""
        video_path = entry.get("video", "")
        video_url = f"{GITHUB_SITE_BASE}{video_path}" if video_path else ""

        articles.append({
            "title": entry.get("title", ""),
            "description": entry.get("description", ""),
            "date": date_str,
            "slug": slug,
            "url": url,
            "image": image_url,
            "video": video_url,
            "categories": entry.get("categories", ["AI", "科技新聞"]),
            "tags": entry.get("tags", []),
            "body": entry.get("body", ""),
        })

    return {
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "articles": articles,
    }


def _write_local_feed(published_log: list[dict]) -> None:
    """本地開發用：將 feed 寫入個人網頁 public/ 目錄（供 npm run dev 即時預覽）"""
    public_dir = settings.PERSONAL_SITE_PUBLIC_DIR
    if not public_dir:
        return
    try:
        feed_content = json.dumps(_build_feed_json(published_log), ensure_ascii=False, indent=2)
        os.makedirs(public_dir, exist_ok=True)
        with open(os.path.join(public_dir, PERSONAL_FEED_FILENAME), "w", encoding="utf-8") as f:
            f.write(feed_content)
        logger.info(f"個人網頁 feed 已寫入本地：{public_dir}")
    except Exception as e:
        logger.warning(f"個人網頁 feed 本地寫入失敗：{e}")


def _load_published_log(repo_dir: str) -> list[dict]:
    log_file = os.path.join(repo_dir, PUBLISHED_LOG_PATH)
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _is_duplicate(published_log: list[dict], source_urls: list[str]) -> bool:
    logged_urls = {url for entry in published_log for url in entry.get("source_urls", [])}
    return any(url in logged_urls for url in source_urls if url)


def _save_published_log(repo_dir: str, published_log: list[dict]) -> None:
    log_file = os.path.join(repo_dir, PUBLISHED_LOG_PATH)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(published_log, f, ensure_ascii=False, indent=2)


def _copy_media(local_media_path: str, repo_dir: str, assets_subdir: str) -> str:
    if not local_media_path or not os.path.exists(local_media_path):
        return ""
    filename = os.path.basename(local_media_path)
    dest_dir = os.path.join(repo_dir, "public", "assets", assets_subdir)
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(local_media_path, os.path.join(dest_dir, filename))
    return f"/assets/{assets_subdir}/{filename}"


def publisher_node(state: NewsState) -> NewsState:
    """Publisher 節點：將文章與媒體寫入本地 repo（git push 由 workflow 處理）"""
    try:
        final_article = state.get("final_article", "")
        metadata = state.get("metadata", {})
        raw_news = state.get("raw_news", [])
        local_image_path = state.get("image_path", "")
        local_video_path = state.get("video_path", "")

        if not final_article:
            logger.error("沒有可發佈的文章內容")
            return {**state, "published_filename": "", "error": "沒有可發佈的文章內容"}

        repo_dir = _REPO_ROOT
        filename = generate_filename(metadata.get("slug", "ai-news"))
        local_path = os.path.join(settings.OUTPUT_DIR, filename)
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

        # 重複發佈偵測
        published_log = _load_published_log(repo_dir)
        source_urls = [item.get("url", "") for item in raw_news if item.get("url")]

        if _is_duplicate(published_log, source_urls):
            logger.warning("偵測到重複新聞，跳過本次發佈")
            return {**state, "published_filename": "", "error": ""}

        # 複製媒體
        jekyll_image_path = _copy_media(local_image_path, repo_dir, "images")
        jekyll_video_path = _copy_media(local_video_path, repo_dir, "videos")
        if jekyll_image_path:
            logger.info(f"圖片已複製：{jekyll_image_path}")
        if jekyll_video_path:
            logger.info(f"影片已複製：{jekyll_video_path}")

        # 生成文章內容
        meta_with_media = {**metadata, "image_path": jekyll_image_path, "video_path": jekyll_video_path}
        front_matter = generate_front_matter(meta_with_media)
        full_content = f"{front_matter}\n\n{final_article}"

        # 儲存到本地備份
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        logger.info(f"文章已儲存至本地：{local_path}")

        # 寫入 _posts/
        posts_dir = os.path.join(repo_dir, settings.GITHUB_POSTS_PATH)
        os.makedirs(posts_dir, exist_ok=True)
        shutil.copy2(local_path, os.path.join(posts_dir, filename))

        # 更新 published_log.json
        published_log.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "slug": metadata.get("slug", ""),
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "categories": metadata.get("categories", ["AI", "科技新聞"]),
            "tags": metadata.get("tags", []),
            "body": final_article,
            "source_urls": source_urls,
            "filename": filename,
            "image": jekyll_image_path,
            "video": jekyll_video_path,
        })
        _save_published_log(repo_dir, published_log)

        # 更新 public/ai-news.json
        feed_dest = os.path.join(repo_dir, "public", PERSONAL_FEED_FILENAME)
        os.makedirs(os.path.dirname(feed_dest), exist_ok=True)
        with open(feed_dest, "w", encoding="utf-8") as f:
            json.dump(_build_feed_json(published_log), f, ensure_ascii=False, indent=2)

        logger.success(f"文章檔案已寫入，等待 workflow git push：{filename}")
        _write_local_feed(published_log)

        return {**state, "published_filename": filename, "error": ""}

    except Exception as e:
        logger.error(f"發佈失敗：{e}")
        return {**state, "published_filename": "", "error": str(e)}
