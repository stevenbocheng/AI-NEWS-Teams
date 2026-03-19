"""
Markdown + Front Matter 生成器
產生符合 Jekyll/Hugo GitHub Pages 規格的文章格式
"""
import re
from datetime import datetime


def generate_front_matter(metadata: dict) -> str:
    """
    生成 YAML Front Matter

    Args:
        metadata: 包含 title, slug, categories, tags, description 的字典

    Returns:
        YAML Front Matter 字串
    """
    today = datetime.now().strftime("%Y-%m-%d")

    title = metadata.get("title", "今日 AI 科技新聞摘要")
    categories = metadata.get("categories", ["AI", "科技新聞"])
    tags = metadata.get("tags", [])
    description = metadata.get("description", "")
    image_path = metadata.get("image_path", "")
    video_path = metadata.get("video_path", "")

    # 格式化 YAML list
    categories_yaml = "\n".join(f"  - {c}" for c in categories)
    tags_yaml = "\n".join(f"  - {t}" for t in tags) if tags else "  []"

    # 媒體欄位（僅在有值時加入）
    media_lines = ""
    if image_path:
        media_lines += f'\nimage: "{image_path}"'
    if video_path:
        media_lines += f'\nvideo: "{video_path}"'

    front_matter = f"""---
title: "{title}"
date: {today}
categories:
{categories_yaml}
tags:
{tags_yaml}
description: "{description}"{media_lines}
---"""

    return front_matter


def generate_filename(slug: str, date: str = None) -> str:
    """
    生成標準化的 Markdown 檔名

    Args:
        slug: URL 友善的文章識別碼（英文）
        date: 日期字串（YYYY-MM-DD），預設為今天

    Returns:
        格式為 YYYY-MM-DD-slug.md 的檔名
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # 清理 slug：只保留英數字、連字號
    clean_slug = re.sub(r'[^a-z0-9-]', '', slug.lower().replace(' ', '-'))
    clean_slug = re.sub(r'-+', '-', clean_slug).strip('-')

    if not clean_slug:
        clean_slug = "ai-news-summary"

    return f"{date}-{clean_slug}.md"
