import os
import sqlite3
from datetime import date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TOKEN = os.environ.get("BOT_TOKEN", "")

BANKS = [
    {"name": "1-Bank", "qoldiq": 18_200_000, "oylik": 1_517_000, "oy": 12},
    {"name": "2-Bank", "qoldiq": 21_700_000, "oylik": 603_000, "oy": 36},
]
KREDIT_TOLOV = 3_920_000

MENU, KIRIM_SUMMA, KIRIM_IZOH, XARAJAT_CAT, XARAJAT_SUMMA, XARAJAT_IZOH = range(6)

XARAJAT_KATEGORIYALAR = [
    "🍞 Oziq-ovqat", "🚗 Transport", "💡 Kommunal",
    "👕 Kiyim", "💊 Sogliq", "📚 Talim",
    "🎮 Kongilochar", "🏦 Kredit tolovi", "📦 Boshqa"
]

def get_db():
    conn = sqlite3.connect("/tmp/hisobchi.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, type TEXT, category TEXT,
            amount REAL, note TEXT, date TEXT
        )
    """)
    conn.commit()
    return conn

def add_txn(user_id, type_, category, amount, note=""):
    db = get_db()
    db.execute(
        "INSERT INTO transactions (user_id,type,category,amount,note,date) VALUES (?,?,?,?,?,?)",
        (user_id, type_, category, amount, note, date.today().isoformat())
    )
    db.commit()
    db.close()

def get_stats(user_id):
    db = get_db()
    oy_start = date.today().replace(day=1).isoformat()
    a_k = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='kirim'", (user_id,)).fetchone()[0] or 0
    a_x = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='xarajat'", (user_id,)).fetchone()[0] or 0
    o_k = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='kirim' AND date>=?", (user_id, oy_start)).fetchone()[0] or 0
    o_x = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='xarajat' AND date>=?", (user_id, oy_start)).fetchone()[0] or 0
    last = db.execute("SELECT type,category,amount,date FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()
    db.close()
    return a_k, a_x, o_k, o_x, last

def fmt(n):
    return f"{int(n):,} som".replace(",", " ")

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Kirim qoshish"), KeyboardButton("💸 Xarajat qoshish")],
        [KeyboardButton("📊 Hisobot"), KeyboardButton("🏦 Kreditlar")],
        [KeyboardButton("📋 Songi 5 ta")],
    ], resize_keyboard=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men sizning shaxsiy *Moliyaviy Hisobchingizman!*\n\nQuyidagi tugmalardan foydalaning 👇",
        parse_mode="Markdown", reply_markup=main_kb()
    )
    return MENU

async def menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "💰 Kirim qoshish":
        await update.message.reply_text("💰 Qancha kirim boldі? (Faqat raqam, masalan: 500000)")
        return KIRIM_SUMMA
    elif text == "💸 Xarajat qoshish":
        cats = [XARAJAT_KATEGORIYALAR[i:i+2] for i in range(0, len(XARAJAT_KATEGORIYALAR), 2)]
        cats.append(["🔙 Orqaga"])
        await update.message.reply_text("📂 Kategoriyani tanlang:", reply_markup=ReplyKeyboardMarkup(cats, resize_keyboard=True))
        return XARAJAT_CAT
    elif text == "📊 Hisobot":
        await show_hisobot(update)
    elif text == "🏦 Kreditlar":
        await show_kreditlar(update)
    elif text == "📋 Songi 5 ta":
        await show_last(update)
    return MENU

async def kirim_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["k_amount"] = float(update.message.text.replace(" ", ""))
        await update.message.reply_text("📝 Izoh yozing yoki /skip:")
        return KIRIM_IZOH
    except:
        await update.message.reply_text("❌ Faqat raqam! Masalan: 500000")
        return KIRIM_SUMMA

async def kirim_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = "" if update.message.text == "/skip" else update.message.text
    add_txn(update.effective_user.id, "kirim", "Kirim", ctx.user_data["k_amount"], note)
    await update.message.reply_text(f"✅ *+{fmt(ctx.user_data['k_amount'])}* saqlandi!", parse_mode="Markdown", reply_markup=main_kb())
    return MENU

async def xarajat_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Orqaga":
        await update.message.reply_text("Bosh menyu:", reply_markup=main_kb())
        return MENU
    ctx.user_data["x_cat"] = update.message.text
    await update.message.reply_text(f"💸 {update.message.text} uchun summa?")
    return XARAJAT_SUMMA

async def xarajat_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["x_amount"] = float(update.message.text.replace(" ", ""))
        await update.message.reply_text("📝 Izoh yozing yoki /skip:")
        return XARAJAT_IZOH
    except:
        await update.message.reply_text("❌ Faqat raqam!")
        return XARAJAT_SUMMA

async def xarajat_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = "" if update.message.text == "/skip" else update.message.text
    add_txn(update.effective_user.id, "xarajat", ctx.user_data["x_cat"], ctx.user_data["x_amount"], note)
    await update.message.reply_text(f"✅ *-{fmt(ctx.user_data['x_amount'])}* saqlandi!", parse_mode="Markdown", reply_markup=main_kb())
    return MENU

async def show_hisobot(update: Update):
    uid = update.effective_user.id
    a_k, a_x, o_k, o_x, _ = get_stats(uid)
    ob = o_k - o_x - KREDIT_TOLOV
    text = (
        "📊 *MOLIYAVIY HISOBOT*\n━━━━━━━━━━━━━━\n\n"
        f"📅 *Bu oy:*\n"
        f"  💰 Kirim: +{fmt(o_k)}\n"
        f"  💸 Xarajat: -{fmt(o_x)}\n"
        f"  🏦 Kredit: -{fmt(KREDIT_TOLOV)}\n"
        f"  {'🟢' if ob>=0 else '🔴'} Sof: {'+' if ob>=0 else ''}{fmt(ob)}\n\n"
        f"📦 *Jami:*\n"
        f"  💰 Kirim: +{fmt(a_k)}\n"
        f"  💸 Xarajat: -{fmt(a_x)}\n"
        f"  {'🟢' if a_k-a_x>=0 else '🔴'} Balans: {fmt(a_k-a_x)}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def show_kreditlar(update: Update):
    text = "🏦 *KREDIT HOLATI*\n━━━━━━━━━━━━━━\n\n"
    for b in BANKS:
        text += f"🏛 *{b['name']}*\n  💳 Qoldiq: {fmt(b['qoldiq'])}\n  📅 Oylik: {fmt(b['oylik'])}\n  ⏳ {b['oy']} oy qoldi\n\n"
    text += "💡 *Strategiya:*\n1-bank 12 oyda tugaydi ✅\nKeyin 1 517 000 somni 2-bankka qoshing\n→ 36 orniga ~12 oyda tugaydi! 🚀"
    await update.message.reply_text(text, parse_mode="Markdown")

async def show_last(update: Update):
    _, _, _, _, txns = get_stats(update.effective_user.id)
    if not txns:
        await update.message.reply_text("📋 Hali yozuvlar yoq.")
        return
    text = "📋 *SONGI 5 TA YOZUV*\n━━━━━━━━━━━━━━\n\n"
    for t in txns:
        e = "💰" if t[0]=="kirim" else "💸"
        s = "+" if t[0]=="kirim" else "-"
        text += f"{e} {t[1]}: {s}{fmt(t[2])} ({t[3]})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
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
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
