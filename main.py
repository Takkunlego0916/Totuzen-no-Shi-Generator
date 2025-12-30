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
load_dotenv()  # .env がある場合に読み込む
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # テスト用にサーバー限定登録するなら入れる（省略可）
MAX_WIDTH = int(os.getenv("TOTUZEN_MAX_WIDTH", "40"))

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("totuzen-bot")

# --- Bot 初期化 ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- ユーティリティ関数 ---
def display_width(s: str) -> int:
    return max(0, wcswidth(s))

def truncate_with_ellipsis(s: str, max_w: int) -> str:
    # 表示幅で切って末尾に…を付ける（必要なら）
    if display_width(s) <= max_w:
        return s
    # 末尾に '…' を残すために1幅分を確保
    out = ""
    for ch in s:
        if display_width(out + ch + "…") > max_w:
            break
        out += ch
    return out + "…"

def make_totuzen_art(message: str, max_width: int = 40) -> str:
    msg = message.replace("\n", " ")
    # メンション系を無効化
    msg = msg.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
    msg = msg.replace("@", "@\u200b")
    # 切り詰め
    msg = truncate_with_ellipsis(msg, max_width - 4)  # 両端の全角スペース分を差し引く
    inner = f"　{msg}　"  # 全角スペースで囲む
    inner_width = display_width(inner)
    people_count = max(2, inner_width)
    top = "＿" + "人" * people_count + "＿"
    middle = f"＞{inner}＜"
    y_repeat = max(2, (inner_width + 1) // 2)
    bottom = "￣" + "Y^" * y_repeat + "￣"
    return "```\n" + top + "\n" + middle + "\n" + bottom + "\n```"

# --- スラッシュコマンド ---
@bot.tree.command(name="totuzen", description="突然のアスキーアートでメッセージを表示します")
@app_commands.describe(message="表示するメッセージ（改行はスペースに変換されます）")
async def totuzen(interaction: discord.Interaction, message: str):
    safe = message  # make_totuzen_art 内でサニタイズ済み
    art = make_totuzen_art(safe, max_width=MAX_WIDTH)
    try:
        await interaction.response.send_message(art)
    except Exception as e:
        logger.exception("Failed to send totuzen response")
        # 既に応答済みかどうかで処理を分ける
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
    # ユーザー向けメッセージ（詳細はログに）
    try:
        await interaction.response.send_message("コマンド実行中にエラーが発生しました。", ephemeral=True)
    except Exception:
        # 既に応答済みの場合
        try:
            await interaction.followup.send("コマンド実行中にエラーが発生しました。", ephemeral=True)
        except Exception:
            pass

# --- 起動時処理 ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (id: {bot.user.id})")
    # ステータス設定（任意）
    try:
        await bot.change_presence(activity=discord.Game(name="/totuzen"))
    except Exception:
        logger.warning("Failed to set presence")
    # コマンド同期
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info("Commands synced to guild: %s", GUILD_ID)
        else:
            await bot.tree.sync()
            logger.info("Global commands synced")
    except Exception:
        logger.exception("Failed to sync commands")

# --- Graceful shutdown for Render ---
async def shutdown():
    logger.info("Shutting down bot...")
    await bot.close()

def _setup_signal_handlers(loop):
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown()))
        except NotImplementedError:
            # Windows 等で未サポートの場合は無視
            pass

# --- エントリポイント ---
if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN が設定されていません。環境変数を確認してください。")
        raise SystemExit(1)

    loop = asyncio.get_event_loop()
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
