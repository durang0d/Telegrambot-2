from quart import Quart, request
import os
import asyncio
import datetime
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import hypercorn.asyncio
from hypercorn.config import Config

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CANAL_ID = -1002817510483
GRUPO_ID = -1002646779589
USER_ADMIN_ID = 1994617924
PALABRAS_CLAVE = ["redes", "contenido"]

mensajes_temporales = {}
botones_temporales = {}
scheduler = AsyncIOScheduler()

# Configuración de Quart
app = Quart(__name__)
app.config.from_mapping({
    'PROVIDE_AUTOMATIC_OPTIONS': False  # Agregar esta configuración
})

@app.route("/")
def index():
    return "Bot activo."

@app.route("/webhook", methods=["POST"])
async def webhook():
    json_str = await request.get_data()
    data = json.loads(json_str.decode("UTF-8"))
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "OK"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID:
        return
    await update.message.reply_text("👋 Enviame el contenido que querés publicar (texto o imagen).")

async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID:
        return
    mensajes_temporales[USER_ADMIN_ID] = update.message
    await update.message.reply_text(
        "¿Querés agregar botones con links? Mandalos en formato:\n\n"
        "`Texto del botón - https://tulink.com`\n"
        "(Mandá uno por línea, o escribí `no` para omitir)",
        parse_mode="Markdown"
    )

async def recibir_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID or USER_ADMIN_ID not in mensajes_temporales:
        return
    texto = update.message.text.strip().lower()
    if texto != "no":
        botones = []
        for linea in update.message.text.strip().split("\n"):
            if "-" in linea:
                label, url = linea.split("-", 1)
                botones.append([InlineKeyboardButton(label.strip(), url=url.strip())])
        botones_temporales[USER_ADMIN_ID] = InlineKeyboardMarkup(botones)
    else:
        botones_temporales[USER_ADMIN_ID] = None
    keyboard = [
        [InlineKeyboardButton("📅 Programar", callback_data="programar"),
         InlineKeyboardButton("✅ Publicar ahora", callback_data="publicar_ahora")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("¿Querés publicarlo ahora o programarlo?", reply_markup=markup)

async def manejar_boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != USER_ADMIN_ID:
        return
    if query.data == "cancelar":
        await query.edit_message_text("❌ Publicación cancelada.")
        mensajes_temporales.pop(USER_ADMIN_ID, None)
        botones_temporales.pop(USER_ADMIN_ID, None)
        return
    if query.data == "publicar_ahora":
        await publicar_contenido(context)
        await query.edit_message_text("✅ Publicación enviada.")
    elif query.data == "programar":
        await query.edit_message_text(
            "⏰ Escribí la fecha y hora en formato `YYYY-MM-DD HH:MM`",
            parse_mode="Markdown"
        )

async def recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID:
        return
    try:
        fecha = datetime.datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
        scheduler.add_job(publicar_contenido, 'date', run_date=fecha, args=[context])
        await update.message.reply_text(f"🗓️ Publicación programada para {fecha.strftime('%Y-%m-%d %H:%M')}")
    except ValueError:
        await update.message.reply_text("⚠️ Formato inválido. Usá `YYYY-MM-DD HH:MM`.")

async def publicar_contenido(context: ContextTypes.DEFAULT_TYPE):
    msg = mensajes_temporales.get(USER_ADMIN_ID)
    markup = botones_temporales.get(USER_ADMIN_ID)
    if msg is None:
        return
    if msg.text:
        await context.bot.send_message(chat_id=CANAL_ID, text=msg.text, reply_markup=markup)
        if any(p in msg.text.lower() for p in PALABRAS_CLAVE):
            await context.bot.send_message(chat_id=GRUPO_ID, text=msg.text, reply_markup=markup)
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        await context.bot.send_photo(chat_id=CANAL_ID, photo=file_id, caption=msg.caption, reply_markup=markup)
        if any(p in (msg.caption or "").lower() for p in PALABRAS_CLAVE):
            await context.bot.send_photo(chat_id=GRUPO_ID, photo=file_id, caption=msg.caption, reply_markup=markup)
    mensajes_temporales.pop(USER_ADMIN_ID, None)
    botones_temporales.pop(USER_ADMIN_ID, None)

async def start_webhook():
    global application
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(manejar_boton))
    application.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=USER_ADMIN_ID) & filters.Regex(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"), recibir_fecha))
    application.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=USER_ADMIN_ID) & ~filters.COMMAND, recibir_botones))
    application.add_handler(MessageHandler(filters.PHOTO & filters.User(user_id=USER_ADMIN_ID), recibir_mensaje))

    await application.initialize()
    await application.bot.set_webhook(url="https://telegrambot-2-fail.onrender.com/webhook")

    config = Config()
    config.bind = ["0.0.0.0:10000"]
    await hypercorn.asyncio.serve(app, config)

async def main():
    webhook_task = asyncio.create_task(start_webhook())
    await webhook_task

if __name__ == "__main__":
    asyncio.run(main())
