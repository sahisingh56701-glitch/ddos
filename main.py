import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8677797398:AAGA0Qiw2HlSnvc2twdJGiB6174eEYNchqg"
OWNER_ID = 8413208942

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

approved_ids: set[int] = {OWNER_ID}
approved_usernames: set[str] = set()

SOURCE = None
channel_link = None

# dests = { dest_id: { interval, last_link, last_message, task } }
dests: dict[int, dict] = {}


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
        f"{ch}\n{ch}\n{ch}\n\n"
        "JOIN GROUP\n"
        f"{grp_link}\n{grp_link}\n{grp_link}\n{grp_link}\n{grp_link}"
    )


async def dest_worker(dest_id: int, bot):
    state = dests[dest_id]
    logger.info(f"Worker started for dest={dest_id} interval={state['interval']}s")
    while state.get("running") and SOURCE:
        try:
            if state["last_link"]:
                try:
                    await bot.revoke_chat_invite_link(SOURCE, state["last_link"])
                except Exception:
                    pass
            if state["last_message"]:
                try:
                    await bot.delete_message(dest_id, state["last_message"])
                except Exception:
                    pass
            expire_date = datetime.now() + timedelta(seconds=state["interval"] + 60)
            invite = await bot.create_chat_invite_link(SOURCE, expire_date=expire_date, creates_join_request=False)
            state["last_link"] = invite.invite_link
            sent = await bot.send_message(dest_id, build_post(state["last_link"]), disable_web_page_preview=True)
            state["last_message"] = sent.message_id
            logger.info(f"Rotated dest={dest_id} link={state['last_link']}")
        except Exception as e:
            logger.error(f"Error dest={dest_id}: {e}")
        await asyncio.sleep(state["interval"])
    logger.info(f"Worker stopped for dest={dest_id}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Not authorized.")
    await update.message.reply_text(
        "Bot ready.\n\n"
        "/setsource <source_id>\n"
        "/adddest <dest_id> <interval>\n"
        "/removedest <dest_id>\n"
        "/listdest\n"
        "/stopdest <dest_id>\n"
        "/startdest <dest_id>\n"
        "/channellink <link>\n"
        "/changechannellink <link>\n"
        "/approve <id or @username>\n"
        "/remove <id or @username>\n"
        "/approvedlist"
    )


async def cmd_setsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SOURCE
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /setsource <source_id>")
    SOURCE = int(context.args[0])
    await update.message.reply_text(f"Source set: {SOURCE}")


async def cmd_adddest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /adddest <dest_id> <interval>")
    dest_id = int(context.args[0])
    interval = max(5, int(context.args[1]))
    if dest_id in dests:
        dests[dest_id]["running"] = False
        await asyncio.sleep(1)
    dests[dest_id] = {"interval": interval, "last_link": None, "last_message": None, "running": True}
    task = asyncio.create_task(dest_worker(dest_id, context.bot))
    dests[dest_id]["task"] = task
    await update.message.reply_text(f"Dest {dest_id} added with interval {interval}s")


async def cmd_removedest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /removedest <dest_id>")
    dest_id = int(context.args[0])
    if dest_id in dests:
        dests[dest_id]["running"] = False
        dests.pop(dest_id)
    await update.message.reply_text(f"Dest {dest_id} removed.")


async def cmd_stopdest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /stopdest <dest_id>")
    dest_id = int(context.args[0])
    if dest_id not in dests:
        return await update.message.reply_text("Dest not found.")
    dests[dest_id]["running"] = False
    await update.message.reply_text(f"Dest {dest_id} stopped.")


async def cmd_startdest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /startdest <dest_id>")
    dest_id = int(context.args[0])
    if dest_id not in dests:
        return await update.message.reply_text("Dest not found. /adddest se pehle add karo.")
    dests[dest_id]["running"] = True
    asyncio.create_task(dest_worker(dest_id, context.bot))
    await update.message.reply_text(f"Dest {dest_id} started.")


async def cmd_listdest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not dests:
        return await update.message.reply_text("Koi dest nahi hai.")
    lines = [f"Source: {SOURCE}\n"]
    for did, s in dests.items():
        status = "running" if s.get("running") else "stopped"
        lines.append(f"{did} | {s['interval']}s | {status}")
    await update.message.reply_text("\n".join(lines))


async def cmd_channellink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global channel_link
    if not is_auth(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /channellink <link>")
    if channel_link:
        return await update.message.reply_text(f"Already set: {channel_link}\nBadlne ke liye: /changechannellink <link>")
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


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("setsource", cmd_setsource))
    app.add_handler(CommandHandler("adddest", cmd_adddest))
    app.add_handler(CommandHandler("removedest", cmd_removedest))
    app.add_handler(CommandHandler("stopdest", cmd_stopdest))
    app.add_handler(CommandHandler("startdest", cmd_startdest))
    app.add_handler(CommandHandler("listdest", cmd_listdest))
    app.add_handler(CommandHandler("channellink", cmd_channellink))
    app.add_handler(CommandHandler("changechannellink", cmd_changechannellink))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("approvedlist", cmd_approvedlist))
    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
    
