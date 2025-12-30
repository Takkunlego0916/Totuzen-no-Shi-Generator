import discord
from discord import app_commands
from discord.ext import commands
from wcwidth import wcswidth


TOKEN = "MTQ1NTM1MzYyMTY0NTM2NTI4OA.G9LZKJ.T9DjUtegp8ccVQM9oDFILoV49oFTAiITzl0cyE"
GUILD_ID = None  

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def display_width(s: str) -> int:
    return max(0, wcswidth(s))


def make_totuzen_art(message: str, max_width: int = 40) -> str:
    # 改行をスペースに置換
    msg = message.replace("\n", " ")
    # 長すぎる場合は切る
    # max_width は表示上の最大文字幅
    # 切り方は簡易的に文字単位で行う
    while display_width(msg) > max_width:
        msg = msg[:-1]
    # 中央にスペースを入れて見栄えを揃える
    inner = f"　{msg}　"  # 全角スペースで囲む
    inner_width = display_width(inner)
    # 上部の「人」の数は内幅に合わせて調整
    # 最低でも 2 個は表示する
    people_count = max(2, inner_width // 1)
    top = "＿" + "人" * people_count + "＿"
    middle = f"＞{inner}＜"
    # 下部は Y^ の繰り返しで長さを合わせる
    y_repeat = max(2, (inner_width + 1) // 2)
    bottom = "￣" + "Y^" * y_repeat + "￣"
    # コードブロックで返すと崩れにくい
    return "```\n" + top + "\n" + middle + "\n" + bottom + "\n```"

# スラッシュコマンド登録
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    # サーバー限定で登録する場合は guild を指定
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("Commands synced to guild:", GUILD_ID)
    else:
        await bot.tree.sync()
        print("Global commands synced")

@bot.tree.command(name="totuzen", description="突然のアスキーアートでメッセージを表示します")
@app_commands.describe(message="表示するメッセージ（改行はスペースに変換されます）")
async def totuzen(interaction: discord.Interaction, message: str):
    # 簡易サニタイズ（メンション無効化）
    safe = message.replace("@", "@\u200b")
    art = make_totuzen_art(safe, max_width=40)
    await interaction.response.send_message(art)

if __name__ == "__main__":
    bot.run(TOKEN)
