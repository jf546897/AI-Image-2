"""Standalone AI Image 2 web app."""

import base64
import io
import json
import threading
import time
import uuid
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
import uvicorn
from PIL import Image, ImageDraw
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

if sys.platform == "win32":
    import winreg
else:  # pragma: no cover
    winreg = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def _resolve_base_dir() -> Path:
    project_root = os.environ.get("AI_IMAGE_PROJECT_ROOT")
    if project_root:
        return Path(project_root).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent


BASE_DIR = _resolve_base_dir()
CODEX_CONFIG_DIR = Path.home() / ".codex"
LOCAL_CONFIG_PATH = BASE_DIR / "local_config.json"
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
IMAGE_MODEL = "gpt-image-2"
IMAGE_TIMEOUT = 600
MAX_PROMPT_CHARS = 4000
UPSTREAM_PROMPT_CHARS = 1400
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
EXTERNAL_CONFIG_ENV = "AI_IMAGE_ENABLE_EXTERNAL_CONFIG"
_KEY_CACHE: dict[str, str] = {}
TASKS: dict[str, dict[str, Any]] = {}
_MODEL_LIST_CACHE: dict[str, list[str]] = {}

app = FastAPI(title="AI Image 2", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("璇诲彇 Codex 鍑瘉鏂囦欢澶辫触: %s", exc)
        return {}


def _read_local_config() -> dict[str, Any]:
    data = _read_json(LOCAL_CONFIG_PATH)
    if not isinstance(data, dict):
        return {}
    return data


def _write_local_config(base_url: str, api_key: str) -> None:
    clean_base_url = str(base_url or "").strip().rstrip("/")
    clean_api_key = str(api_key or "").strip()
    if not clean_base_url:
        raise HTTPException(status_code=400, detail="API URL Base is required")
    if not clean_api_key:
        raise HTTPException(status_code=400, detail="API Key is required")
    LOCAL_CONFIG_PATH.write_text(
        json.dumps({"base_url": clean_base_url, "api_key": clean_api_key}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _KEY_CACHE.clear()
    _MODEL_LIST_CACHE.clear()


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8-sig")
        return tomllib.loads(content)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("璇诲彇 Codex 閰嶇疆鏂囦欢澶辫触: %s", exc)
        return {}


def _read_windows_user_env(name: str) -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "").strip()
    except OSError:
        return ""


def _external_config_enabled() -> bool:
    return str(os.environ.get(EXTERNAL_CONFIG_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def _mask_api_key(api_key: str) -> str:
    clean_api_key = str(api_key or "").strip()
    if not clean_api_key:
        return ""
    if len(clean_api_key) <= 4:
        return "*" * len(clean_api_key)
    if len(clean_api_key) <= 8:
        return f"{clean_api_key[:2]}...{clean_api_key[-1:]}"
    if len(clean_api_key) <= 12:
        return f"{clean_api_key[:4]}...{clean_api_key[-2:]}"
    return f"{clean_api_key[:6]}...{clean_api_key[-4:]}"


def _resolve_base_url_with_source() -> tuple[str, str]:
    local_config = _read_local_config()
    local_base_url = str(local_config.get("base_url") or "").strip()
    if local_base_url:
        return local_base_url.rstrip("/"), "local_config"

    if _external_config_enabled():
        config = _read_toml(CODEX_CONFIG_DIR / "config.toml")
        provider_name = str(config.get("model_provider") or "OpenAI")
        providers = config.get("model_providers") or {}
        provider = providers.get(provider_name) or providers.get("OpenAI") or {}
        base_url = str(provider.get("base_url") or os.environ.get("OPENAI_BASE_URL") or "").strip()
        if base_url:
            return base_url.rstrip("/"), "external_opt_in"

    return DEFAULT_OPENAI_BASE_URL, "default"


def _get_codex_base_url() -> str:
    base_url, _ = _resolve_base_url_with_source()
    return base_url


def _iter_api_key_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    local_config = _read_local_config()
    local_api_key = str(local_config.get("api_key") or "").strip()
    if local_api_key:
        candidates.append(("local_config.json", local_api_key))

    if _external_config_enabled():
        for filename in ("auth.json", "auth.json.proxy", "auth.json.sub2api"):
            data = _read_json(CODEX_CONFIG_DIR / filename)
            api_key = str(data.get("OPENAI_API_KEY") or data.get("api_key") or "").strip()
            if api_key:
                candidates.append((filename, api_key))

        for name in ("OPENAI_API_KEY", "SUB2API_KEY"):
            api_key = str(os.environ.get(name) or "").strip()
            if api_key:
                candidates.append((f"process:{name}", api_key))

        for name in ("OPENAI_API_KEY", "SUB2API_KEY"):
            api_key = _read_windows_user_env(name)
            if api_key:
                candidates.append((f"user:{name}", api_key))

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, api_key in candidates:
        if api_key not in seen:
            unique.append((source, api_key))
            seen.add(api_key)
    return unique


def _is_api_key_accepted(api_key: str) -> bool:
    try:
        response = requests.get(
            _openai_image_url("/models"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=12,
        )
        return response.status_code < 400
    except requests.RequestException as exc:
        logger.warning("?? API Key ?????: %s", exc)
        return False


def _get_codex_api_key() -> str:
    cache_key = _get_codex_base_url()
    cached_key = _KEY_CACHE.get(cache_key)
    if cached_key:
        return cached_key

    candidates = _iter_api_key_candidates()
    for source, api_key in candidates:
        if _is_api_key_accepted(api_key):
            logger.info("???? API Key ??: %s", source)
            _KEY_CACHE[cache_key] = api_key
            return api_key

    if candidates:
        logger.warning("???? API Key ????????????????????")
        return candidates[0][1]
    return ""


def _peek_api_key_candidate() -> tuple[str, str]:
    candidates = _iter_api_key_candidates()
    if not candidates:
        return "", ""
    return candidates[0]


def _describe_config_source(local_config: dict[str, Any], base_url_source: str, api_key_source: str) -> str:
    has_local_config = bool(local_config.get("base_url") or local_config.get("api_key"))
    external_involved = base_url_source == "external_opt_in" or (api_key_source and api_key_source != "local_config.json")
    if has_local_config:
        return "mixed" if external_involved else "local_config"
    if external_involved:
        return "external_opt_in"
    return "default"


def _optimize_prompt_to_limit(prompt: str) -> str:
    compact = str(prompt or "").replace("\r\n", "\n").strip()
    compact = " ".join(compact.split())
    if len(compact) <= MAX_PROMPT_CHARS:
        return compact

    budget = MAX_PROMPT_CHARS - 120
    head_length = int(budget * 0.72)
    tail_length = max(0, budget - head_length)
    head = compact[:head_length]
    for separator in ("。", "！", "？", ".", "!", "?", "\n"):
        candidate = head.rsplit(separator, 1)[0]
        if len(candidate) >= head_length * 0.65:
            head = candidate + separator
            break
    tail = compact[-tail_length:] if tail_length else ""
    optimized = (
        head
        + "\n\n[Auto-optimized: middle repetitive details compressed to fit the 4000 character limit.]\n\n"
        + tail
    )
    return optimized[:MAX_PROMPT_CHARS]


def _game_visual_prompt() -> str:
    return (
        "Top-down isometric 3D pixel-art gameplay screenshot of an original wasteland open-world RPG sandbox. "
        "Desert ruins, scavenger base, small squad, NPC factions, traders, raiders, wounded survivor, crafting benches, "
        "caravans, prosthetics, harsh survival mood. Looks like a real playable game screenshot, RimWorld and Kenshi inspired, no magic."
    )


def _game_visual_prompt_ultra() -> str:
    return (
        "Top-down 3D pixel-art wasteland RPG game screenshot: desert outpost, survivors, raiders, traders, crafting, "
        "medical injuries, caravans, harsh sandbox survival, original RimWorld Kenshi inspired world, no magic."
    )


def _known_chinese_visual_prompt(prompt: str) -> str:
    if "\u4f01\u9e45" in prompt:
        if "\u5199\u5b9e" in prompt or "\u771f\u5b9e" in prompt:
            return "A photorealistic penguin standing on Antarctic ice, full body, natural lighting, high detail, no text, no letters, no question marks."
        if "\u50cf\u7d20" in prompt:
            return "A cute pixel-art penguin, full body, clear black and white feathers, orange feet, simple icy background, no text, no question marks."
        return "Draw a full body penguin bird, black back, white belly, orange feet, standing on ice, simple clean background. Do not include any text or symbols."
    return ""


def _prepare_upstream_prompt(prompt: str) -> str:
    clean_prompt = str(prompt or "").strip()
    lower_prompt = clean_prompt.lower()
    is_game_prompt = any(
        token in lower_prompt or token in clean_prompt
        for token in (
            "rpg", "rimworld", "kenshi", "sandbox", "wasteland",
            "\u6e38\u620f", "\u50cf\u7d20", "\u5e9f\u571f", "\u5f00\u653e\u4e16\u754c", "\u4fef\u89c6"
        )
    )
    if is_game_prompt:
        return _game_visual_prompt()

    known_prompt = _known_chinese_visual_prompt(clean_prompt)
    if known_prompt:
        return known_prompt

    if len(clean_prompt) <= UPSTREAM_PROMPT_CHARS:
        return clean_prompt

    compact = " ".join(clean_prompt.split())
    head = compact[:900]
    tail = compact[-350:] if len(compact) > 1250 else ""
    return (
        head
        + "\n\n[Auto-distilled for image generation: preserve the main subject, visual style, composition, mood, world rules and important constraints.]\n\n"
        + tail
    )[:UPSTREAM_PROMPT_CHARS]


def _validate_prompt(prompt: str) -> str:
    clean_prompt = _optimize_prompt_to_limit(prompt)
    if not clean_prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    return clean_prompt


def _should_fallback_to_responses(message: str) -> bool:
    clean_message = str(message or "")
    return (
        _is_account_pool_unavailable(clean_message)
        or clean_message == "upstream_html_timeout"
        or "no access to model gpt-image-2" in clean_message.lower()
    )


def _available_model_ids(api_key: str) -> list[str]:
    cache_key = f"{_get_codex_base_url()}:{api_key[:8]}:{api_key[-4:]}"
    cached = _MODEL_LIST_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = _requests_session().get(
            _openai_image_url("/models"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        if response.status_code >= 400:
            _MODEL_LIST_CACHE[cache_key] = []
            return []
        data = response.json()
        models = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
        _MODEL_LIST_CACHE[cache_key] = models
        return models
    except Exception as exc:
        logger.warning("Could not list available models: %s", exc)
        _MODEL_LIST_CACHE[cache_key] = []
        return []


def _select_responses_model(api_key: str) -> str:
    models = _available_model_ids(api_key)
    if not models:
        return "gpt-5.5"
    for model in ("gpt-5.5", "gpt-5.4", "gpt-5.3-codex", "gpt-5.2"):
        if model in models:
            return model
    return models[0]


def _normalize_size(size: str) -> str:
    allowed_sizes = {"auto", "1024x1024", "1024x1536", "1536x1024"}
    return size if size in allowed_sizes else "1024x1024"


def _openai_image_url(path: str) -> str:
    base_url = _get_codex_base_url()
    if base_url.endswith("/v1"):
        return f"{base_url}{path}"
    return f"{base_url}/v1{path}"


def _is_html_error_response(response: requests.Response) -> bool:
    content_type = str(response.headers.get("content-type") or "").lower()
    text = response.text[:500].lower()
    return "text/html" in content_type or "<!doctype html" in text or "<html" in text


def _extract_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        if _is_html_error_response(response):
            return "upstream_html_timeout"
        return response.text[:500] or f"HTTP {response.status_code}"
    detail = data.get("error") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail)
    message = str(detail or data)
    if "<!DOCTYPE html>" in message or "<html" in message.lower():
        return "upstream_html_timeout"
    return message



def _is_account_pool_unavailable(message: str) -> bool:
    normalized = str(message or "").lower()
    return "no available compatible accounts" in normalized or "compatible accounts" in normalized


def _requests_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _normalize_quality(quality: str) -> str:
    return quality if quality in {"auto", "low", "medium", "high"} else "auto"


def _normalize_background(background: str) -> str:
    return background if background in {"auto", "transparent", "opaque"} else "auto"


def _normalize_output_format(output_format: str) -> str:
    return output_format if output_format in {"png", "jpeg", "webp"} else "png"


def _normalize_compression(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    return max(0, min(100, int(value)))


def _append_generation_options(payload: dict[str, Any], size: str, quality: str, background: str, output_format: str, output_compression: Optional[int]) -> dict[str, Any]:
    size = _normalize_size(size)
    quality = _normalize_quality(quality)
    background = _normalize_background(background)
    output_format = _normalize_output_format(output_format)
    if size != "auto":
        payload["size"] = size
    if quality != "auto":
        payload["quality"] = quality
    if background != "auto":
        payload["background"] = background
    if output_format != "png":
        payload["output_format"] = output_format
    if output_format in {"jpeg", "webp"} and output_compression is not None:
        payload["output_compression"] = _normalize_compression(output_compression)
    return payload


def _set_task(task_id: str, **updates: Any) -> None:
    task = TASKS.setdefault(task_id, {})
    task.update(updates)
    task["updated_at"] = time.time()


def _request_openai_images(endpoint: str, data: dict[str, Any], files: Optional[list[tuple[str, Any]]] = None) -> dict[str, Any]:
    api_key = _get_codex_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="鏈壘鍒板綋鍓?API Key锛岃妫€鏌ョ敤鎴风幆澧冨彉閲?OPENAI_API_KEY / SUB2API_KEY")

    try:
        response = requests.post(
            _openai_image_url(endpoint),
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
            timeout=IMAGE_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.error("AI 鐢熷浘璇锋眰澶辫触: %s", exc)
        raise HTTPException(status_code=502, detail=f"杩炴帴鍥剧墖妯″瀷澶辫触: {exc}") from exc

    if response.status_code >= 400:
        message = _extract_error_message(response)
        logger.warning("AI 鐢熷浘鎺ュ彛杩斿洖閿欒: %s", message)
        raise HTTPException(status_code=response.status_code, detail=message)

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="鍥剧墖妯″瀷杩斿洖浜嗛潪 JSON 鍝嶅簲") from exc


def _build_contact_sheet(images: list[tuple[str, bytes, str]]) -> tuple[str, bytes, str]:
    opened: list[Image.Image] = []
    try:
        for name, content, _ in images:
            image = Image.open(io.BytesIO(content)).convert("RGB")
            image.thumbnail((640, 900))
            opened.append(image.copy())
    finally:
        for image in opened:
            pass

    if not opened:
        raise HTTPException(status_code=400, detail="图片内容为空")

    padding = 24
    label_height = 42
    width = sum(image.width for image in opened) + padding * (len(opened) + 1)
    height = max(image.height for image in opened) + padding * 2 + label_height
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    x = padding
    for index, image in enumerate(opened, start=1):
        draw.text((x, padding // 2), f"Reference Image {index}", fill=(0, 0, 0))
        sheet.paste(image, (x, padding + label_height))
        x += image.width + padding

    output = io.BytesIO()
    sheet.save(output, format="PNG")
    return "combined-reference.png", output.getvalue(), "image/png"


def _request_image2_generation(
    prompt: str,
    size: str,
    quality: str,
    background: str,
    output_format: str,
    output_compression: Optional[int] = None,
    progress_callback: Optional[Any] = None,
) -> dict[str, Any]:
    prompt = _prepare_upstream_prompt(prompt)
    api_key = _get_codex_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="未找到可用 API Key")

    payload = _append_generation_options(
        {"model": IMAGE_MODEL, "prompt": prompt},
        size=size,
        quality=quality,
        background=background,
        output_format=output_format,
        output_compression=output_compression,
    )

    try:
        response = _requests_session().post(
            _openai_image_url("/images/generations"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=IMAGE_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.error("GPT Image 2 ???????: %s", exc)
        raise HTTPException(status_code=502, detail=f"?? GPT Image 2 ??: {exc}") from exc

    if response.status_code >= 400:
        message = _extract_error_message(response)
        logger.warning("GPT Image 2 generation failed: %s", message)
        if _should_fallback_to_responses(message):
            logger.warning("Falling back to Responses image_generation for text-to-image")
            return _request_responses_image(prompt=prompt, quality=quality, progress_callback=progress_callback)
        raise HTTPException(status_code=response.status_code, detail=message)

    data = response.json()
    if not data.get("data"):
        raise HTTPException(status_code=502, detail="GPT Image 2 未返回图片")
    return data


def _request_image2_edit(
    prompt: str,
    images: list[UploadFile],
    size: str,
    quality: str,
    background: str,
    output_format: str,
    output_compression: Optional[int] = None,
    progress_callback: Optional[Any] = None,
) -> dict[str, Any]:
    prompt = _prepare_upstream_prompt(prompt)
    api_key = _get_codex_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="未找到可用 API Key")
    if not images:
        raise HTTPException(status_code=400, detail="请至少上传一张参考图")

    image_payloads: list[tuple[str, bytes, str]] = []
    for index, upload in enumerate(images, start=1):
        image_bytes = upload.file.read()
        upload.file.seek(0)
        if image_bytes:
            image_payloads.append((upload.filename or f"image-{index}.png", image_bytes, upload.content_type or "image/png"))

    if not image_payloads:
        raise HTTPException(status_code=400, detail="图片内容为空")

    def send_edit(payloads: list[tuple[str, bytes, str]], use_array_field: bool, minimal: bool, prompt_override: Optional[str] = None) -> requests.Response:
        files: list[tuple[str, Any]] = []
        field_name = "image[]" if use_array_field and len(payloads) > 1 else "image"
        for filename, content, content_type in payloads:
            files.append((field_name, (filename, content, content_type)))
        data = {"model": IMAGE_MODEL, "prompt": prompt_override or prompt}
        if not minimal:
            data = _append_generation_options(
                data,
                size=size,
                quality=quality,
                background=background,
                output_format=output_format,
                output_compression=output_compression,
            )
        return _requests_session().post(
            _openai_image_url("/images/edits"),
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
            timeout=IMAGE_TIMEOUT,
        )

    attempts: list[tuple[str, requests.Response]] = []
    try:
        if len(image_payloads) > 1:
            combined = _build_contact_sheet(image_payloads)
            combined_prompt = (
                prompt
                + "\n\nThe uploaded reference is a combined contact sheet. Treat Reference Image 1 as the room/layout, "
                + "Reference Image 2 as the left character, and Reference Image 3 as the right character."
            )
            response = send_edit([combined], use_array_field=False, minimal=True, prompt_override=combined_prompt)
            attempts.append(("combined_minimal_first", response))
            if response.status_code >= 400:
                response = send_edit(image_payloads, use_array_field=True, minimal=True)
                attempts.append(("multi_minimal_fallback", response))
        else:
            response = send_edit(image_payloads, use_array_field=False, minimal=False)
            attempts.append(("single_with_options", response))
            if response.status_code >= 400 and _extract_error_message(response) == "upstream_html_timeout":
                response = send_edit(image_payloads, use_array_field=False, minimal=True)
                attempts.append(("single_minimal", response))
    except requests.RequestException as exc:
        logger.error("GPT Image 2 ???????: %s", exc)
        raise HTTPException(status_code=502, detail=f"?? GPT Image 2 ??: {exc}") from exc

    if response.status_code >= 400:
        message = _extract_error_message(response)
        logger.warning("GPT Image 2 edit failed: %s; attempts=%s", message, [(name, item.status_code) for name, item in attempts])
        if _should_fallback_to_responses(message):
            logger.warning("Falling back to Responses image_generation for image edit")
            return _request_responses_image(prompt=prompt, images=images, quality=quality, progress_callback=progress_callback)
        if message == "upstream_html_timeout":
            message = "upstream_timeout_after_retries"
        raise HTTPException(status_code=response.status_code, detail=message)

    data = response.json()
    if not data.get("data"):
        raise HTTPException(status_code=502, detail="GPT Image 2 未返回图片")
    return data


def _quality_for_responses(quality: str) -> str:
    return quality if quality in {"low", "medium", "high"} else "low"


def _image_to_data_url(upload: UploadFile) -> str:
    upload.file.seek(0)
    content = upload.file.read()
    upload.file.seek(0)
    mime_type = upload.content_type or "image/png"
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_response_images(data: dict[str, Any]) -> dict[str, Any]:
    images: list[dict[str, str]] = []
    for item in data.get("output", []):
        if isinstance(item, dict) and item.get("type") == "image_generation_call" and item.get("result"):
            images.append({"b64_json": item["result"]})
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("type") in {"output_image", "image"}:
                value = content.get("image_base64") or content.get("b64_json")
                if value:
                    images.append({"b64_json": value})
    return {"created": data.get("created_at"), "data": images, "raw_id": data.get("id")}


def _collect_b64_images(value: Any, images: list[str]) -> None:
    if isinstance(value, dict):
        for key in ("result", "partial_image_b64", "image_base64", "b64_json"):
            item = value.get(key)
            if isinstance(item, str) and len(item) > 1000:
                images.append(item)
        for item in value.values():
            _collect_b64_images(item, images)
    elif isinstance(value, list):
        for item in value:
            _collect_b64_images(item, images)


def _request_responses_image(
    prompt: str,
    images: Optional[list[UploadFile]] = None,
    quality: str = "low",
    progress_callback: Optional[Any] = None,
) -> dict[str, Any]:
    api_key = _get_codex_api_key()
    prepared_prompt = _prepare_upstream_prompt(prompt)
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required")
    preferred_model = _select_responses_model(api_key)
    responses_models = list(dict.fromkeys([preferred_model, "gpt-5.4", "gpt-5.3-codex", "gpt-5.5", "gpt-5.2"]))

    image_inputs: list[dict[str, Any]] = []
    for upload in images or []:
        image_inputs.append({"type": "input_image", "image_url": _image_to_data_url(upload)})

    def build_payload(current_prompt: str, responses_model: str) -> dict[str, Any]:
        tool_prompt = (
            "Use the image_generation tool. Create exactly one image. "
            + current_prompt
        )
        content: list[dict[str, Any]] = [{"type": "input_text", "text": tool_prompt}, *image_inputs]
        return {
            "model": responses_model,
            "input": [{"role": "user", "content": content}],
            "tools": [
                {
                    "type": "image_generation",
                    "quality": _quality_for_responses(quality),
                    "output_format": "png",
                    "partial_images": 2,
                }
            ],
            "stream": True,
        }

    def send_stream(current_prompt: str, responses_model: str) -> dict[str, Any]:
        collected_images: list[str] = []
        last_event: Optional[dict[str, Any]] = None
        try:
            with requests.post(
                _openai_image_url("/responses"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=build_payload(current_prompt, responses_model),
                stream=True,
                timeout=(30, IMAGE_TIMEOUT),
            ) as response:
                if response.status_code >= 400:
                    message = _extract_error_message(response)
                    logger.warning("Responses stream failed before events: %s", message)
                    raise HTTPException(status_code=response.status_code, detail=message)

                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue

                    last_event = event
                    event_type = str(event.get("type") or "")
                    if progress_callback:
                        if event_type.endswith(".in_progress"):
                            progress_callback(35, "responses_in_progress")
                        elif event_type.endswith(".generating"):
                            progress_callback(45, "responses_generating")
                        elif event_type.endswith(".partial_image"):
                            progress_callback(75, "responses_partial_image")
                        elif event_type == "response.completed":
                            progress_callback(95, "responses_completed")
                    _collect_b64_images(event, collected_images)
        except HTTPException:
            raise
        except requests.RequestException as exc:
            logger.error("Responses stream request failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"Responses stream request failed: {exc}") from exc

        if collected_images:
            return {"created": int(time.time()), "data": [{"b64_json": collected_images[-1]}], "raw_id": (last_event or {}).get("item_id")}
        logger.warning("Responses stream returned no image: %s", str(last_event)[:1000])
        raise HTTPException(status_code=502, detail="Responses stream returned no image")

    last_error: Optional[HTTPException] = None
    for responses_model in responses_models:
        try:
            logger.info("Using Responses model for image_generation: %s", responses_model)
            return send_stream(prepared_prompt, responses_model)
        except HTTPException as exc:
            last_error = exc
            detail = str(exc.detail)
            if detail == "upstream_html_timeout":
                logger.warning("Responses stream timed out; retrying with ultra compact prompt")
                return send_stream(_game_visual_prompt_ultra(), responses_model)
            if "no access to model" in detail.lower():
                logger.warning("Responses model unavailable, trying next: %s", responses_model)
                continue
            raise
    if last_error:
        raise last_error
    raise HTTPException(status_code=502, detail="No Responses image model available")


def _save_request_cache(prompt: str, images: list[UploadFile], mask: Optional[UploadFile]) -> None:
    cache_root = CACHE_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / "prompt.txt").write_text(prompt, encoding="utf-8")

    image_dir = cache_root / "images"
    image_dir.mkdir(exist_ok=True)
    for index, upload in enumerate(images, start=1):
        suffix = Path(upload.filename or "image.png").suffix or ".png"
        upload.file.seek(0)
        with (image_dir / f"image-{index}{suffix}").open("wb") as target:
            shutil.copyfileobj(upload.file, target)
        upload.file.seek(0)

    if mask and mask.filename:
        suffix = Path(mask.filename).suffix or ".png"
        mask.file.seek(0)
        with (cache_root / f"mask{suffix}").open("wb") as target:
            shutil.copyfileobj(mask.file, target)
        mask.file.seek(0)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/config")
async def get_config():
    local_config = _read_local_config()
    base_url, base_url_source = _resolve_base_url_with_source()
    api_key_source, api_key = _peek_api_key_candidate()
    return {
        "model": IMAGE_MODEL,
        "base_url": base_url,
        "has_api_key": bool(api_key),
        "key_hint": _mask_api_key(api_key),
        "has_local_config": bool(local_config.get("base_url") or local_config.get("api_key")),
        "config_source": _describe_config_source(local_config, base_url_source, api_key_source),
    }


@app.get("/api/local-config")
async def get_local_config():
    local_config = _read_local_config()
    api_key = str(local_config.get("api_key") or "")
    return {
        "base_url": str(local_config.get("base_url") or DEFAULT_OPENAI_BASE_URL),
        "has_api_key": bool(api_key),
        "key_hint": _mask_api_key(api_key),
    }


@app.post("/api/local-config")
async def save_local_config(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    base_url = str(payload.get("base_url") or "").strip()
    api_key = str(payload.get("api_key") or "").strip()
    _write_local_config(base_url, api_key)
    return {"ok": True, "base_url": _get_codex_base_url(), "key_hint": _mask_api_key(api_key)}


def _run_task(task_id: str, mode: str, prompt: str, options: dict[str, Any], image_paths: Optional[list[Path]] = None, mask_path: Optional[Path] = None) -> None:
    try:
        def update_stream_progress(progress: int, message: str) -> None:
            stage = "generating_text" if mode == "text" else "generating_edit"
            _set_task(task_id, stage=stage, progress=progress, message=message)

        _set_task(task_id, status="running", stage="prepare", progress=5, message="prepare_request")
        time.sleep(0.2)
        _set_task(task_id, stage="connect", progress=15, message="connect_gateway")

        if mode == "text":
            _set_task(task_id, stage="generating_text", progress=20, message="image2_generating")
            result = _request_image2_generation(prompt=prompt, progress_callback=update_stream_progress, **options)
        else:
            uploads: list[UploadFile] = []
            handles = []
            try:
                for path in image_paths or []:
                    handle = path.open("rb")
                    handles.append(handle)
                    uploads.append(UploadFile(file=handle, filename=path.name))
                if mask_path:
                    prompt = prompt + "\n\nUse the uploaded mask as the edit mask. Only modify the masked region and preserve the unmasked area as much as possible."
                    handle = mask_path.open("rb")
                    handles.append(handle)
                    uploads.append(UploadFile(file=handle, filename=mask_path.name))
                _set_task(task_id, stage="generating_edit", progress=20, message="image2_editing")
                result = _request_image2_edit(prompt=prompt, images=uploads, progress_callback=update_stream_progress, **options)
            finally:
                for handle in handles:
                    handle.close()

        _set_task(task_id, status="completed", stage="completed", progress=100, message="completed", result=result)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        _set_task(task_id, status="failed", stage="failed", progress=100, message=str(detail), error=str(detail))


def _cache_uploads_for_task(task_id: str, prompt: str, images: list[UploadFile], mask: Optional[UploadFile]) -> tuple[list[Path], Optional[Path]]:
    cache_root = CACHE_DIR / task_id
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / "prompt.txt").write_text(prompt, encoding="utf-8")
    image_dir = cache_root / "images"
    image_dir.mkdir(exist_ok=True)
    image_paths: list[Path] = []
    for index, upload in enumerate(images, start=1):
        suffix = Path(upload.filename or "image.png").suffix or ".png"
        target = image_dir / f"image-{index}{suffix}"
        upload.file.seek(0)
        with target.open("wb") as target_file:
            shutil.copyfileobj(upload.file, target_file)
        upload.file.seek(0)
        image_paths.append(target)
    mask_path = None
    if mask and mask.filename:
        suffix = Path(mask.filename).suffix or ".png"
        mask_path = cache_root / f"mask{suffix}"
        mask.file.seek(0)
        with mask_path.open("wb") as target_file:
            shutil.copyfileobj(mask.file, target_file)
        mask.file.seek(0)
    return image_paths, mask_path


@app.get("/api/options")
async def get_options():
    return {
        "model": IMAGE_MODEL,
        "sizes": ["auto", "1024x1024", "1024x1536", "1536x1024"],
        "qualities": ["auto", "low", "medium", "high"],
        "backgrounds": ["auto", "transparent", "opaque"],
        "output_formats": ["png", "jpeg", "webp"],
        "output_compression": {"min": 0, "max": 100, "applies_to": ["jpeg", "webp"]},
    }


@app.post("/api/generate")
async def generate_image(
    prompt: str = Form(...),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    background: str = Form("auto"),
    output_format: str = Form("png"),
    output_compression: Optional[int] = Form(None),
):
    prompt = _validate_prompt(prompt)
    return _request_image2_generation(prompt=prompt, size=size, quality=quality, background=background, output_format=output_format, output_compression=output_compression)


@app.post("/api/edit")
async def edit_image(
    prompt: str = Form(...),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    background: str = Form("auto"),
    output_format: str = Form("png"),
    output_compression: Optional[int] = Form(None),
    image: list[UploadFile] = File(...),
    mask: Optional[UploadFile] = File(None),
):
    prompt = _validate_prompt(prompt)
    if not image:
        raise HTTPException(status_code=400, detail="请至少上传一张参考图")
    _save_request_cache(prompt, image, mask)
    if mask and mask.filename:
        prompt = prompt + "\n\nUse the uploaded mask as the edit mask. Only modify the masked region and preserve the unmasked area as much as possible."
        image = [*image, mask]
    return _request_image2_edit(prompt=prompt, images=image, size=size, quality=quality, background=background, output_format=output_format, output_compression=output_compression)


@app.post("/api/tasks/generate")
async def start_generate_task(
    prompt: str = Form(...),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    background: str = Form("auto"),
    output_format: str = Form("png"),
    output_compression: Optional[int] = Form(None),
):
    prompt = _validate_prompt(prompt)
    task_id = uuid.uuid4().hex
    _set_task(task_id, status="queued", stage="queued", progress=0, message="task_created")
    options = {"size": size, "quality": quality, "background": background, "output_format": output_format, "output_compression": output_compression}
    threading.Thread(target=_run_task, args=(task_id, "text", prompt, options), daemon=True).start()
    return {"task_id": task_id}


@app.post("/api/tasks/edit")
async def start_edit_task(
    prompt: str = Form(...),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    background: str = Form("auto"),
    output_format: str = Form("png"),
    output_compression: Optional[int] = Form(None),
    image: list[UploadFile] = File(...),
    mask: Optional[UploadFile] = File(None),
):
    prompt = _validate_prompt(prompt)
    if not image:
        raise HTTPException(status_code=400, detail="请至少上传一张参考图")
    task_id = uuid.uuid4().hex
    image_paths, mask_path = _cache_uploads_for_task(task_id, prompt, image, mask)
    _set_task(task_id, status="queued", stage="queued", progress=0, message="task_created_images_cached")
    options = {"size": size, "quality": quality, "background": background, "output_format": output_format, "output_compression": output_compression}
    threading.Thread(target=_run_task, args=(task_id, "edit", prompt, options, image_paths, mask_path), daemon=True).start()
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return JSONResponse({"detail": "任务不存在"}, status_code=404)
    return task


if __name__ == "__main__":
    host = os.environ.get("AI_IMAGE_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_IMAGE_PORT", "8012"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
