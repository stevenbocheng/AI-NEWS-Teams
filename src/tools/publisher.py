"""
GitHub 發佈工具
自動將生成的 .md 文章 push 到 stevenbocheng.github.io

功能：
  - 重複發佈偵測：比對 _data/published_log.json，來源 URL 重複則跳過
  - 發佈成功後更新 published_log.json（與文章同一個 commit）
  - 將發佈檔名寫入 state["published_filename"] 供 Job Summary 使用
  - 若有 image_path/video_path，複製媒體到 assets/images/ 與 assets/videos/
    並在 metadata 中寫入 Jekyll 可用的相對路徑供 Front Matter 使用
"""
import json
import os
import shutil
import stat
import tempfile
from datetime import datetime
from loguru import logger
from src.graph.workflow import NewsState
from src.utils.formatter import generate_front_matter, generate_filename
from config.settings import settings

PUBLISHED_LOG_PATH = "_data/published_log.json"
PERSONAL_FEED_FILENAME = "ai-news.json"
PERSONAL_FEED_MAX_ARTICLES = 6
GITHUB_SITE_BASE = "https://stevenbocheng.github.io"


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


def _rmtree_windows(path: str) -> None:
    """Windows 相容的目錄刪除，處理 git 產生的唯讀檔案"""
    def _remove_readonly(func, fpath, _):
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)
    shutil.rmtree(path, onerror=_remove_readonly)


def _load_published_log(repo_dir: str) -> list[dict]:
    """讀取已發佈記錄，檔案不存在時回傳空列表"""
    log_file = os.path.join(repo_dir, PUBLISHED_LOG_PATH)
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _is_duplicate(published_log: list[dict], source_urls: list[str]) -> bool:
    """比對來源 URL，有任一 URL 已在記錄中就視為重複"""
    logged_urls = {url for entry in published_log for url in entry.get("source_urls", [])}
    return any(url in logged_urls for url in source_urls if url)


def _save_published_log(repo_dir: str, published_log: list[dict]) -> None:
    """將更新後的記錄寫回檔案"""
    log_file = os.path.join(repo_dir, PUBLISHED_LOG_PATH)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(published_log, f, ensure_ascii=False, indent=2)


def _copy_media(local_media_path: str, repo_dir: str, assets_subdir: str) -> str:
    """
    複製媒體檔案到 repo 的 assets 目錄
    回傳 Jekyll 可用的相對路徑（如 /assets/images/xxx.png），失敗回傳空字串
    """
    if not local_media_path or not os.path.exists(local_media_path):
        return ""
    filename = os.path.basename(local_media_path)
    dest_dir = os.path.join(repo_dir, "assets", assets_subdir)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, filename)
    shutil.copy2(local_media_path, dest_path)
    return f"/assets/{assets_subdir}/{filename}"


def publisher_node(state: NewsState) -> NewsState:
    """Publisher 節點：將文章與媒體發佈到 GitHub Pages（含重複偵測）"""
    try:
        import git  # gitpython

        final_article = state.get("final_article", "")
        metadata = state.get("metadata", {})
        raw_news = state.get("raw_news", [])
        local_image_path = state.get("image_path", "")
        local_video_path = state.get("video_path", "")

        if not final_article:
            logger.error("沒有可發佈的文章內容")
            return {**state, "published_filename": "", "error": "沒有可發佈的文章內容"}

        # 生成檔案名稱
        filename = generate_filename(metadata.get("slug", "ai-news"))
        local_path = os.path.join(settings.OUTPUT_DIR, filename)
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

        # Clone 目標 repo（媒體路徑需要在 clone 後決定，再寫 Front Matter）
        tmp_dir = tempfile.mkdtemp()
        try:
            repo_url = f"https://{settings.GITHUB_TOKEN}@github.com/{settings.GITHUB_REPO}.git"
            logger.info(f"正在 clone {settings.GITHUB_REPO}...")
            repo = git.Repo.clone_from(repo_url, tmp_dir)

            # ── 重複發佈偵測 ──────────────────────────────
            published_log = _load_published_log(tmp_dir)
            source_urls = [item.get("url", "") for item in raw_news if item.get("url")]

            if _is_duplicate(published_log, source_urls):
                logger.warning("偵測到重複新聞，跳過本次發佈")
                return {**state, "published_filename": "", "error": ""}

            # ── 複製媒體到 assets/ ─────────────────────────
            files_to_commit = []

            jekyll_image_path = _copy_media(local_image_path, tmp_dir, "images")
            jekyll_video_path = _copy_media(local_video_path, tmp_dir, "videos")

            if jekyll_image_path:
                img_dest = os.path.join(tmp_dir, "assets", "images", os.path.basename(local_image_path))
                files_to_commit.append(img_dest)
                logger.info(f"圖片已複製：{jekyll_image_path}")

            if jekyll_video_path:
                vid_dest = os.path.join(tmp_dir, "assets", "videos", os.path.basename(local_video_path))
                files_to_commit.append(vid_dest)
                logger.info(f"影片已複製：{jekyll_video_path}")

            # ── 生成含媒體路徑的 Front Matter ────────────────
            meta_with_media = {
                **metadata,
                "image_path": jekyll_image_path,
                "video_path": jekyll_video_path,
            }
            front_matter = generate_front_matter(meta_with_media)
            full_content = f"{front_matter}\n\n{final_article}"

            # 先保存到本地（供備份）
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(full_content)
            logger.info(f"文章已儲存至本地：{local_path}")

            # ── 複製文章到 _posts 目錄 ─────────────────────
            posts_dir = os.path.join(tmp_dir, settings.GITHUB_POSTS_PATH)
            os.makedirs(posts_dir, exist_ok=True)
            dest_path = os.path.join(posts_dir, filename)
            shutil.copy2(local_path, dest_path)
            files_to_commit.append(dest_path)

            # ── 更新 published_log.json ───────────────────
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
            _save_published_log(tmp_dir, published_log)
            log_dest = os.path.join(tmp_dir, PUBLISHED_LOG_PATH)
            files_to_commit.append(log_dest)

            # ── 更新個人網頁 public/ai-news.json（同一 commit）─
            feed_dest = os.path.join(tmp_dir, "public", PERSONAL_FEED_FILENAME)
            os.makedirs(os.path.dirname(feed_dest), exist_ok=True)
            with open(feed_dest, "w", encoding="utf-8") as f:
                json.dump(_build_feed_json(published_log), f, ensure_ascii=False, indent=2)
            files_to_commit.append(feed_dest)

            # ── Git 操作（文章 + 媒體 + log + feed 同一個 commit）──
            repo.index.add(files_to_commit)
            commit_message = f"Auto-publish: {datetime.now().strftime('%Y-%m-%d')} AI News"
            repo.index.commit(commit_message)

            origin = repo.remote("origin")
            origin.push()
            logger.success(f"文章已成功發佈：{filename}")

            # ── 寫入本地（供 npm run dev 開發預覽）──────────
            _write_local_feed(published_log)

        finally:
            # 釋放 git 物件後再刪除，避免 Windows 檔案鎖定問題
            try:
                repo.close()
            except Exception:
                pass
            try:
                _rmtree_windows(tmp_dir)
            except Exception as cleanup_err:
                logger.warning(f"臨時目錄清理失敗（不影響發佈）：{cleanup_err}")

        return {**state, "published_filename": filename, 