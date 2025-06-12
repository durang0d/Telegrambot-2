from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import datetime

TOKEN = '8169029291:AAGO1a7CkYx0xnDGML_vq7Ug--mDdvMuSNc'
CANAL_ID = -1002817510483
GRUPO_ID = -1002646779589
USER_ADMIN_ID = 1994617924  # Reemplazar con tu ID real
PALABRAS_CLAVE = ["redes", "contenido"]

mensajes_temporales = {}
botones_temporales = {}
scheduler = BackgroundScheduler()
scheduler.start()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID:
        return
    await update.message.reply_text("👋 Enviame el contenido que querés publicar (texto o imagen).")

# Recibe mensaje
async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID:
        return

    mensajes_temporales[USER_ADMIN_ID] = update.message
    await update.message.reply_text("¿Querés agregar botones con links? Mandalos en formato:\n\n`Texto del botón - https://tulink.com`\n(Mandá uno por línea, o escribí `no` para omitir)", parse_mode="Markdown")

# Recibe botones
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

# Botones de opción final
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
        await query.edit_message_text("⏰ Escribí la fecha y hora en formato `YYYY-MM-DD HH:MM` (ej: 2025-06-11 14:30)", parse_mode="Markdown")

# Recibe fecha y hora
async def recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ADMIN_ID:
        return

    try:
        fecha = datetime.datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
        scheduler.add_job(publicar_contenido, 'date', run_date=fecha, args=[context])
        await update.message.reply_text(f"🗓️ Publicación programada para {fecha.strftime('%Y-%m-%d %H:%M')}")
    except ValueError:
        await update.message.reply_text("⚠️ Formato inválido. Usá `YYYY-MM-DD HH:MM`.")

# Función para publicar
async def publicar_contenido(context: ContextTypes.DEFAULT_TYPE):
    msg = mensajes_temporales.get(USER_ADMIN_ID)
    markup = botones_temporales.get(USER_ADMIN_ID)

    if msg.text:
        await context.bot.send_message(chat_id=CANAL_ID, text=msg.text, reply_markup=markup)
        if any(p in msg.text.lower() for p in PALABRAS_CLAVE):
            await context.bot.send_message(chat_id=GRUPO_ID, text=msg.text, reply_markup=markup)
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        await context.bot.send_photo(chat_id=CANAL_ID, photo=file_id, caption=msg.caption, reply_markup=markup)
        if any(p in (msg.caption or "").lower() for p in PALABRAS_CLAVE):
            await context.bot.send_photo(chat_id=GRUPO_ID, photo=file_id, caption=msg.caption, reply_markup=markup)

    # Limpia la memoria
    mensajes_temporales.pop(USER_ADMIN_ID, None)
    botones_temporales.pop(USER_ADMIN_ID, None)

# Configuración de handlers
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(manejar_boton))
app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=USER_ADMIN_ID) & ~filters.COMMAND, recibir_botones))
app.add_handler(MessageHandler(filters.PHOTO & filters.User(user_id=USER_ADMIN_ID), recibir_mensaje))
app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=USER_ADMIN_ID) & filters.Regex(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"), recibir_fecha))

app.run_polling()
