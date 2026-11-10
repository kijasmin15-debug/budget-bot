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
    "🏠 Квартплата и дом",
    "🧴 Бытовая химия",
    "🎭 Развлечения",
    "💳 Платежи",
    "🚗 Транспорт",
    "🛒 Продукты",
    "🎁 Подарки",
    "💰 Отложить",
    "⚠️ Незапланированные траты",
    "❤️ Здоровье",
    "👩 Лена",
    "👨 Родион",
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

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
    )


def append_operation(sheet, values):
    dates = sheet.col_values(1)
    next_row = max(len(dates) + 1, 2)

    sheet.update(
        range_name=f"A{next_row}:E{next_row}",
        values=[values],
        value_input_option="USER_ENTERED",
    )


def parse_amount(value):
    value = (
        str(value)
        .replace("\u00a0", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )

    return float(value)


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


async def income_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {
        "action": "income"
    }

    await update.message.reply_text(
        "💰 Введи сумму дохода:"
    )


async def expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {
        "action": "expense"
    }

    await update.message.reply_text(
        "📂 Выбери категорию:",
        reply_markup=categories_keyboard(),
    )


async def totals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sheet = get_sheet()
        rows = sheet.get("A2:E")

        month = datetime.now().strftime("%m.%Y")

        income_total = 0.0
        expense_total = 0.0

        category_totals = {
            category: 0.0
            for category in CATEGORIES
        }

        for row in rows:
            row = row + [""] * (5 - len(row))

            try:
                date = datetime.strptime(
                    row[0].strip(),
                    "%d.%m.%Y"
                )
            except (ValueError, TypeError):
                continue

            if date.strftime("%m.%Y") != month:
                continue

            category = row[1].strip()

            try:
                income = parse_amount(row[3]) if row[3].strip() else 0.0
            except (ValueError, TypeError):
                income = 0.0

            try:
                expense = parse_amount(row[4]) if row[4].strip() else 0.0
            except (ValueError, TypeError):
                expense = 0.0

            income_total += income
            expense_total += expense

            # Старые категории объединяем с новой категорией.
            if category in (
                "🏠 Квартплата",
                "🏡 Дом",
                "Квартплата",
                "Дом",
            ):
                category = "🏠 Квартплата и дом"

            if category in category_totals:
                category_totals[category] += expense

        balance = income_total - expense_total

        message = (
            f"📊 Итоги за {month}\n\n"
            f"💰 Доходы: {income_total:.2f}\n"
            f"💸 Расходы: {expense_total:.2f}\n"
            f"⚖️ Баланс: {balance:.2f}\n\n"
            f"📂 Расходы по категориям:\n"
        )

        for category in CATEGORIES:
            message += (
                f"\n{category}: "
                f"{category_totals[category]:.2f}"
            )

        await update.message.reply_text(message)

    except Exception as e:
        print(f"Ошибка итогов: {e}")

        await update.message.reply_text(
            "😔 Не удалось получить данные из таблицы."
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

    # ДОХОД — СУММА

    if data["action"] == "income" and "amount" not in data:
        try:
            amount = parse_amount(text)

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

    # ДОХОД — ЗАПИСЬ

    if data["action"] == "income" and "amount" in data:
        description = "" if text == "-" else text

        try:
            sheet = get_sheet()
            today = datetime.now().strftime("%d.%m.%Y")

            append_operation(
                sheet,
                [
                    today,
                    "💰 Доход",
                    description,
                    data["amount"],
                    "",
                ],
            )

            user_data.pop(user_id, None)

            await update.message.reply_text(
                "✅ Доход записан в таблицу!",
                reply_markup=main_keyboard(),
            )

        except Exception as e:
            print(f"Ошибка записи дохода: {e}")

            await update.message.reply_text(
                "😔 Не удалось записать доход в таблицу."
            )

        return

    # РАСХОД — КАТЕГОРИЯ

    if data["action"] == "expense" and "category" not in data:
        if text not in CATEGORIES:
            await update.message.reply_text(
                "Пожалуйста, выбери категорию кнопкой."
            )
            return

        data["category"] = text

        await update.message.reply_text(
            "💰 Теперь введи сумму:"
        )

        return

    # РАСХОД — СУММА

    if data["action"] == "expense" and "amount" not in data:
        try:
            amount = parse_amount(text)

            if amount <= 0:
                raise ValueError

            data["amount"] = amount

            await update.message.reply_text(
                "📝 Напиши описание.\n\n"
                "Если описание не нужно — напиши: -"
            )

        except ValueError:
            await update.message.reply_text(
                "Введи положительную сумму, например: 500"
            )

        return

    # РАСХОД — ЗАПИСЬ

    if data["action"] == "expense" and "amount" in data:
        description = "" if text == "-" else text

        try:
            sheet = get_sheet()
            today = datetime.now().strftime("%d.%m.%Y")

            append_operation(
                sheet,
                [
                    today,
                    data["category"],
                    description,
                    "",
                    data["amount"],
                ],
            )

            user_data.pop(user_id, None)

            await update.message.reply_text(
                "✅ Расход записан в таблицу!",
                reply_markup=main_keyboard(),
            )

        except Exception as e:
            print(f"Ошибка записи расхода: {e}")

            await update.message.reply_text(
                "😔 Не удалось записать данные в таблицу."
            )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("Токен Telegram не найден!")
        return

    app = Application.builder().token(token).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("Бот запущен!")

    app.run_polling()


if __name__ == "__main__":
    main()
