"""Pick the active OpenRouter model at runtime.

Flow:
  /admin_model [filter]  →  fetches /v1/models from OpenRouter, filters by
                            substring (if passed), sorts by prompt price,
                            shows a numbered list (top 30) + FSM prompt.
  <admin replies with N> →  resolves list[N-1] and pins it in Redis.

summary.generate_summary reads the active model via admin_model.get_active_model
on every call, so the switch takes effect without a restart.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.handlers.admin._common import guard
from src.bot.states import AdminFlow
from src.config import settings
from src.db.models.user import User
from src.utils import admin_model
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)

_PAGE_SIZE = 30


@router.message(Command("admin_model"))
async def cmd_admin_model(
    message: Message, user: User, state: FSMContext
) -> None:
    if not await guard(user):
        return

    parts = (message.text or "").split(maxsplit=1)
    query = parts[1].strip().lower() if len(parts) == 2 else ""

    try:
        models = await _fetch_openrouter_models()
    except Exception as e:
        logger.warning("admin_model_fetch_failed", exc_info=True)
        await message.answer(f"❌ Не удалось получить список моделей: {e}")
        return

    # Only chat-capable, text-input models.
    models = [m for m in models if _is_chat(m)]
    if query:
        models = [m for m in models if query in m["id"].lower()]
    # Sort by prompt price asc (free models bubble up).
    models.sort(key=lambda m: _price(m))
    models = models[:_PAGE_SIZE]

    if not models:
        await message.answer("Ничего не нашлось. Попробуй без фильтра: /admin_model")
        return

    active = await admin_model.get_active_model()

    lines = [f"<b>Выбери модель (сейчас: <code>{active}</code>)</b>\n"]
    for idx, m in enumerate(models, 1):
        mid = m["id"]
        prompt_price = _price(m)
        price_str = "🆓" if prompt_price == 0 else f"${prompt_price * 1000:.3f}/1K"
        marker = "⭐️ " if mid == active else ""
        lines.append(f"{idx}. {marker}<code>{mid}</code> — {price_str}")
    lines.append("\nПришли номер одним сообщением. /cancel — отмена.")

    await admin_model.save_model_list(user.id, [m["id"] for m in models])
    await state.set_state(AdminFlow.selecting_model)
    await message.answer(
        "\n".join(lines)[:4000],
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(AdminFlow.selecting_model)
async def on_model_number(
    message: Message, user: User, state: FSMContext
) -> None:
    if not await guard(user):
        await state.clear()
        return

    text = (message.text or "").strip()
    try:
        idx = int(text)
    except ValueError:
        await message.answer("Нужно число. Попробуй ещё раз или /cancel.")
        return

    models = await admin_model.load_model_list(user.id)
    if not models:
        await state.clear()
        await message.answer("Список устарел. Запусти /admin_model заново.")
        return
    if idx < 1 or idx > len(models):
        await message.answer(f"Номер вне диапазона 1..{len(models)}.")
        return

    selected = models[idx - 1]
    await admin_model.set_active_model(selected)
    await state.clear()
    logger.info("admin_model_switched", admin_id=user.id, model=selected)
    await message.answer(
        f"✅ Активная модель: <code>{selected}</code>",
        parse_mode="HTML",
    )


# ---------- helpers ----------

async def _fetch_openrouter_models() -> list[dict]:
    import httpx

    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY не задан в .env")

    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
        )
        response.raise_for_status()
        data = response.json()
    return data.get("data", [])


def _is_chat(model: dict) -> bool:
    """Keep only models that can do chat-style text completion."""
    arch = model.get("architecture", {}) or {}
    modality = (arch.get("modality") or "").lower()
    input_mods = arch.get("input_modalities") or []
    # OpenRouter models list has either `modality: "text->text"` or
    # `input_modalities: ["text", ...]`. Accept text-input models with
    # text output.
    if "text" in modality and "->" in modality and modality.endswith("text"):
        return True
    if "text" in input_mods:
        return True
    return False


def _price(model: dict) -> float:
    """Prompt price per token. 0.0 means free tier / unknown."""
    try:
        return float(model.get("pricing", {}).get("prompt", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
