import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from database import (
    get_admin_roles, get_admin_users, add_admin_role, remove_admin_role,
    add_admin_user, remove_admin_user, get_formatted_settings, save_ui_settings,
    get_balance, update_balance, get_faction_by_name, hex_to_color,
    create_faction, get_role_based_factions, get_all_balances,
    get_total_balance, add_role_salary, remove_role_salary,
    get_all_role_salaries, get_role_salary
)
import sqlite3


# Декоратор для проверки прав доступа к админ-панели
def has_admin_access():
    async def predicate(ctx):
        # Проверяем, что команда используется на сервере
        if not ctx.guild:
            if hasattr(ctx, 'send'):
                await ctx.send("Эта команда доступна только на сервере!", ephemeral=True)
            return False

        # Владелец сервера всегда имеет доступ
        if ctx.author == ctx.guild.owner:
            return True

        # Проверяем права пользователя (по ID)
        admin_users = get_admin_users(ctx.guild.id)
        if ctx.author.id in admin_users:
            return True

        # Проверяем роли пользователя
        user_role_ids = [role.id for role in ctx.author.roles]
        admin_roles = get_admin_roles(ctx.guild.id)

        # Проверяем, есть ли у пользователя хоть одна админская роль
        for role_id in admin_roles:
            if role_id in user_role_ids:
                return True

        if hasattr(ctx, 'send'):
            await ctx.send("❌ У вас нет доступа к админ-панели!", ephemeral=True)
        return False

    return commands.check(predicate)


