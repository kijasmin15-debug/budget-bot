
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


async def income_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {"action": "income"}
    await update.message.reply_text("💰 Введи сумму дохода:")


async def expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {"action": "expense"}
    await update.message.reply_text(
        "📂 Выбери категорию:",
        reply_markup=categories_keyboard(),
    )


def append_operation(sheet, values):
    # Находим последнюю заполненную строку именно в столбце A.
    dates = sheet.col_values(1)
    next_row = max(len(dates) + 1, 2)

    # Записываем только в A:E, не затрагивая данные справа.
    sheet.update(
        range_name=f"A{next_row}:E{next_row}",
        values=[values],
        value_input_option="USER_ENTERED",
    )


async def totals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sheet = get_sheet()
        rows = sheet.get("A2:E")

        month = datetime.now().strftime("%m.%Y")
        income_total = 0.0
        expense_total = 0.0

        for row in rows:
            if len(row) < 5:
                row = row + [""] * (5 - len(row))

            try:
                date = datetime.strptime(
                    row[0].strip(), "%d.%m.%Y"
                )
            except (ValueError, TypeError):
                continue

            if date.strftime("%m.%Y") != month:
                continue

            try:
                value = row[3].replace(" ", "").replace(",", ".").strip()
                if value:
                    income_total += float(value)
            except (ValueError, TypeError):
                pass

            try:
                value = row[4].replace(" ", "").replace(",", ".").strip()
                if value:
                    expense_total += float(value)
            except (ValueError, TypeError):
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
                [today, "💰 Доход", description, data["amount"], ""],
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

    if data["action"] == "expense" and "category" not in data:
        if text not in CATEGORIES:
            await update.message.reply_text(
                "Пожалуйста, выбери категорию кнопкой."
            )
            return

        data["category"] = text
        await update.message.reply_text("💰 Теперь введи сумму:")
        return

    if data["action"] == "expense" and "amount" not in data:
        try:
            amount = float(text.replace(",", "."))
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

    if data["action"] == "expense" and "amount" in data:
        description = "" if text == "-" else text

        try:
            sheet = get_sheet()
            today = datetime.now().strftime("%d.%m.%Y")
            append_operation(
                sheet,
                [today, data["category"], description, "", data["amount"]],
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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()

