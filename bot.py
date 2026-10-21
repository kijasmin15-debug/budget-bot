```python
import os
import gspread
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

SHEET_ID = "1OMWBEVsww6ftRVbYQOME7OpLiq9vk4I1_9kBFrBULCE"
SHEET_NAME = "Лист2"

CATEGORIES = [
    "🏠 Квартплата",
    "🛒 Продукты",
    "🏡 Дом",
    "🎁 Подарки",
    "🧴 Бытовая химия",
    "💰 Отложить",
    "🎭 Развлечения",
    "⚠️ Незапланированные траты",
    "💳 Платежи",
    "❤️ Здоровье",
    "🚗 Транспорт",
    "👩 Лена",
]

user_data = {}


def get_sheet():
    client = gspread.service_account(
        filename="/app/credentials.json"
    )
    spreadsheet = client.open_by_key(SHEET_ID)
    return spreadsheet.worksheet(SHEET_NAME)


def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Доход"],
            ["➖ Расход"],
            ["📊 Итоги", "📂 Категории"],
        ],
        resize_keyboard=True,
    )


def categories_keyboard():
    buttons = [
        CATEGORIES[i:i + 2]
        for i in range(0, len(CATEGORIES), 2)
    ]
    buttons.append(["↩️ Отмена"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.pop(update.effective_user.id, None)
    await update.message.reply_text(
        "Привет! 😊\n\nВыбери действие кнопкой ниже:",
        reply_markup=main_keyboard(),
    )


async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 Выбери категорию:",
        reply_markup=categories_keyboard(),
    )


async def expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {"action": "expense"}
    await update.message.reply_text(
        "📂 Выбери категорию:",
        reply_markup=categories_keyboard(),
    )


async def income_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {"action": "income"}
    await update.message.reply_text("💰 Введи сумму дохода:")


async def totals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        month = datetime.now().strftime("%m.%Y")

        income_total = 0.0
        expense_total = 0.0

        for row in rows[1:]:
            if len(row) < 5:
                continue

            try:
                date = datetime.strptime(row[0].strip(), "%d.%m.%Y")
            except (ValueError, IndexError):
                continue

            if date.strftime("%m.%Y") != month:
                continue

            try:
                value = row[3].replace(" ", "").replace(",", ".").strip()
                if value:
                    income_total += float(value)
            except (ValueError, IndexError):
                pass

            try:
                value = row[4].replace(" ", "").replace(",", ".").strip()
                if value:
                    expense_total += float(value)
            except (ValueError, IndexError):
                pass

        balance = income_total - expense_total

        await update.message.reply_text(
            f"📊 Итоги за {month}\n\n"
            f"Доходы: {income_total:.2f}\n"
            f"Расходы: {expense_total:.2f}\n"
            f"Баланс: {balance:.2f}"
        )

    except Exception as e:
        print(f"Ошибка итогов: {e}")
        await update.message.reply_text(
            "😔 Не удалось получить данные из таблицы."
        )


def append_operation(sheet, values):
    # Записываем только в колонки A–E.
    next_row = len(sheet.col_values(1)) + 1
    sheet.update(
        range_name=f"A{next_row}:E{next_row}",
        values=[values],
        value_input_option="USER_ENTERED",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "➕ Доход":
        await income_start(update, context)
        return

    if text == "➖ Расход":
        await expense_start(update, context)
        return

    if text == "📊 Итоги":
        await totals(update, context)
        return

    if text == "📂 Категории":
        await categories(update, context)
        return

    if text == "↩️ Отмена":
        user_data.pop(user_id, None)
        await update.message.reply_text(
            "Отменено.",
            reply_markup=main_keyboard(),
        )
        return

    data = user_data.get(user_id)
    if not data:
        return

    if data["action"] == "income" and "amount" not in data:
        try:
            amount = float(text.replace(",", "."))
            if amount <= 0:
                raise ValueError

            data["amount"] = amount
            await update.message.reply_text(
                "📝 Напиши описание дохода.\n\n"
                "Если описание не нужно — напиши: -"
            )
        except ValueError:
            await update.message.reply_text(
                "Введи положительную сумму, например: 500"
            )
        return

    if data["action"] == "income" and "amount" in data:
        description = "" if text == "-" else text
        try:
            sheet = get_sheet()
            today = datetime.now().strftime("%d.%m.%Y")
            append_operation(
                sheet,
                [today, "💰 Доход
