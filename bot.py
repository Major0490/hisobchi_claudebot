import os
import sqlite3
from datetime import date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TOKEN = os.environ.get("BOT_TOKEN", "8951038010:AAEsjwPLQ-NJGwydrjwZGf0GSiDq88kVwrY")

BANKS = [
    {"name": "1-Bank", "qoldiq": 18_200_000, "oylik": 1_517_000, "oy": 12},
    {"name": "2-Bank", "qoldiq": 21_700_000, "oylik": 603_000, "oy": 36},
]
KREDIT_TOLOV = 3_920_000

MENU, KIRIM_SUMMA, KIRIM_IZOH, XARAJAT_CAT, XARAJAT_SUMMA, XARAJAT_IZOH = range(6)

XARAJAT_KATEGORIYALAR = [
    "Oziq-ovqat", "Transport", "Kommunal",
    "Kiyim", "Sogliq", "Talim",
    "Kongilochar", "Kredit tolovi", "Boshqa"
]

def init_db():
    conn = sqlite3.connect("/tmp/hisobchi.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, type TEXT, category TEXT,
        amount REAL, note TEXT, date TEXT)""")
    conn.commit()
    conn.close()

def add_txn(user_id, type_, category, amount, note=""):
    conn = sqlite3.connect("/tmp/hisobchi.db")
    conn.execute("INSERT INTO transactions (user_id,type,category,amount,note,date) VALUES (?,?,?,?,?,?)",
        (user_id, type_, category, amount, note, date.today().isoformat()))
    conn.commit()
    conn.close()

def get_stats(user_id):
    conn = sqlite3.connect("/tmp/hisobchi.db")
    oy = date.today().replace(day=1).isoformat()
    ak = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND type='kirim'", (user_id,)).fetchone()[0]
    ax = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND type='xarajat'", (user_id,)).fetchone()[0]
    ok = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND type='kirim' AND date>=?", (user_id,oy)).fetchone()[0]
    ox = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND type='xarajat' AND date>=?", (user_id,oy)).fetchone()[0]
    last = conn.execute("SELECT type,category,amount,date FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()
    conn.close()
    return ak, ax, ok, ox, last

def fmt(n):
    return f"{int(n):,} som".replace(",", " ")

def main_kb():
    return ReplyKeyboardMarkup([
        ["💰 Kirim qoshish", "💸 Xarajat qoshish"],
        ["📊 Hisobot", "🏦 Kreditlar"],
        ["📋 Songi 5 ta"],
    ], resize_keyboard=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men sizning Moliyaviy Hisobchingizman!\n\nQuyidagi tugmalardan foydalaning 👇",
        reply_markup=main_kb())
    return MENU

async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if t == "💰 Kirim qoshish":
        await update.message.reply_text("💰 Qancha kirim boldi? (Masalan: 500000)")
        return KIRIM_SUMMA
    elif t == "💸 Xarajat qoshish":
        kb = [XARAJAT_KATEGORIYALAR[i:i+2] for i in range(0,len(XARAJAT_KATEGORIYALAR),2)]
        kb.append(["Orqaga"])
        await update.message.reply_text("Kategoriyani tanlang:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return XARAJAT_CAT
    elif t == "📊 Hisobot":
        uid = update.effective_user.id
        ak,ax,ok,ox,_ = get_stats(uid)
        ob = ok - ox - KREDIT_TOLOV
        msg = (f"📊 MOLIYAVIY HISOBOT\n\n"
               f"📅 Bu oy:\n"
               f"  Kirim: +{fmt(ok)}\n"
               f"  Xarajat: -{fmt(ox)}\n"
               f"  Kredit: -{fmt(KREDIT_TOLOV)}\n"
               f"  {'✅' if ob>=0 else '❌'} Sof: {'+' if ob>=0 else ''}{fmt(ob)}\n\n"
               f"📦 Jami:\n"
               f"  Kirim: +{fmt(ak)}\n"
               f"  Xarajat: -{fmt(ax)}\n"
               f"  Balans: {fmt(ak-ax)}")
        await update.message.reply_text(msg)
    elif t == "🏦 Kreditlar":
        msg = "🏦 KREDIT HOLATI\n\n"
        for b in BANKS:
            msg += f"{b['name']}:\n  Qoldiq: {fmt(b['qoldiq'])}\n  Oylik: {fmt(b['oylik'])}\n  {b['oy']} oy qoldi\n\n"
        msg += "💡 Strategiya:\n1-bank 12 oyda tugaydi\nKeyin 1 517 000 somni 2-bankka qoshing\n→ 36 orniga ~12 oyda tugaydi!"
        await update.message.reply_text(msg)
    elif t == "📋 Songi 5 ta":
        _,_,_,_,txns = get_stats(update.effective_user.id)
        if not txns:
            await update.message.reply_text("Hali yozuvlar yoq.")
        else:
            msg = "📋 SONGI 5 TA:\n\n"
            for tx in txns:
                s = "+" if tx[0]=="kirim" else "-"
                msg += f"{tx[1]}: {s}{fmt(tx[2])} ({tx[3]})\n"
            await update.message.reply_text(msg)
    return MENU

async def kirim_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["ka"] = float(update.message.text.replace(" ",""))
        await update.message.reply_text("Izoh yozing yoki /skip:")
        return KIRIM_IZOH
    except:
        await update.message.reply_text("Faqat raqam! Masalan: 500000")
        return KIRIM_SUMMA

async def kirim_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = "" if update.message.text=="/skip" else update.message.text
    add_txn(update.effective_user.id, "kirim", "Kirim", ctx.user_data["ka"], note)
    await update.message.reply_text(f"✅ +{fmt(ctx.user_data['ka'])} saqlandi!", reply_markup=main_kb())
    return MENU

async def xarajat_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Orqaga":
        await update.message.reply_text("Bosh menyu:", reply_markup=main_kb())
        return MENU
    ctx.user_data["xc"] = update.message.text
    await update.message.reply_text(f"{update.message.text} uchun summa?")
    return XARAJAT_SUMMA

async def xarajat_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["xa"] = float(update.message.text.replace(" ",""))
        await update.message.reply_text("Izoh yozing yoki /skip:")
        return XARAJAT_IZOH
    except:
        await update.message.reply_text("Faqat raqam!")
        return XARAJAT_SUMMA

async def xarajat_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = "" if update.message.text=="/skip" else update.message.text
    add_txn(update.effective_user.id, "xarajat", ctx.user_data["xc"], ctx.user_data["xa"], note)
    await update.message.reply_text(f"✅ -{fmt(ctx.user_data['xa'])} saqlandi!", reply_markup=main_kb())
    return MENU

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu)],
            KIRIM_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, kirim_summa)],
            KIRIM_IZOH: [MessageHandler(filters.TEXT, kirim_izoh), CommandHandler("skip", kirim_izoh)],
            XARAJAT_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, xarajat_cat)],
            XARAJAT_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, xarajat_summa)],
            XARAJAT_IZOH: [MessageHandler(filters.TEXT, xarajat_izoh), CommandHandler("skip", xarajat_izoh)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    print("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
