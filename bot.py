import os
import sqlite3
from datetime import date

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TOKEN = os.environ.get("BOT_TOKEN", "8951038010:AAEsjwPLQ-NJGwydrjwZGf0GSiDq88kVwrY")

BANKS = [
    {"name": "1-Bank", "qoldiq": 18_200_000, "oylik": 1_517_000, "oy": 12},
    {"name": "2-Bank", "qoldiq": 21_700_000, "oylik": 603_000, "oy": 36},
]
KREDIT_TOLOV = 3_920_000
MENU, KIRIM_SUMMA, KIRIM_IZOH, XARAJAT_CAT, XARAJAT_SUMMA, XARAJAT_IZOH = range(6)
CATS = ["Oziq-ovqat","Transport","Kommunal","Kiyim","Sogliq","Talim","Kongilochar","Kredit tolovi","Boshqa"]

DB = "/tmp/h.db"

def init_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, uid INTEGER, tp TEXT, cat TEXT, amt REAL, note TEXT, dt TEXT)")
    c.commit(); c.close()

def add_t(uid, tp, cat, amt, note=""):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO t (uid,tp,cat,amt,note,dt) VALUES (?,?,?,?,?,?)", (uid,tp,cat,amt,note,date.today().isoformat()))
    c.commit(); c.close()

def stats(uid):
    c = sqlite3.connect(DB)
    oy = date.today().replace(day=1).isoformat()
    ak = c.execute("SELECT COALESCE(SUM(amt),0) FROM t WHERE uid=? AND tp='k'", (uid,)).fetchone()[0]
    ax = c.execute("SELECT COALESCE(SUM(amt),0) FROM t WHERE uid=? AND tp='x'", (uid,)).fetchone()[0]
    ok = c.execute("SELECT COALESCE(SUM(amt),0) FROM t WHERE uid=? AND tp='k' AND dt>=?", (uid,oy)).fetchone()[0]
    ox = c.execute("SELECT COALESCE(SUM(amt),0) FROM t WHERE uid=? AND tp='x' AND dt>=?", (uid,oy)).fetchone()[0]
    last = c.execute("SELECT tp,cat,amt,dt FROM t WHERE uid=? ORDER BY id DESC LIMIT 5", (uid,)).fetchall()
    c.close()
    return ak, ax, ok, ox, last

def f(n): return f"{int(n):,} som".replace(",", " ")

def kb():
    return ReplyKeyboardMarkup([
        ["💰 Kirim", "💸 Xarajat"],
        ["📊 Hisobot", "🏦 Kreditlar"],
        ["📋 Oxirgi 5 ta"],
    ], resize_keyboard=True)

async def start(u: Update, _):
    await u.message.reply_text("👋 Salom! Moliyaviy Hisobchingizman!\n\nTugmalardan foydalaning 👇", reply_markup=kb())
    return MENU

async def menu(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = u.message.text
    uid = u.effective_user.id
    if t == "💰 Kirim":
        await u.message.reply_text("Qancha kirim? (Masalan: 500000)")
        return KIRIM_SUMMA
    elif t == "💸 Xarajat":
        rows = [CATS[i:i+2] for i in range(0,len(CATS),2)] + [["Orqaga"]]
        await u.message.reply_text("Kategoriya:", reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True))
        return XARAJAT_CAT
    elif t == "📊 Hisobot":
        ak,ax,ok,ox,_ = stats(uid)
        ob = ok - ox - KREDIT_TOLOV
        await u.message.reply_text(
            f"📊 HISOBOT\n\n📅 Bu oy:\n  Kirim: +{f(ok)}\n  Xarajat: -{f(ox)}\n  Kredit: -{f(KREDIT_TOLOV)}\n  {'✅' if ob>=0 else '❌'} Sof: {'+' if ob>=0 else ''}{f(ob)}\n\n📦 Jami:\n  Kirim: +{f(ak)}\n  Xarajat: -{f(ax)}\n  Balans: {f(ak-ax)}")
    elif t == "🏦 Kreditlar":
        msg = "🏦 KREDITLAR\n\n"
        for b in BANKS:
            msg += f"{b['name']}: {f(b['qoldiq'])} | Oylik: {f(b['oylik'])} | {b['oy']} oy\n\n"
        msg += "💡 1-bank 12 oyda tugaydi. Keyin bo'shagan pulni 2-bankka qo'shing → 12 oyda tugaydi!"
        await u.message.reply_text(msg)
    elif t == "📋 Oxirgi 5 ta":
        _,_,_,_,txns = stats(uid)
        if not txns:
            await u.message.reply_text("Yozuvlar yo'q.")
        else:
            msg = "📋 OXIRGI 5 TA:\n\n"
            for tx in txns:
                s = "+" if tx[0]=="k" else "-"
                msg += f"{tx[1]}: {s}{f(tx[2])} ({tx[3]})\n"
            await u.message.reply_text(msg)
    return MENU

async def kirim_s(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["ka"] = float(u.message.text.replace(" ",""))
        await u.message.reply_text("Izoh yoki /skip:")
        return KIRIM_IZOH
    except:
        await u.message.reply_text("Faqat raqam! Masalan: 500000")
        return KIRIM_SUMMA

async def kirim_i(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = "" if u.message.text=="/skip" else u.message.text
    add_t(u.effective_user.id, "k", "Kirim", ctx.user_data["ka"], note)
    await u.message.reply_text(f"✅ +{f(ctx.user_data['ka'])} saqlandi!", reply_markup=kb())
    return MENU

async def xarajat_c(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.message.text == "Orqaga":
        await u.message.reply_text("Bosh menyu:", reply_markup=kb())
        return MENU
    ctx.user_data["xc"] = u.message.text
    await u.message.reply_text(f"{u.message.text} uchun summa?")
    return XARAJAT_SUMMA

async def xarajat_s(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["xa"] = float(u.message.text.replace(" ",""))
        await u.message.reply_text("Izoh yoki /skip:")
        return XARAJAT_IZOH
    except:
        await u.message.reply_text("Faqat raqam!")
        return XARAJAT_SUMMA

async def xarajat_i(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = "" if u.message.text=="/skip" else u.message.text
    add_t(u.effective_user.id, "x", ctx.user_data["xc"], ctx.user_data["xa"], note)
    await u.message.reply_text(f"✅ -{f(ctx.user_data['xa'])} saqlandi!", reply_markup=kb())
    return MENU

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu)],
            KIRIM_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, kirim_s)],
            KIRIM_IZOH: [MessageHandler(filters.TEXT, kirim_i), CommandHandler("skip", kirim_i)],
            XARAJAT_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, xarajat_c)],
            XARAJAT_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, xarajat_s)],
            XARAJAT_IZOH: [MessageHandler(filters.TEXT, xarajat_i), CommandHandler("skip", xarajat_i)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    print("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