def setup_admin_commands(bot: commands.Bot, config: dict):
    """Регистрация команд администратора"""

    PREFIX = config['prefix']
    CURRENCY = config['currency']
    DEFAULT_BALANCE = config['default_balance']

    # УПРАВЛЕНИЕ РОЛЯМИ АДМИНОВ
    @bot.hybrid_group(name="админ_роли", description="Управление ролями с доступом к админ-панели")
    @has_admin_access()
    async def admin_roles(ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="👑 Управление админ-ролями",
                description="Доступные команды:\n"
                            f"`{PREFIX}админ_роли добавить_роль @роль` - Добавить роль\n"
                            f"`{PREFIX}админ_роли удалить_роль @роль` - Удалить роль\n"
                            f"`{PREFIX}админ_роли список` - Список ролей\n"
                            f"`{PREFIX}админ_роли добавить_пользователя @пользователь` - Добавить пользователя\n"
                            f"`{PREFIX}админ_роли удалить_пользователя @пользователь` - Удалить пользователя\n"
                            f"`{PREFIX}админ_роли список_пользователей` - Список пользователей",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed, ephemeral=True)

    @admin_roles.command(name="добавить_роль", description="Добавить роль с доступом к админ-панели")
    @app_commands.describe(роль="Роль для добавления")
    async def add_admin_role_cmd(ctx, роль: discord.Role):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет прав для управления админ-ролями!", ephemeral=True)
                    return

            if add_admin_role(ctx.guild.id, роль.id, ctx.author.id):
                embed = discord.Embed(
                    title="✅ Роль добавлена",
                    description=f"Роль {роль.mention} теперь имеет доступ к админ-панели.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Добавил: {ctx.author.display_name}")
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Эта роль уже имеет доступ к админ-панели!", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в команде добавить_роль: {e}")
            await ctx.send("❌ Произошла ошибка при добавлении роли", ephemeral=True)

    @admin_roles.command(name="удалить_роль", description="Удалить роль из списка админов")
    @app_commands.describe(роль="Роль для удаления")
    async def remove_admin_role_cmd(ctx, роль: discord.Role):
        try:
            if ctx.author != ctx.guild.owner:
                await ctx.send("❌ Только владелец сервера может удалять админ-роли!", ephemeral=True)
                return

            remove_admin_role(ctx.guild.id, роль.id)

            embed = discord.Embed(
                title="✅ Роль удалена",
                description=f"Роль {роль.mention} больше не имеет доступ к админ-панели.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Ошибка в команде удалить_роль: {e}")
            await ctx.send("❌ Произошла ошибка при удалении роли", ephemeral=True)

    @admin_roles.command(name="список", description="Показать все роли с доступом к админ-панели")
    async def list_admin_roles_cmd(ctx):
        try:
            admin_role_ids = get_admin_roles(ctx.guild.id)

            if not admin_role_ids:
                embed = discord.Embed(
                    title="👑 Админ-роли",
                    description="Нет назначенных ролей. Только владелец сервера имеет доступ.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            roles_list = []
            for role_id in admin_role_ids:
                role = ctx.guild.get_role(role_id)
                if role:
                    roles_list.append(f"• {role.mention} (ID: {role_id})")
                else:
                    roles_list.append(f"• Удаленная роль (ID: {role_id})")

            embed = discord.Embed(
                title="👑 Роли с доступом к админ-панели",
                description="\n".join(roles_list),
                color=discord.Color.blue()
            )
            embed.add_field(name="Всего ролей", value=str(len(roles_list)))
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Ошибка в команде список: {e}")
            await ctx.send("❌ Произошла ошибка при получении списка ролей", ephemeral=True)

    # АДМИН ПАНЕЛЬ (основная)
    @bot.hybrid_group(name="админ", description="Админ панель")
    @has_admin_access()
    async def admin(ctx):
        if ctx.invoked_subcommand is None:
            try:
                settings = get_formatted_settings(ctx.guild.id)

                # Получаем статистику
                conn = sqlite3.connect('economy.db')
                c = conn.cursor()

                c.execute('SELECT COUNT(*) FROM users WHERE guild_id = ?', (ctx.guild.id,))
                user_count = c.fetchone()[0]

                c.execute('SELECT COUNT(*) FROM factions WHERE guild_id = ?', (ctx.guild.id,))
                faction_count = c.fetchone()[0]

                c.execute('SELECT SUM(balance) FROM users WHERE guild_id = ?', (ctx.guild.id,))
                total_balance_result = c.fetchone()
                total_balance = total_balance_result[0] if total_balance_result[0] is not None else 0

                c.execute('SELECT SUM(balance) FROM factions WHERE guild_id = ?', (ctx.guild.id,))
                faction_total_balance_result = c.fetchone()
                faction_total_balance = faction_total_balance_result[0] if faction_total_balance_result[
                                                                               0] is not None else 0

                conn.close()

                admin_roles_count = len(get_admin_roles(ctx.guild.id))
                admin_users_count = len(get_admin_users(ctx.guild.id))

                embed = discord.Embed(
                    title="⚙️ Админ Панель",
                    description=f"Добро пожаловать, {ctx.author.mention}!",
                    color=settings['color']
                )

                embed.add_field(name="📊 Статистика",
                                value=f"👥 Пользователей: {user_count}\n"
                                      f"🏛️ Фракций: {faction_count}\n"
                                      f"💰 Общий баланс: {total_balance:.2f}{CURRENCY}\n"
                                      f"🏛️ Баланс фракций: {faction_total_balance:.2f}{CURRENCY}",
                                inline=False)

                embed.add_field(name="🔐 Уровень доступа",
                                value=f"👑 Ролей админов: {admin_roles_count}\n"
                                      f"👤 Пользователей админов: {admin_users_count}",
                                inline=True)

                embed.add_field(name="📁 Основные команды",
                                value=f"`{PREFIX}админ установить_баланс` - Баланс игрока\n"
                                      f"`{PREFIX}админ редактировать_фракцию` - Редактировать фракцию\n"
                                      f"`{PREFIX}админ создать_ролевую_фракцию` - Создать ролевую фракцию\n"
                                      f"`{PREFIX}админ список_ролевых_фракций` - Список ролевых фракций\n"
                                      f"`{PREFIX}админ настройки_интерфейса` - Настройки интерфейса\n"
                                      f"`{PREFIX}админ общий_баланс` - Общий баланс сервера\n"
                                      f"`{PREFIX}админ зарплаты` - Управление зарплатами\n"
                                      f"'{PREFIX}админ add_balance` - пополняет баланс участнику",
                                inline=True)

                embed.set_footer(text=settings['footer'])
                await ctx.send(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"Ошибка в команде админ: {e}")
                await ctx.send("❌ Произошла ошибка при отображении админ-панели", ephemeral=True)

    @admin.command(name="установить_баланс", description="Установить баланс игрока")
    @app_commands.describe(участник="Участник", сумма="Новый баланс")
    async def admin_set_balance(ctx, участник: discord.Member, сумма: float):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            c.execute('UPDATE users SET balance = ? WHERE user_id = ? AND guild_id = ?',
                      (сумма, участник.id, ctx.guild.id))

            if c.rowcount == 0:
                c.execute('INSERT INTO users (user_id, guild_id, balance) VALUES (?, ?, ?)',
                          (участник.id, ctx.guild.id, сумма))

            conn.commit()
            conn.close()

            await ctx.send(f"✅ Баланс {участник.mention} установлен на **{сумма:.2f}**{CURRENCY}", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в команде установить_баланс: {e}")
            await ctx.send("❌ Произошла ошибка при установке баланса", ephemeral=True)

    @admin.command(name="редактировать_фракцию", description="Редактировать фракцию")
    @app_commands.describe(название="Название фракции",
                           действие="Действие: добавить_деньги/убрать_деньги/назначить_лидера/переименовать/изменить_описание",
                           значение="Значение")
    async def admin_edit_faction(ctx, название: str, действие: str, значение: str):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            faction = get_faction_by_name(ctx.guild.id, название)

            if not faction:
                await ctx.send("❌ Фракция не найдена!", ephemeral=True)
                conn.close()
                return

            faction_id, guild_id, name, balance, leader_id, color, created_at, description, role_id, is_role_based = faction

            if действие == "добавить_деньги":
                try:
                    amount = float(значение)
                    c.execute('UPDATE factions SET balance = balance + ? WHERE faction_id = ?',
                              (amount, faction_id))
                    embed = discord.Embed(
                        title="✅ Баланс фракции обновлен",
                        description=f"Добавлено {amount:.2f}{CURRENCY} в казну фракции {name}",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed, ephemeral=True)
                except ValueError:
                    await ctx.send("❌ Неверная сумма!", ephemeral=True)

            elif действие == "убрать_деньги":
                try:
                    amount = float(значение)
                    if balance < amount:
                        await ctx.send(f"❌ Недостаточно средств в казне! Доступно: {balance:.2f}{CURRENCY}",
                                       ephemeral=True)
                        conn.close()
                        return
                    c.execute('UPDATE factions SET balance = balance - ? WHERE faction_id = ?',
                              (amount, faction_id))
                    embed = discord.Embed(
                        title="✅ Баланс фракции обновлен",
                        description=f"Списано {amount:.2f}{CURRENCY} из казны фракции {name}",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed, ephemeral=True)
                except ValueError:
                    await ctx.send("❌ Неверная сумма!", ephemeral=True)

            elif действие == "назначить_лидера":
                try:
                    # Пытаемся извлечь ID пользователя из упоминания
                    if значение.startswith('<@') and значение.endswith('>'):
                        user_id = int(значение.strip('<@!>'))
                    else:
                        # Пытаемся интерпретировать как ID
                        user_id = int(значение)

                    # Для ролевых фракций нельзя назначить лидера
                    if is_role_based:
                        await ctx.send("❌ Для ролевых фракций нельзя назначать лидера!", ephemeral=True)
                        conn.close()
                        return

                    # Проверяем, что пользователь состоит во фракции
                    c.execute('SELECT 1 FROM faction_members WHERE faction_id = ? AND user_id = ?',
                              (faction_id, user_id))
                    if not c.fetchone():
                        await ctx.send("❌ Этот пользователь не состоит во фракции!", ephemeral=True)
                        conn.close()
                        return

                    c.execute('UPDATE factions SET leader_id = ? WHERE faction_id = ?',
                              (user_id, faction_id))
                    c.execute('UPDATE faction_members SET role = ? WHERE faction_id = ? AND user_id = ?',
                              ('Лидер', faction_id, user_id))
                    embed = discord.Embed(
                        title="✅ Лидер фракции изменен",
                        description=f"Новый лидер фракции {name} установлен",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed, ephemeral=True)
                except ValueError:
                    await ctx.send("❌ Неверный ID пользователя!", ephemeral=True)

            elif действие == "переименовать":
                c.execute('UPDATE factions SET name = ? WHERE faction_id = ?', (значение, faction_id))
                embed = discord.Embed(
                    title="✅ Название фракции изменено",
                    description=f"Новое название: {значение}",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed, ephemeral=True)

            elif действие == "изменить_описание":
                c.execute('UPDATE factions SET description = ? WHERE faction_id = ?', (значение[:500], faction_id))
                embed = discord.Embed(
                    title="✅ Описание фракции обновлено",
                    description="Описание фракции было изменено",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(
                    "❌ Неизвестное действие! Доступные действия: добавить_деньги, убрать_деньги, назначить_лидера, переименовать, изменить_описание",
                    ephemeral=True)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка в команде редактировать_фракцию: {e}")
            await ctx.send("❌ Произошла ошибка при редактировании фракции", ephemeral=True)

    @admin.command(name="создать_ролевую_фракцию", description="Создать фракцию, привязанную к роли")
    @app_commands.describe(название="Название фракции", роль="Роль для привязки", описание="Описание фракции",
                           цвет="Цвет в формате HEX (например, FF0000)")
    async def admin_create_faction_role(ctx, название: str, роль: discord.Role,
                                        описание: Optional[str] = None, цвет: Optional[str] = None):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            # Проверяем валидность HEX цвета
            цвет_hex = цвет or "3498db"
            if цвет_hex and not all(c in "0123456789ABCDEFabcdef" for c in цвет_hex):
                цвет_hex = "3498db"

            # Создаем ролевую фракцию
            faction_id = create_faction(
                guild_id=ctx.guild.id,
                name=название,
                leader_id=0,  # Для ролевых фракций лидер не нужен
                description=описание or "",
                color=цвет_hex,
                role_id=роль.id
            )

            settings = get_formatted_settings(ctx.guild.id)
            embed = discord.Embed(
                title="✅ Ролевая фракция создана",
                description=f"**Название:** {название}\n**Привязана к роли:** {роль.mention}",
                color=hex_to_color(цвет_hex)
            )

            if описание:
                embed.add_field(name="Описание", value=описание, inline=False)

            embed.add_field(name="Особенности",
                            value="• Все пользователи с этой ролью автоматически считаются участниками фракции\n"
                                  "• Фракция не имеет лидера\n"
                                  "• Для вступления нужно получить соответствующую роль",
                            inline=False)

            embed.set_footer(text=settings['footer'])
            await ctx.send(embed=embed)

        except ValueError as e:
            await ctx.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в команде создать_ролевую_фракцию: {e}")
            await ctx.send("❌ Произошла ошибка при создании ролевой фракции", ephemeral=True)

    @admin.command(name="список_ролевых_фракций", description="Список всех ролевых фракций")
    async def admin_list_role_factions(ctx):
        try:
            role_factions = get_role_based_factions(ctx.guild.id)

            if not role_factions:
                embed = discord.Embed(
                    title="🏛️ Ролевые фракции",
                    description="На сервере еще нет ролевых фракций",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            settings = get_formatted_settings(ctx.guild.id)
            embed = discord.Embed(
                title="🏛️ Ролевые фракции сервера",
                color=settings['color']
            )

            for faction in role_factions:
                (faction_id, guild_id, name, balance, leader_id, color,
                 created_at, description, role_id, is_role_based) = faction

                role = ctx.guild.get_role(role_id) if role_id else None

                faction_info = f"**ID:** {faction_id}\n"
                faction_info += f"**Баланс:** {balance:.2f}{CURRENCY}\n"
                faction_info += f"**Роль:** {role.mention if role else 'Роль удалена'}"

                embed.add_field(name=f"🏛️ {name}", value=faction_info, inline=False)

            embed.set_footer(text=settings['footer'])
            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Ошибка в команде список_ролевых_фракций: {e}")
            await ctx.send("❌ Произошла ошибка при получении списка ролевых фракций", ephemeral=True)

    @admin.command(name="настройки_интерфейса", description="Настройки интерфейса")
    @app_commands.describe(цвет="Цвет embed (HEX, например FF0000)", подвал="Текст в подвале")
    async def admin_ui_settings(ctx, цвет: Optional[str] = None, подвал: Optional[str] = None):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            # Проверяем валидность цвета HEX
            if цвет and not all(c in "0123456789ABCDEFabcdef" for c in цвет):
                await ctx.send("❌ Неверный формат цвета HEX!", ephemeral=True)
                return

            save_ui_settings(ctx.guild.id, цвет, подвал)

            await ctx.send("✅ Настройки интерфейса обновлены!", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в команде настройки_интерфейса: {e}")
            await ctx.send("❌ Произошла ошибка при обновлении настроек интерфейса", ephemeral=True)

    @admin.command(name="общий_баланс", description="Общий баланс сервера")
    @app_commands.describe(игнорировать_роль="Роль, которую игнорировать при подсчете")
    async def admin_total_balance(ctx, игнорировать_роль: Optional[discord.Role] = None):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            settings = get_formatted_settings(ctx.guild.id)

            # Получаем все балансы
            all_balances = get_all_balances(ctx.guild.id)

            if not all_balances:
                embed = discord.Embed(
                    title="💰 Общий баланс сервера",
                    description="На сервере еще нет зарегистрированных игроков",
                    color=settings['color']
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Фильтруем пользователей по ролям если нужно
            total = 0
            user_count = 0
            ignored_count = 0

            for user_id, balance in all_balances:
                user = ctx.guild.get_member(user_id)
                if not user:
                    continue

                # Проверяем игнорируемую роль
                if игнорировать_роль and игнорировать_роль in user.roles:
                    ignored_count += 1
                    continue

                total += balance
                user_count += 1

            # Получаем топ-10 самых богатых игроков
            rich_players = []
            for user_id, balance in all_balances:
                user = ctx.guild.get_member(user_id)
                if user and (not игнорировать_роль or игнорировать_роль not in user.roles):
                    rich_players.append((user, balance))

            # Сортируем по балансу
            rich_players.sort(key=lambda x: x[1], reverse=True)
            top_10 = rich_players[:10]

            # Создаем embed
            embed = discord.Embed(
                title="💰 Общий баланс сервера",
                color=settings['color']
            )

            embed.add_field(
                name="📊 Статистика",
                value=f"**Общая сумма:** {total:.2f}{CURRENCY}\n"
                      f"**Учитываемых игроков:** {user_count}\n"
                      f"**Игнорировано игроков:** {ignored_count}",
                inline=False
            )

            if игнорировать_роль:
                embed.add_field(
                    name="⚙️ Фильтр",
                    value=f"Игнорируется роль: {игнорировать_роль.mention}",
                    inline=True
                )

            # Добавляем топ-10
            if top_10:
                top_text = ""
                for i, (user, balance) in enumerate(top_10, 1):
                    top_text += f"{i}. {user.display_name}: {balance:.2f}{CURRENCY}\n"

                embed.add_field(
                    name="🏆 Топ-10 самых богатых игроков",
                    value=top_text,
                    inline=False
                )

            embed.set_footer(text=settings['footer'])
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Ошибка в команде общий_баланс: {e}")
            await ctx.send("❌ Произошла ошибка при получении общего баланса", ephemeral=True)

    # КОМАНДА ПРОВЕРКИ ДОСТУПА
    @bot.hybrid_command(name="проверить_админ", description="Проверить доступ к админ-панели")
    async def check_admin_access(ctx):
        try:
            has_access = False
            reasons = []

            if ctx.author == ctx.guild.owner:
                has_access = True
                reasons.append("✅ Вы владелец сервера")

            admin_users = get_admin_users(ctx.guild.id)
            if ctx.author.id in admin_users:
                has_access = True
                reasons.append("✅ Вы в списке пользователей с доступом")

            user_role_ids = [role.id for role in ctx.author.roles]
            admin_roles_list = get_admin_roles(ctx.guild.id)

            matching_roles = []
            for role_id in admin_roles_list:
                if role_id in user_role_ids:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        matching_roles.append(role.name)

            if matching_roles:
                has_access = True
                reasons.append(f"✅ У вас есть роли: {', '.join(matching_roles)}")

            color = discord.Color.green() if has_access else discord.Color.red()
            title = "✅ Доступ к админ-панели есть" if has_access else "❌ Доступа к админ-панели нет"

            embed = discord.Embed(
                title=title,
                color=color
            )

            if reasons:
                embed.description = "\n".join(reasons)
            else:
                embed.description = "У вас нет специальных прав доступа."

            if has_access:
                embed.add_field(
                    name="Доступные команды",
                    value=f"Используйте `{PREFIX}админ` для доступа к админ-панели\n"
                          f"Используйте `{PREFIX}админ_роли` для управления доступом",
                    inline=False
                )

            embed.set_footer(text=f"Запрошено: {ctx.author.display_name}")
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Ошибка в команде проверить_админ: {e}")
            await ctx.send("❌ Произошла ошибка при проверке доступа", ephemeral=True)

    @admin.command(name="add_balance", description="Пополнить баланс игрока")
    @app_commands.rename(участник="участник", сумма="сумма")
    @app_commands.describe(участник="Участник для пополнения", сумма="Сумма пополнения")
    async def admin_balance_add(ctx, участник: discord.Member, сумма: float):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            if сумма <= 0:
                await ctx.send("❌ Сумма должна быть положительной!", ephemeral=True)
                return

            # Начисляем сумму получателю
            update_balance(участник.id, ctx.guild.id, сумма, DEFAULT_BALANCE)

            settings = get_formatted_settings(ctx.guild.id)

            embed = discord.Embed(
                title="✅ Пополнение выполнено",
                description=f"**{ctx.author.display_name}** → **{участник.display_name}**\nСумма: **{сумма:.2f}**{CURRENCY}",
                color=discord.Color.green()
            )
            embed.add_field(name="Баланс получателя",
                            value=f"{get_balance(участник.id, ctx.guild.id, DEFAULT_BALANCE):.2f}{CURRENCY}")
            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Ошибка в команде admin_balance_add: {e}")
            await ctx.send("❌ Произошла ошибка при выполнении пополнения", ephemeral=True)

    @admin.command(name="remove_balance", description="Списать баланс у игрока")
    @app_commands.rename(участник="участник", сумма="сумма")
    @app_commands.describe(участник="Участник для списания", сумма="Сумма списания")
    async def admin_balance_remove(ctx, участник: discord.Member, сумма: float):
        try:
            if ctx.author != ctx.guild.owner and ctx.author.id not in get_admin_users(ctx.guild.id):
                user_roles = [r.id for r in ctx.author.roles]
                admin_roles_list = get_admin_roles(ctx.guild.id)
                if not any(role_id in admin_roles_list for role_id in user_roles):
                    await ctx.send("❌ У вас нет доступа к этой команде!", ephemeral=True)
                    return

            if сумма <= 0:
                await ctx.send("❌ Сумма должна быть положительной!", ephemeral=True)
                return

            # Получаем текущий баланс перед списанием
            current_balance = get_balance(участник.id, ctx.guild.id, DEFAULT_BALANCE)

            # Проверяем, достаточно ли средств для списания
            if сумма > current_balance:
                await ctx.send(
                    f"❌ Недостаточно средств! У игрока {участник.display_name} только {current_balance:.2f}{CURRENCY}",
                    ephemeral=True)
                return

            # Вычитаем сумму из баланса получателя (передаем отрицательное значение)
            update_balance(участник.id, ctx.guild.id, -сумма, DEFAULT_BALANCE)

            settings = get_formatted_settings(ctx.guild.id)

            embed = discord.Embed(
                title="✅ Списание выполнено",
                description=f"**{ctx.author.display_name}** → **{участник.display_name}**\nСписано: **{сумма:.2f}**{CURRENCY}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Новый баланс получателя",
                            value=f"{get_balance(участник.id, ctx.guild.id, DEFAULT_BALANCE):.2f}{CURRENCY}")
            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Ошибка в команде admin_balance_remove: {e}")
            await ctx.send("❌ Произошла ошибка при выполнении списания", ephemeral=True)