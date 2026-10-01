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
]


def get_sheet():
    client = gspread.service_account(filename="/app/credentials.json")
    spreadsheet = client.open_by_key(SHEET_ID)
    return spreadsheet.worksheet(SHEET_NAME)


def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Доход", "➖ Расход"],
            ["📊 Итоги", "📂 Категории"],
        ],
        resize_keyboard=True,
    )


def category_keyboard():
    buttons = []

    for i in range(0, len(CATEGORIES), 2):
        buttons.append(CATEGORIES[i:i + 2])

    buttons.append(["↩️ Отмена"])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я помогу вести твой бюджет.\n"
        "Выбери действие:",
        reply_markup=main_keyboard(),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Отмена
    if text == "↩️ Отмена":
        context.user_data.clear()

        await update.message.reply_text(
            "Отменено.\n\nГлавное меню:",
            reply_markup=main_keyboard(),
        )
        return

    # Доход
    if text == "➕ Доход":
        context.user_data["type"] = "income"
        context.user_data["step"] = "amount"

        await update.message.reply_text(
            "💰 Введи сумму дохода:",
            reply_markup=ReplyKeyboardMarkup(
                [["↩️ Отмена"]],
                resize_keyboard=True,
            ),
        )
        return

    # Расход
    if text == "➖ Расход":
        context.user_data["type"] = "expense"
        context.user_data["step"] = "category"

        await update.message.reply_text(
            "📂 Выбери категорию:",
            reply_markup=category_keyboard(),
        )
        return

    # Категории
    if text == "📂 Категории":
        await update.message.reply_text(
            "📂 Твои категории:",
            reply_markup=category_keyboard(),
        )
        return

    # Итоги
    if text == "📊 Итоги":
        try:
            sheet = get_sheet()
            rows = sheet.get_all_values()

            total_income = 0
            total_expense = 0

            current_month = datetime.now().strftime("%m.%Y")

            for row in rows[1:]:
                if not row:
                    continue

                date = row[0] if len(row) > 0 else ""

                if current_month not in date:
                    continue

                try:
                    if len(row) > 3 and row[3]:
                        total_income += float(
                            str(row[3]).replace(",", ".").replace(" ", "")
                        )
                except ValueError:
                    pass

                try:
                    if len(row) > 4 and row[4]:
                        total_expense += float(
                            str(row[4]).replace(",", ".").replace(" ", "")
                        )
                except ValueError:
                    pass

            balance = total_income - total_expense

            await update.message.reply_text(
                "📊 Итоги за текущий месяц\n\n"
                f"💰 Доходы: {total_income:,.2f}\n"
                f"💸 Расходы: {total_expense:,.2f}\n"
                f"🏦 Остаток: {balance:,.2f}",
                reply_markup=main_keyboard(),
            )

        except Exception as e:
            print("ОШИБКА:", e)

            await update.message.reply_text(
                "😔 Не удалось получить итоги.\n"
                "Посмотри ошибку в чёрном окне.",
                reply_markup=main_keyboard(),
            )

        return

    # Выбор категории
    step = context.user_data.get("step")

    if step == "category":
        if text not in CATEGORIES:
            await update.message.reply_text(
                "Пожалуйста, выбери категорию кнопкой.",
                reply_markup=category_keyboard(),
            )
            return

        context.user_data["category"] = text
        context.user_data["step"] = "amount"

        await update.message.reply_text(
            "💵 Теперь введи сумму:",
            reply_markup=ReplyKeyboardMarkup(
                [["↩️ Отмена"]],
                resize_keyboard=True,
            ),
        )
        return

    # Ввод суммы
    if step == "amount":
        try:
            amount = float(
                text.replace(" ", "").replace(",", ".")
            )
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введи сумму числом.\n"
                "Например: 1500",
            )
            return

        if amount <= 0:
            await update.message.reply_text(
                "Сумма должна быть больше нуля."
            )
            return

        context.user_data["amount"] = amount

        if context.user_data["type"] == "income":
            context.user_data["category"] = "Доход"

        context.user_data["step"] = "description"

        await update.message.reply_text(
            "📝 Напиши описание.\n\n"
            "Например: зарплата, продукты на неделю.\n\n"
            "Если описание не нужно — напиши: -",
            reply_markup=ReplyKeyboardMarkup(
                [["↩️ Отмена"]],
                resize_keyboard=True,
            ),
        )
        return

    # Ввод описания
    if step == "description":
        description = text

        if description == "-":
            description = ""

        try:
            sheet = get_sheet()

            date = datetime.now().strftime("%d.%m.%Y")

            income = ""
            expense = ""

            if context.user_data["type"] == "income":
                income = context.user_data["amount"]
            else:
                expense = context.user_data["amount"]

            row = [
                date,
                context.user_data["category"],
                description,
                income,
                expense,
                "",
            ]

            sheet.append_row(row)

            await update.message.reply_text(
                "✅ Записала в таблицу!\n\n"
                f"📅 {date}\n"
                f"📂 {context.user_data['category']}\n"
                f"💵 {context.user_data['amount']}\n"
                f"📝 {description if description else 'Без описания'}",
                reply_markup=main_keyboard(),
            )

            context.user_data.clear()

        except Exception as e:
            print("ОШИБКА:", e)

            await update.message.reply_text(
                "😔 Не удалось записать данные в таблицу.\n"
                "Посмотри ошибку в чёрном окне."
            )

        return

    await update.message.reply_text(
        "Выбери действие кнопкой ниже:",
        reply_markup=main_keyboard(),
    )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("Токен Telegram не найден!")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("Бот запущен!")

    app.run_polling()


if __name__ == "__main__":
    main()
