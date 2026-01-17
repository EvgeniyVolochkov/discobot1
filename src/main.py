import discord
from discord.ext import commands
import json
import asyncio
from datetime import datetime
# Flask сервер для обработки HTTP запросов
from flask import Flask
from threading import Thread

# Импортируем модули
from database import init_db, cleanup_expired_transfers
from balance import setup_balance_commands
from fractions import setup_fraction_commands
from admin import setup_admin_commands
# from payment import setup_payment_commands

# Загрузка конфигурации
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

TOKEN = config['token']
PREFIX = config['prefix']
DEFAULT_BALANCE = config['default_balance']
CURRENCY = config['currency']

# Инициализация бота
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


# Функция для загрузки конфигурации
def get_config():
    return {
        'token': TOKEN,
        'prefix': PREFIX,
        'default_balance': DEFAULT_BALANCE,
        'currency': CURRENCY
    }


@bot.event
async def on_ready():
    print(f'{bot.user} подключился к Discord!')

    # Инициализируем базу данных
    init_db()

    # Очищаем просроченные переводы при запуске
    expired = cleanup_expired_transfers()
    if expired > 0:
        print(f"Очищено {expired} просроченных переводов")

    # Устанавливаем статус бота
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"админ-панель | {PREFIX}помощь"
    )
    await bot.change_presence(activity=activity)

    # Синхронизируем команды
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")


# Загружаем конфигурацию
config_data = get_config()

# Регистрируем команды из модулей
setup_balance_commands(bot, config_data)
setup_fraction_commands(bot, config_data)
setup_admin_commands(bot, config_data)
# setup_payment_commands(bot, config_data)


# КОМАНДА ПОМОЩИ
@bot.hybrid_command(name="помощь", description="Показать все команды бота")
async def help_bot(ctx):
    try:
        embed = discord.Embed(
            title="📚 Список команд бота",
            description="Экономический бот с фракциями и админ-панелью",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="💰 Экономика",
            value=f"`{PREFIX}баланс [@участник]` - Показать баланс\n"
                  f"`{PREFIX}перевод @участник сумма` - Перевести деньги (с подтверждением)\n"
                  f"`{PREFIX}перевод_фракции название сумма` - Перевести деньги в любую фракцию (с подтверждением)",
            inline=False
        )

        embed.add_field(
            name="🏛️ Фракции",
            value=f"`{PREFIX}фракция создать название описание [цвет]` - Создать фракцию\n"
                  f"`{PREFIX}фракция информация [название]` - Информация о фракции\n"
                  f"`{PREFIX}фракция участники [название]` - Участники фракции\n"
                  f"`{PREFIX}фракция список` - Список всех фракций\n"
                  f"`{PREFIX}фракция вступить название` - Вступить во фракцию\n"
                  f"`{PREFIX}фракция покинуть` - Покинуть фракцию",
            inline=False
        )

        embed.add_field(
            name="⚙️ Администрирование",
            value=f"`{PREFIX}админ` - Админ панель\n"
                  f"`{PREFIX}админ_роли` - Управление доступом\n"
                  f"`{PREFIX}проверить_админ` - Проверить свой доступ",
            inline=False
        )

        embed.set_footer(text="Используйте слэш-команды (/) для удобного ввода")
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Ошибка в команде помощь: {e}")
        await ctx.send("❌ Произошла ошибка при отображении справки", ephemeral=True)


# Запуск бота
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:

        print(f"Ошибка при запуске бота: {e}")
