import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8660866355:AAGEFctiiAGIgY20GGEog_DDtWA6XF4W2JA"
OWNER_ID = 7963568281

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

approved_ids: set[int] = {OWNER_ID}
approved_usernames: set[str] = set()

SOURCE = None
DEST = None
INTERVAL = 30
last_message = None
last_link = None
channel_link = None
worker_started = False
worker_running = False


def is_auth(update: Update) -> bool:
    uid = update.effective_user.id
    uname = (update.effective_user.username or "").lower().strip()
    if uid in approved_ids:
        return True
    if uname and uname in approved_usernames:
        approved_ids.add(uid)
        return True
    return False


def build_post(grp_link):
    ch = channel_link if channel_link else "NaN"
    return (
        "FRIEND CHATTING CHANNEL\n"
        f"{ch}\n"
        f"{ch}\n"
        f"{ch}\n\n"
        "JOIN GROUP\n"
        f"{grp_link}\n"
        f"{grp_link}\n"
        f"{grp_link}\n"
        f"{grp_link}\n"
        f"{grp_link}"
    )


async def worker(bot):
    global last_message, last_link, worker_running
    logger.info("Worker started")
    while worker_running:
        if SOURCE and DEST:
            try:
                if last_link:
                    try:
                        await bot.revoke_chat_invite_link(SOURCE, last_link)
                    except Exception:
                        pass
                if last_message:
                    try:
                        await bot.delete_message(DEST, last_message)
                    except Exception:
                        pass
                expire_date = datetime.now() + timedelta(seconds=INTERVAL + 60)
                invite = await bot.create_chat_invite_link(
                    SOURCE, expire_date=expire_date, creates_join_request=False
                )
                last_link = invite.invite_link
                sent = await bot.send_message(DEST, build_post(last_link))
                last_message = sent.message_id
                logger.info(f"Rotated: {last_link}")
            except Exception as e:
                logger.error(f"Worker error: {e}")
        await asyncio.sleep(INTERVAL)
    logger.info("Worker stopped")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global worker_started, worker_running
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Not authorized.")
    if worker_running:
        return await update.message.reply_text("Rotator already running. /stoprotator se band karo.")
    worker_running = True
    if not worker_started:
        asyncio.create_task(worker(context.bot))
        worker_started = True
    else:
        asyncio.create_task(worker(context.bot))
    await update.message.reply_text(
        "Bot started.\n\n"
        "/add <source_id> <dest_id> <interval>\n"
        "/channellink <link>\n"
        "/changechannellink <link>\n"
        "/stoprotator\n"
        "/approve <user_id or @username>\n"
        "/remove <user_id or @username>\n"
        "/approvedlist\n\n"
        "Kisi ke message pe reply karke /approve bhi kar sakte ho."
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SOURCE, DEST, INTERVAL
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if len(context.args) < 3:
        return await update.message.reply_text("Usage: /add <source_id> <dest_id> <interval>")
    SOURCE = int(context.args[0])
    DEST = int(context.args[1])
    INTERVAL = max(5, int(context.args[2]))
    await update.message.reply_text(f"Rotator set. Source: {SOURCE} | Dest: {DEST} | Interval: {INTERVAL}s")


async def cmd_channellink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global channel_link
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /channellink <link>")
    if channel_link:
        return await update.message.reply_text(
            f"Channel link already set: {channel_link}\n"
            "Badlne ke liye: /changechannellink <new_link>"
        )
    channel_link = context.args[0]
    await update.message.reply_text(f"Channel link set: {channel_link}")


async def cmd_changechannellink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global channel_link
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /changechannellink <new_link>")
    channel_link = context.args[0]
    await update.message.reply_text(f"Channel link updated: {channel_link}")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Only owner can approve.")
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        approved_ids.add(target.id)
        if target.username:
            approved_usernames.add(target.username.lower())
        name = f"@{target.username}" if target.username else target.full_name
        return await update.message.reply_text(f"Approved: {name} ({target.id})")
    if not context.args:
        return await update.message.reply_text("Usage: /approve <user_id or @username>")
    arg = context.args[0]
    if arg.startswith("@"):
        approved_usernames.add(arg[1:].lower())
        await update.message.reply_text(f"Approved: {arg}")
    else:
        approved_ids.add(int(arg))
        await update.message.reply_text(f"Approved: {arg}")


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Only owner can remove.")
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if target.id == OWNER_ID:
            return await update.message.reply_text("Owner ko remove nahi kar sakte.")
        approved_ids.discard(target.id)
        if target.username:
            approved_usernames.discard(target.username.lower())
        name = f"@{target.username}" if target.username else target.full_name
        return await update.message.reply_text(f"Removed: {name}")
    if not context.args:
        return await update.message.reply_text("Usage: /remove <user_id or @username>")
    arg = context.args[0]
    if arg.startswith("@"):
        approved_usernames.discard(arg[1:].lower())
        await update.message.reply_text(f"Removed: {arg}")
    else:
        uid = int(arg)
        if uid == OWNER_ID:
            return await update.message.reply_text("Owner ko remove nahi kar sakte.")
        approved_ids.discard(uid)
        await update.message.reply_text(f"Removed: {uid}")


async def cmd_approvedlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Not authorized.")
    lines = [f"{OWNER_ID} (Owner)"]
    for uid in approved_ids:
        if uid != OWNER_ID:
            lines.append(str(uid))
    for uname in approved_usernames:
        lines.append(f"@{uname}")
    await update.message.reply_text("\n".join(lines))


async def cmd_stoprotator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global worker_running
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not worker_running:
        return await update.message.reply_text("Rotator already stopped.")
    worker_running = False
    await update.message.reply_text("Rotator stopped. /start se dobara shuru karo.")


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("channellink", cmd_channellink))
    app.add_handler(CommandHandler("changechannellink", cmd_changechannellink))
    app.add_handler(CommandHandler("stoprotator", cmd_stoprotator))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("approvedlist", cmd_approvedlist))
    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
    
