import os
import json
import logging
from typing import Dict, Optional

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "data.json"

# Cargar variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID")  # el chat id del grupo donde se publicará el reporte final

if not TELEGRAM_TOKEN:
    logger.error("Falta la variable de entorno TELEGRAM_TOKEN. Abortando.")
    raise SystemExit("TELEGRAM_TOKEN missing")

if not REPORT_CHAT_ID:
    logger.warning("REPORT_CHAT_ID no está definido. El bot seguirá funcionando pero no publicará en el grupo final.")

# Grupos 1..6
GROUPS = [str(i) for i in range(1, 7)]


def load_state() -> Dict[str, Optional[int]]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {g: (data.get(g) if data.get(g) is not None else None) for g in GROUPS}
        except Exception:
            logger.exception("No pude leer data.json, inicializando estado limpio.")
    return {g: None for g in GROUPS}


def save_state(state: Dict[str, Optional[int]]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


state = load_state()


# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot de asistencia listo.\n"
        "Comandos:\n"
        "/asistencia <grupo> <número>  — reportar asistentes por Zoom (grupos 1-6)\n"
        "/estado  — ver quién ya reportó\n"
        "/help — muestra esto\n\n"
        "Ejemplo: /asistencia 3 12"
    )


async def asistencia_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Formato: /asistencia <grupo> <número>  (ej: /asistencia 2 15)")
        return

    grupo, numero_raw = context.args
    if grupo not in GROUPS:
        await update.message.reply_text("Grupo inválido. Usa un número entre 1 y 6.")
        return

    try:
        numero = int(numero_raw)
        if numero < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("El número debe ser un entero >= 0.")
        return

    state[grupo] = numero
    save_state(state)

    await update.message.reply_text(f"✅ Grupo {grupo} reportó {numero} asistentes por Zoom.")

    # Si todos reportaron: enviar resumen al chat donde se llamó y al REPORT_CHAT_ID
    if all(v is not None for v in state.values()):
        total = sum(state.values())
        mensaje = "📊 *Resumen de asistencia por Zoom*\n\n"
        for g in GROUPS:
            mensaje += f"Grupo {g}: {state[g]}\n"
        mensaje += f"\n-------------------\n✅ *Total:* {total}"

        # Enviar al chat que hizo la petición
        await update.message.reply_text(mensaje, parse_mode="Markdown")

        # Enviar al grupo de reportes si está configurado
        if REPORT_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=int(REPORT_CHAT_ID), text=mensaje, parse_mode="Markdown")
            except Exception as e:
                logger.exception("No pude enviar el mensaje al REPORT_CHAT_ID: %s", e)
                await update.message.reply_text("⚠️ Falló el envío del reporte al chat final (ver logs).")

        # Reiniciar estado para la próxima reunión
        for g in GROUPS:
            state[g] = None
        save_state(state)


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = "📌 Estado actual de reportes:\n"
    for g in GROUPS:
        if state[g] is None:
            mensaje += f"Grupo {g}: ❌ pendiente\n"
        else:
            mensaje += f"Grupo {g}: ✅ {state[g]} asistentes\n"
    await update.message.reply_text(mensaje)


# opcional: obtener chat id (usar para obtener REPORT_CHAT_ID)
async def getchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"Este chat tiene id: {chat.id}")


# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("asistencia", asistencia_cmd))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("getchatid", getchat))  # borra/usa sólo para obtener id del grupo

    logger.info("Bot iniciado. Haciendo polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
