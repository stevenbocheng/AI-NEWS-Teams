"""
Media Generator：圖片 + 影片生成節點
依據 Manager 的 media_decision 生成配圖和/或短影片

圖片：black-forest-labs/FLUX.1-schnell（主）/ stabilityai/stable-diffusion-xl-base-1.0（備選）
影片：Wan-AI/Wan2.2-I2V-A14B（image_to_video，先生成基底圖再轉影片）
Provider：hf-inference（HuggingFace 官方，PRO 免費）
"""
import io
import os
from loguru import logger
from src.graph.workflow import NewsState
from config.settings import settings

IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",  # 主模型（hf-inference 免費）
    "stabilityai/stable-diffusion-xl-base-1.0",  # 備選模型
]
VIDEO_BASE_MODEL = "black-forest-labs/FLUX.1-schnell"
VIDEO_MODEL = "Wan-AI/Wan2.2-I2V-A14B"


def _get_client():
    """建立 HF InferenceClient，若未設定 HF_TOKEN 則回傳 None"""
    if not settings.HF_TOKEN:
        return None
    try:
        from huggingface_hub import InferenceClient
        return InferenceClient(provider="hf-inference", api_key=settings.HF_TOKEN)
    except ImportError:
        logger.warning("huggingface_hub 未安裝，跳過媒體生成")
        return None


def _save_image(pil_image, path: str) -> None:
    """儲存 PIL.Image 到指定路徑"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pil_image.save(path, format="PNG")


def _generate_image(client, prompt: str, path: str) -> bool:
    """生成圖片並存檔，依序嘗試 IMAGE_MODELS，全部失敗回傳 False"""
    for model in IMAGE_MODELS:
        try:
            image = client.text_to_image(prompt, model=model)
            _save_image(image, path)
            logger.info(f"圖片已生成（{model}）：{path}")
            return True
        except Exception as e:
            logger.warning(f"圖片生成失敗（{model}）：{e}，嘗試備選模型...")
    logger.warning("所有圖片模型均失敗，跳過圖片生成")
    return False


def _generate_video(client, video_prompt: str, path: str) -> bool:
    """
    生成影片並存檔：
    Step 1：用 video_prompt 生成基底圖
    Step 2：用基底圖 + video_prompt 呼叫 image_to_video
    """
    try:
        # Step 1：生成基底圖
        base_image = client.text_to_image(video_prompt, model=VIDEO_BASE_MODEL)
        img_bytes = io.BytesIO()
        base_image.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        # Step 2：image → video
        video_bytes = client.image_to_video(
            img_bytes.read(),
            prompt=video_prompt,
            model=VIDEO_MODEL,
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(video_bytes)
        logger.info(f"影片已生成：{path}")
        return True
    except Exception as e:
        logger.warning(f"影片生成失敗：{e}")
        return False


def media_generator_node(state: NewsState) -> NewsState:
    """
    Media Generator 節點
    讀取 media_decision → 生成圖片和/或影片 → 更新 candidates
    """
    media_decision = state.get("media_decision", {})
    if not media_decision:
        logger.info("無 media_decision，跳過媒體生成")
        return state

    generate_image = media_decision.get("generate_image", False)
    generate_video = media_decision.get("generate_video", False)

    if not generate_image and not generate_video:
        logger.info("Manager 決定不需要媒體，跳過")
        return state

    client = _get_client()
    if not client:
        logger.info("HF_TOKEN 未設定，跳過媒體生成")
        return state

    metadata = state.get("metadata", {})
    slug = metadata.get("slug", "ai-news")
    revision = state.get("media_revision_count", 0) + 1

    image_candidates = list(state.get("image_candidates", []))
    video_candidates = list(state.get("video_candidates", []))

    # ── 生成圖片 ────────────────────────────────────────────
    if generate_image:
        image_prompt = media_decision.get("image_prompt", "")
        img_path = os.path.join(settings.OUTPUT_DIR, "images", f"{slug}_v{revision}.png")
        ok = _generate_image(client, image_prompt, img_path)
        image_candidates.append({
            "prompt": image_prompt,
            "path": img_path if ok else "",
            "score": 0,
            "suitable": False,
        })

    # ── 生成影片 ────────────────────────────────────────────
    if generate_video:
        video_prompt = media_decision.get("video_prompt", "")
        vid_path = os.path.join(settings.OUTPUT_DIR, "videos", f"{slug}_v{revision}.mp4")
        ok = _generate_video(client, video_prompt, vid_path)
        video_candidates.append({
            "prompt": video_prompt,
            "path": vid_path if ok else "",
            "score": 0,
            "suitable": False,
        })

    return {
        **state,
        "image_candidates": image_candidates,
        "video_candidates": video_candidates,
        "media_revision_count": revision,
    }
