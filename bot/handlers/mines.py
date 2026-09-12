from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from sqlalchemy.ext.asyncio import AsyncSession

from db.repo import UserRepo
from services.mines import new_field, multiplier, SIZE

router = Router()
ACTIVE: dict[int, dict] = {}


def field_kb(game: dict) -> InlineKeyboardMarkup:
    opened = game["opened"]
    rows = []
    for r in range(SIZE):
        row = []
        for c in range(SIZE):
            idx = r * SIZE + c
            text = "💎" if idx in opened else "⬜"
            row.append(InlineKeyboardButton(
                text=text,
                callback_data=f"mn:open:{idx}"
            ))
        rows.append(row)

    if opened:
        mult = multiplier(len(opened), game["mines"])
        win = int(game["bet"] * mult)
        rows.append([InlineKeyboardButton(
            text=f"💰 Забрать {win:,} ⭐",
            callback_data="mn:cashout"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("mines"))
@router.message(F.text == "💣 Мины")
async def cmd_mines(msg: Message, session: AsyncSession):
    args = msg.text.split()
    bet = 1000
    mines = 3
    if len(args) > 1 and args[1].isdigit():
        bet = int(args[1])
    if len(args) > 2 and args[2].isdigit():
        mines = int(args[2])

    user = await UserRepo(session).get_by_tg(msg.from_user.id)
    if not user:
        await msg.answer("Сначала /start")
        return
    if bet < 100 or bet > user.balance:
        await msg.answer(f"❌ Ставка от 100 до {user.balance:,} ⭐")
        return
    if mines < 1 or mines > 24:
        await msg.answer("❌ Мин от 1 до 24")
        return

    user.balance -= bet
    await session.commit()

    game = {
        "bet": bet,
        "mines": mines,
        "field": new_field(mines),
        "opened": set(),
    }
    ACTIVE[msg.from_user.id] = game

    await msg.answer(
        f"💣 <b>Мины</b>\n"
        f"Ставка: <b>{bet:,} ⭐</b>\n"
        f"Мин: <b>{mines}</b>\n"
        f"Открывай клетки, забирай вовремя!",
        reply_markup=field_kb(game),
    )


@router.callback_query(F.data.startswith("mn:"))
async def on_mine(cb: CallbackQuery, session: AsyncSession):
    parts = cb.data.split(":")
    action = parts[1]
    game = ACTIVE.get(cb.from_user.id)
    if not game:
        await cb.answer("Игра не найдена. /mines")
        return

    if action == "open":
        idx = int(parts[2])
        if idx in game["opened"]:
            await cb.answer("Уже открыто")
            return

        if idx in game["field"]:
            ACTIVE.pop(cb.from_user.id, None)
            await cb.message.edit_text(
                f"💥 <b>Бум!</b> Попал на мину.\n"
                f"Потеряно: <b>{game['bet']:,} ⭐</b>"
            )
            await cb.answer("💥")
            return

        game["opened"].add(idx)
        await cb.message.edit_reply_markup(reply_markup=field_kb(game))
        mult = multiplier(len(game["opened"]), game["mines"])
        await cb.answer(f"💎 x{mult}")

    elif action == "cashout":
        opened = len(game["opened"])
        if opened == 0:
            await cb.answer("Открой хоть одну клетку")
            return

        mult = multiplier(opened, game["mines"])
        win = int(game["bet"] * mult)
        ACTIVE.pop(cb.from_user.id, None)

        user = await UserRepo(session).get_by_tg(cb.from_user.id)
        user.balance += win
        user.total_won += (win - game["bet"])
        await session.commit()

        await cb.message.edit_text(
            f"💰 <b>Забрал!</b>\n"
            f"Множитель: <b>x{mult}</b>\n"
            f"Выигрыш: <b>+{win:,} ⭐</b>\n"
            f"Баланс: <b>{user.balance:,} ⭐</b>"
        )
        await cb.answer("✅")