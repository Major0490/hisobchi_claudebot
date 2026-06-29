import os
import json
import sqlite3
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TOKEN = os.environ.get("BOT_TOKEN", "8951038010:AAHd_zcpCcCo4J9LpX1osZ5b5a5O3buXufs")

# Bank ma'lumotlari
BANKS = [
    {"name": "1-Bank", "qoldiq": 18_200_000, "oylik": 1_517_000, "oy": 12},
    {"name": "2-Bank", "qoldiq": 21_700_000, "oylik": 603_000, "oy": 36},
]
KREDIT_TOLOV = 3_920_000

# Conversation states
MENU, KIRIM_SUMMA, KIRIM_IZOH, XARAJAT_CAT, XARAJAT_SUMMA, XARAJAT_IZOH = range(6)

XARAJAT_KATEGORIYALAR = [
    "🍞 Oziq-ovqat", "🚗 Transport", "💡 Kommunal",
    "👕 Kiyim", "💊 Sog'liq", "📚 Ta'lim",
    "🎮 Ko'ngilochar", "🏦 Kredit to'lovi", "📦 Boshqa"
]

# ─── Database ───────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("hisobchi.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            category TEXT,
            amount REAL,
            note TEXT,
            date TEXT
        )
    """)
    conn.commit()
    return conn

def add_txn(user_id, type_, category, amount, note=""):
    db = get_db()
    db.execute(
        "INSERT INTO transactions (user_id, type, category, amount, note, date) VALUES (?,?,?,?,?,?)",
        (user_id, type_, category, amount, note, date.today().isoformat())
    )
    db.commit()
    db.close()

def get_stats(user_id):
    db = get_db()
    today = date.today()
    oy_start = today.replace(day=1).isoformat()

    all_kirim = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='kirim'", (user_id,)).fetchone()[0] or 0
    all_xarajat = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='xarajat'", (user_id,)).fetchone()[0] or 0
    oy_kirim = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='kirim' AND date>=?", (user_id, oy_start)).fetchone()[0] or 0
    oy_xarajat = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='xarajat' AND date>=?", (user_id, oy_start)).fetchone()[0] or 0
    last_txns = db.execute("SELECT type, category, amount, date FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()
    db.close()
    return all_kirim, all_xarajat, oy_kirim, oy_xarajat, last_txns

# ─── Helpers ────────────────────────────────────────────────────────────────
def fmt(n):
    return f"{int(n):,} so'm".replace(",", " ")

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Kirim qo'shish"), KeyboardButton("💸 Xarajat qo'shish")],
        [KeyboardButton("📊 Hisobot"), KeyboardButton("🏦 Kreditlar")],
        [KeyboardButton("📋 So'nggi 5 ta")],
    ], resize_keyboard=True)

# ─── Handlers ───────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men sizning shaxsiy *Moliyaviy Hisobchingizman!*\n\n"
        "Quyidagi tugmalardan foydalaning 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    return MENU

async def menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "💰 Kirim qo'shish":
        await update.message.reply_text("💰 Qancha kirim bo'ldi? (Faqat raqam yozing, masalan: 500000)")
        return KIRIM_SUMMA

    elif text == "💸 Xarajat qo'shish":
        cats = [XARAJAT_KATEGORIYALAR[i:i+2] for i in range(0, len(XARAJAT_KATEGORIYALAR), 2)]
        cats.append(["🔙 Orqaga"])
        await update.message.reply_text(
            "📂 Xarajat kategoriyasini tanlang:",
            reply_markup=ReplyKeyboardMarkup(cats, resize_keyboard=True)
        )
        return XARAJAT_CAT

    elif text == "📊 Hisobot":
        await show_hisobot(update)
        return MENU

    elif text == "🏦 Kreditlar":
        await show_kreditlar(update)
        return MENU

    elif text == "📋 So'nggi 5 ta":
        await show_last(update)
        return MENU

    return MENU

# ── Kirim ──
async def kirim_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(" ", "").replace(",", ""))
        ctx.user_data["kirim_amount"] = amount
        await update.message.reply_text("📝 Izoh qo'shing yoki /skip yozing:")
        return KIRIM_IZOH
    except:
        await update.message.reply_text("❌ Iltimos faqat raqam yozing! Masalan: 500000")
        return KIRIM_SUMMA

async def kirim_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = update.message.text if update.message.text != "/skip" else ""
    amount = ctx.user_data["kirim_amount"]
    user_id = update.effective_user.id
    add_txn(user_id, "kirim", "Kirim", amount, note)
    await update.message.reply_text(
        f"✅ *+{fmt(amount)}* kirim sifatida saqlandi!",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )
    return MENU

# ── Xarajat ──
async def xarajat_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Orqaga":
        await update.message.reply_text("Bosh menyu:", reply_markup=main_keyboard())
        return MENU
    ctx.user_data["xarajat_cat"] = text
    await update.message.reply_text(f"💸 {text} uchun summa? (Masalan: 50000)")
    return XARAJAT_SUMMA

async def xarajat_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(" ", "").replace(",", ""))
        ctx.user_data["xarajat_amount"] = amount
        await update.message.reply_text("📝 Izoh qo'shing yoki /skip:")
        return XARAJAT_IZOH
    except:
        await update.message.reply_text("❌ Faqat raqam yozing!")
        return XARAJAT_SUMMA

async def xarajat_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = update.message.text if update.message.text != "/skip" else ""
    amount = ctx.user_data["xarajat_amount"]
    cat = ctx.user_data["xarajat_cat"]
    user_id = update.effective_user.id
    add_txn(user_id, "xarajat", cat, amount, note)
    await update.message.reply_text(
        f"✅ *-{fmt(amount)}* ({cat}) saqlandi!",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )
    return MENU

# ── Hisobot ──
async def show_hisobot(update: Update):
    user_id = update.effective_user.id
    all_kirim, all_xarajat, oy_kirim, oy_xarajat, _ = get_stats(user_id)
    oy_balans = oy_kirim - oy_xarajat - KREDIT_TOLOV
    umumiy = all_kirim - all_xarajat

    emoji = "🟢" if oy_balans >= 0 else "🔴"

    text = (
        "📊 *MOLIYAVIY HISOBOT*\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "📅 *Bu oy:*\n"
        f"  💰 Kirim: +{fmt(oy_kirim)}\n"
        f"  💸 Xarajat: -{fmt(oy_xarajat)}\n"
        f"  🏦 Kredit: -{fmt(KREDIT_TOLOV)}\n"
        f"  {emoji} Sof qoldiq: {'+' if oy_balans>=0 else ''}{fmt(oy_balans)}\n\n"
        "📦 *Jami (barcha vaqt):*\n"
        f"  💰 Kirim: +{fmt(all_kirim)}\n"
        f"  💸 Xarajat: -{fmt(all_xarajat)}\n"
        f"  {'🟢' if umumiy>=0 else '🔴'} Balans: {'+' if umumiy>=0 else ''}{fmt(umumiy)}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ── Kreditlar ──
async def show_kreditlar(update: Update):
    text = "🏦 *KREDIT HOLATI*\n━━━━━━━━━━━━━━━━\n\n"
    for b in BANKS:
        text += (
            f"🏛 *{b['name']}*\n"
            f"  💳 Qoldiq: {fmt(b['qoldiq'])}\n"
            f"  📅 Oylik: {fmt(b['oylik'])}\n"
            f"  ⏳ Qolgan: {b['oy']} oy\n\n"
        )
    text += (
        "💡 *Strategiya:*\n"
        "1-bank 12 oyda tugaydi ✅\n"
        "Keyin bo'shagan 1 517 000 so'mni\n"
        "2-bankka qo'shing → 36 o'rniga\n"
        "~12 oyda tugaydi! 🚀"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ── So'nggi 5 ──
async def show_last(update: Update):
    user_id = update.effective_user.id
    _, _, _, _, txns = get_stats(user_id)
    if not txns:
        await update.message.reply_text("📋 Hali yozuvlar yo'q.")
        return
    text = "📋 *SO'NGGI 5 TA YOZUV*\n━━━━━━━━━━━━━━━━\n\n"
    for t in txns:
        emoji = "💰" if t[0] == "kirim" else "💸"
        sign = "+" if t[0] == "kirim" else "-"
        text += f"{emoji} {t[1]}: {sign}{fmt(t[2])} ({t[3]})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT, menu_handler)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            KIRIM_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, kirim_summa)],
            KIRIM_IZOH: [MessageHandler(filters.TEXT, kirim_izoh), CommandHandler("skip", kirim_izoh)],
            XARAJAT_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, xarajat_cat)],
            XARAJAT_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, xarajat_summa)],
            XARAJAT_IZOH: [MessageHandler(filters.TEXT, xarajat_izoh), CommandHandler("skip", xarajat_izoh)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
