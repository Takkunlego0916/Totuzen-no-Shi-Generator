import asyncio
import signal
import logging
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands
from wcwidth import wcswidth
import os
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    port = int(os.environ.get("PORT", 10000))  # Renderが自動割り当て
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

# --- 環境変数読み込み ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # テスト用ギルドID。未設定ならグローバル登録
MAX_WIDTH = int(os.getenv("TOTUZEN_MAX_WIDTH", "40"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- ログ設定 ---
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger("totuzen-bot")

# --- Bot 初期化 ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- ユーティリティ関数 ---
def display_width(s: str) -> int:
    return max(0, wcswidth(s))

def truncate_with_ellipsis(s: str, max_w: int) -> str:
    if display_width(s) <= max_w:
        return s
    out = ""
    for ch in s:
        if display_width(out + ch + "…") > max_w:
            break
        out += ch
    return out + "…"

def sanitize_message(s: str) -> str:
    # 改行をスペースに、メンションを無効化
    s = s.replace("\n", " ")
    s = s.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
    s = s.replace("@", "@\u200b")
    return s

def make_totuzen_art(message: str, max_width: int = 40) -> str:
    msg = sanitize_message(message)
    # 両端の全角スペース分を差し引いて切る
    msg = truncate_with_ellipsis(msg, max_width - 4)
    inner = f"　{msg}　"  # 全角スペースで囲む
    inner_width = display_width(inner)
    people_count = max(2, inner_width)
    top = "＿" + "人" * people_count + "＿"
    middle = f"＞{inner}＜"
    y_repeat = max(2, (inner_width + 1) // 2)
    bottom = "￣" + "Y^" * y_repeat + "￣"
    return "```\n" + top + "\n" + middle + "\n" + bottom + "\n```"

# --- スラッシュコマンドの定義を分離して管理する場合は Cog にすることも可能 ---
@bot.tree.command(name="totuzen", description="突然のアスキーアートでメッセージを表示します")
@app_commands.describe(message="表示するメッセージ（改行はスペースに変換されます）")
async def totuzen(interaction: discord.Interaction, message: str):
    art = make_totuzen_art(message, max_width=MAX_WIDTH)
    try:
        await interaction.response.send_message(art)
    except Exception:
        logger.exception("Failed to send totuzen response")
        try:
            if interaction.response.is_done():
                await interaction.followup.send("送信に失敗しました。", ephemeral=True)
            else:
                await interaction.response.send_message("送信に失敗しました。", ephemeral=True)
        except Exception:
            pass

# --- エラーハンドリング ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.exception("App command error")
    try:
        await interaction.response.send_message("コマンド実行中にエラーが発生しました。", ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send("コマンド実行中にエラーが発生しました。", ephemeral=True)
        except Exception:
            pass

# --- 起動時処理とコマンド同期 ---
async def sync_commands():
    guild_id = int(GUILD_ID) if GUILD_ID else None
    try:
        if guild_id:
            # ギルドに参加しているか確認してから同期
            guild = bot.get_guild(guild_id)
            if guild is None:
                logger.error("Bot is not a member of guild %s. Skipping guild sync.", guild_id)
            else:
                bot.tree.copy_global_to(guild=discord.Object(id=guild_id))
                await bot.tree.sync(guild=discord.Object(id=guild_id))
                logger.info("Commands synced to guild %s", guild_id)
        else:
            await bot.tree.sync()
            logger.info("Global commands synced")
    except discord.errors.Forbidden:
        logger.exception("Failed to sync commands due to missing access")
    except Exception:
        logger.exception("Failed to sync commands")

@bot.event
async def on_ready():
    logger.info("Logged in as %s (id: %s)", bot.user, bot.user.id)
    try:
        await bot.change_presence(activity=discord.Game(name="/totuzen"))
    except Exception:
        logger.warning("Failed to set presence")
    # 同期は別タスクで行うと起動がブロックされにくい
    asyncio.create_task(sync_commands())

# --- Graceful shutdown for Render ---
async def shutdown():
    logger.info("Shutting down bot...")
    await bot.close()

def _setup_signal_handlers(loop):
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass

# --- エントリポイント ---
if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN is not set. Exiting.")
        raise SystemExit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _setup_signal_handlers(loop)
    try:
        loop.run_until_complete(bot.start(TOKEN))
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down")
        loop.run_until_complete(shutdown())
    except Exception:
        logger.exception("Unexpected exception in bot")
    finally:
        loop.close()
        logger.info("Bot stopped")
