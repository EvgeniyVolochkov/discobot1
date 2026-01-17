import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from database import (
    get_user_faction, get_faction_by_name, get_formatted_settings,
    create_faction, get_faction_members, hex_to_color, get_all_factions,
    get_faction_balance, update_faction_balance, create_pending_transfer,
    get_pending_transfer, delete_pending_transfer, get_balance, update_balance
)
import sqlite3
from datetime import datetime


def setup_fraction_commands(bot: commands.Bot, config: dict):
    """Регистрация команд фракций"""

    CURRENCY = config['currency']
    DEFAULT_BALANCE = config['default_balance']

    @bot.hybrid_group(name="фракция", description="Управление фракциями")
    async def faction(ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🏛️ Система фракций",
                description="Доступные команды:\n"
                            "`!фракция создать` - Создать фракцию\n"
                            "`!фракция информация` - Информация о фракции\n"
                            "`!фракция участники` - Участники фракции\n"
                            "`!фракция список` - Список всех фракций\n"
                            "`!фракция вступить` - Вступить во фракцию\n"
                            "`!фракция покинуть` - Покинуть фракцию\n"
                            "`!перевод_фракции` - Перевести деньги фракции",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

    @faction.command(name="создать", description="Создать новую фракцию")
    @app_commands.describe(название="Название фракции", описание="Описание фракции",
                           цвет="Цвет в формате HEX (например, FF0000)")
    async def create_faction_cmd(ctx, название: str, описание: Optional[str] = None, цвет: Optional[str] = None):
        try:
            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            # Проверяем, не состоит ли пользователь уже во фракции
            c.execute('SELECT faction_id FROM faction_members WHERE user_id = ? AND guild_id = ?',
                      (ctx.author.id, ctx.guild.id))
            if c.fetchone():
                await ctx.send("❌ Вы уже состоите во фракции!", ephemeral=True)
                conn.close()
                return

            # Проверяем валидность HEX цвета
            цвет_hex = цвет or "3498db"
            if цвет_hex and not all(c in "0123456789ABCDEFabcdef" for c in цвет_hex):
                цвет_hex = "3498db"

            # Создаем фракцию через функцию из database
            faction_id = create_faction(
                guild_id=ctx.guild.id,
                name=название,
                leader_id=ctx.author.id,
                description=описание or "",
                color=цвет_hex
            )

            conn.close()

            settings = get_formatted_settings(ctx.guild.id)
            embed = discord.Embed(
                title="✅ Фракция создана",
                description=f"**Название:** {название}\n**Лидер:** {ctx.author.mention}",
                color=hex_to_color(цвет_hex)
            )
            if описание:
                embed.add_field(name="Описание", value=описание, inline=False)
            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в команде фракция создать: {e}")
            await ctx.send("❌ Произошла ошибка при создании фракции", ephemeral=True)

    @faction.command(name="информация", description="Информация о фракции")
    @app_commands.describe(название="Название фракции (оставьте пустым для своей фракции)")
    async def faction_info(ctx, название: Optional[str] = None):
        try:
            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            if название:
                c.execute('''SELECT f.*, COUNT(fm.user_id) as members 
                             FROM factions f 
                             LEFT JOIN faction_members fm ON f.faction_id = fm.faction_id
                             WHERE f.guild_id = ? AND LOWER(f.name) LIKE LOWER(?)
                             GROUP BY f.faction_id''',
                          (ctx.guild.id, f"%{название}%"))
            else:
                # Ищем фракцию пользователя
                c.execute('''SELECT f.*, COUNT(fm2.user_id) as members 
                             FROM factions f
                             JOIN faction_members fm ON f.faction_id = fm.faction_id
                             LEFT JOIN faction_members fm2 ON f.faction_id = fm2.faction_id
                             WHERE fm.user_id = ? AND f.guild_id = ?
                             GROUP BY f.faction_id''',
                          (ctx.author.id, ctx.guild.id))

            faction = c.fetchone()
            conn.close()

            if not faction:
                await ctx.send("❌ Фракция не найдена!", ephemeral=True)
                return

            (faction_id, guild_id, name, balance, leader_id, color, created_at,
             description, role_id, is_role_based, members_count) = faction

            # Получаем лидера
            leader = ctx.guild.get_member(leader_id) if leader_id != 0 else None

            settings = get_formatted_settings(ctx.guild.id)
            color_obj = hex_to_color(color) if color else settings['color']

            embed = discord.Embed(
                title=f"🏛️ {name}",
                description=description or "Описание отсутствует",
                color=color_obj
            )

            # Добавляем информацию о привязке к роли
            if is_role_based and role_id:
                role = ctx.guild.get_role(role_id)
                if role:
                    embed.add_field(name="📌 Привязана к роли", value=role.mention, inline=True)
                    embed.add_field(name="👥 Тип", value="Ролевая фракция", inline=True)
                else:
                    embed.add_field(name="👥 Тип", value="Ролевая фракция (роль удалена)", inline=True)
            else:
                embed.add_field(name="💰 Баланс", value=f"{balance:.2f}{CURRENCY}", inline=True)
                embed.add_field(name="👥 Участников", value=str(members_count), inline=True)

            if leader:
                embed.add_field(name="👑 Лидер", value=leader.mention if leader else "Не найден", inline=True)
            elif not is_role_based:
                embed.add_field(name="👑 Лидер", value="Отсутствует", inline=True)

            try:
                created_date = datetime.fromisoformat(created_at)
                embed.add_field(name="📅 Создана", value=created_date.strftime("%d.%m.%Y"), inline=True)
            except:
                embed.add_field(name="📅 Создана", value="Неизвестно", inline=True)

            # Для обычных фракций показываем топ участников
            if not is_role_based:
                # Получаем топ-3 участников по балансу
                conn = sqlite3.connect('economy.db')
                c = conn.cursor()
                c.execute('''SELECT fm.user_id, u.balance 
                             FROM faction_members fm
                             JOIN users u ON fm.user_id = u.user_id AND fm.guild_id = u.guild_id
                             WHERE fm.faction_id = ?
                             ORDER BY u.balance DESC LIMIT 3''',
                          (faction_id,))

                top_members = c.fetchall()
                conn.close()

                if top_members:
                    members_text = ""
                    for i, (user_id, user_balance) in enumerate(top_members, 1):
                        user = ctx.guild.get_member(user_id)
                        if user:
                            role = "👑" if user_id == leader_id else ""
                            members_text += f"{i}. {role}{user.display_name}: {user_balance:.2f}{CURRENCY}\n"
                    if members_text:
                        embed.add_field(name="🏆 Топ участников по балансу", value=members_text, inline=False)

            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Ошибка в команде фракция информация: {e}")
            await ctx.send("❌ Произошла ошибка при получении информации о фракции", ephemeral=True)

    @faction.command(name="участники", description="Участники фракции")
    @app_commands.describe(название="Название фракции (оставьте пустым для своей фракции)")
    async def faction_members(ctx, название: Optional[str] = None):
        try:
            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            if название:
                c.execute('''SELECT f.faction_id, f.name, f.leader_id, f.is_role_based, f.role_id
                             FROM factions f 
                             WHERE f.guild_id = ? AND LOWER(f.name) LIKE LOWER(?)''',
                          (ctx.guild.id, f"%{название}%"))
            else:
                c.execute('''SELECT f.faction_id, f.name, f.leader_id, f.is_role_based, f.role_id
                             FROM factions f
                             JOIN faction_members fm ON f.faction_id = fm.faction_id
                             WHERE fm.user_id = ? AND f.guild_id = ?''',
                          (ctx.author.id, ctx.guild.id))

            faction = c.fetchone()

            if not faction:
                await ctx.send("❌ Фракция не найдена!", ephemeral=True)
                conn.close()
                return

            faction_id, faction_name, leader_id, is_role_based, role_id = faction

            if is_role_based and role_id:
                # Для ролевой фракции показываем всех пользователей с этой ролью
                role = ctx.guild.get_role(role_id)
                if not role:
                    await ctx.send("❌ Роль, привязанная к фракции, не найдена!", ephemeral=True)
                    conn.close()
                    return

                members = [member for member in ctx.guild.members if role in member.roles]

                if not members:
                    await ctx.send("❌ В фракции нет участников с этой ролью!", ephemeral=True)
                    conn.close()
                    return

                # Разбиваем на страницы (по 10 участников на страницу)
                members_per_page = 10
                pages = []

                for i in range(0, len(members), members_per_page):
                    page_members = members[i:i + members_per_page]

                    embed = discord.Embed(
                        title=f"👥 Участники фракции {faction_name} (ролевая)",
                        color=discord.Color.blue()
                    )

                    for member in page_members:
                        balance = get_balance(member.id, ctx.guild.id, DEFAULT_BALANCE)
                        embed.add_field(
                            name=f"**{member.display_name}**",
                            value=f"Баланс: {balance:.2f}{CURRENCY}",
                            inline=False
                        )

                    total_pages = ((len(members) - 1) // members_per_page) + 1
                    current_page = (i // members_per_page) + 1
                    embed.set_footer(text=f"Страница {current_page}/{total_pages} | Всего участников: {len(members)}")
                    pages.append(embed)

                if len(pages) == 1:
                    await ctx.send(embed=pages[0])
                else:
                    current_page_idx = 0

                    class MembersView(discord.ui.View):
                        def __init__(self, timeout=120):
                            super().__init__(timeout=timeout)

                        @discord.ui.button(label="⬅️ Назад", style=discord.ButtonStyle.secondary, disabled=True)
                        async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                            nonlocal current_page_idx
                            if interaction.user != ctx.author:
                                await interaction.response.send_message(
                                    "❌ Только автор команды может листать страницы!", ephemeral=True)
                                return

                            current_page_idx -= 1
                            self.update_buttons()
                            await interaction.response.edit_message(embed=pages[current_page_idx], view=self)

                        @discord.ui.button(label="Вперед ➡️", style=discord.ButtonStyle.secondary)
                        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                            nonlocal current_page_idx
                            if interaction.user != ctx.author:
                                await interaction.response.send_message(
                                    "❌ Только автор команды может листать страницы!", ephemeral=True)
                                return

                            current_page_idx += 1
                            self.update_buttons()
                            await interaction.response.edit_message(embed=pages[current_page_idx], view=self)

                        def update_buttons(self):
                            self.prev_button.disabled = current_page_idx == 0
                            self.next_button.disabled = current_page_idx == len(pages) - 1

                    view = MembersView()
                    await ctx.send(embed=pages[0], view=view)

                conn.close()
                return

            # Для обычной фракции
            members = get_faction_members(faction_id)

            if not members:
                await ctx.send("❌ В фракции нет участников!", ephemeral=True)
                conn.close()
                return

            # Разбиваем на страницы (по 10 участников на страницу)
            members_per_page = 10
            pages = []

            for i in range(0, len(members), members_per_page):
                page_members = members[i:i + members_per_page]

                embed = discord.Embed(
                    title=f"👥 Участники фракции {faction_name}",
                    color=discord.Color.blue()
                )

                for user_id, role, joined_at, balance in page_members:
                    user = ctx.guild.get_member(user_id)
                    if user:
                        member_text = f"**{user.display_name}**"
                        if user_id == leader_id:
                            member_text = f"👑 {member_text}"

                        balance_text = f"{balance:.2f}{CURRENCY}" if balance is not None else "Неизвестно"

                        try:
                            join_date = datetime.fromisoformat(joined_at).strftime('%d.%m.%Y')
                        except:
                            join_date = "Неизвестно"

                        embed.add_field(
                            name=f"{member_text} ({role})",
                            value=f"Баланс: {balance_text}\nВступил: {join_date}",
                            inline=False
                        )

                total_pages = ((len(members) - 1) // members_per_page) + 1
                current_page = (i // members_per_page) + 1
                embed.set_footer(text=f"Страница {current_page}/{total_pages} | Всего участников: {len(members)}")
                pages.append(embed)

            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                current_page_idx = 0

                class MembersView(discord.ui.View):
                    def __init__(self, timeout=120):
                        super().__init__(timeout=timeout)

                    @discord.ui.button(label="⬅️ Назад", style=discord.ButtonStyle.secondary, disabled=True)
                    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        nonlocal current_page_idx
                        if interaction.user != ctx.author:
                            await interaction.response.send_message("❌ Только автор команды может листать страницы!",
                                                                    ephemeral=True)
                            return

                        current_page_idx -= 1
                        self.update_buttons()
                        await interaction.response.edit_message(embed=pages[current_page_idx], view=self)

                    @discord.ui.button(label="Вперед ➡️", style=discord.ButtonStyle.secondary)
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        nonlocal current_page_idx
                        if interaction.user != ctx.author:
                            await interaction.response.send_message("❌ Только автор команды может листать страницы!",
                                                                    ephemeral=True)
                            return

                        current_page_idx += 1
                        self.update_buttons()
                        await interaction.response.edit_message(embed=pages[current_page_idx], view=self)

                    def update_buttons(self):
                        self.prev_button.disabled = current_page_idx == 0
                        self.next_button.disabled = current_page_idx == len(pages) - 1

                view = MembersView()
                await ctx.send(embed=pages[0], view=view)
        except Exception as e:
            print(f"Ошибка в команде фракция участники: {e}")
            await ctx.send("❌ Произошла ошибка при получении списка участников", ephemeral=True)

    @faction.command(name="список", description="Список всех фракций на сервере")
    async def faction_list(ctx):
        try:
            factions = get_all_factions(ctx.guild.id)

            if not factions:
                embed = discord.Embed(
                    title="🏛️ Фракции сервера",
                    description="На сервере еще нет фракций",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            # Разбиваем на страницы (по 5 фракций на страницу)
            factions_per_page = 5
            pages = []

            for i in range(0, len(factions), factions_per_page):
                page_factions = factions[i:i + factions_per_page]

                embed = discord.Embed(
                    title="🏛️ Фракции сервера",
                    color=discord.Color.blue()
                )

                for (faction_id, guild_id, name, balance, leader_id, color,
                     created_at, description, role_id, is_role_based, member_count) in page_factions:

                    leader = ctx.guild.get_member(leader_id) if leader_id != 0 else None

                    faction_info = f"**ID:** {faction_id}\n"
                    faction_info += f"**Участников:** {member_count}\n"
                    faction_info += f"**Баланс:** {balance:.2f}{CURRENCY}\n"

                    if is_role_based and role_id:
                        role = ctx.guild.get_role(role_id)
                        if role:
                            faction_info += f"**Тип:** Ролевая фракция\n"
                            faction_info += f"**Роль:** {role.mention}"
                        else:
                            faction_info += f"**Тип:** Ролевая фракция (роль удалена)"
                    else:
                        if leader:
                            faction_info += f"**Лидер:** {leader.mention if leader else 'Не найден'}"
                        else:
                            faction_info += f"**Лидер:** Отсутствует"

                    embed.add_field(name=f"🏛️ {name}", value=faction_info, inline=False)

                total_pages = ((len(factions) - 1) // factions_per_page) + 1
                current_page = (i // factions_per_page) + 1
                embed.set_footer(text=f"Страница {current_page}/{total_pages} | Всего фракций: {len(factions)}")
                pages.append(embed)

            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                current_page_idx = 0

                class FactionListView(discord.ui.View):
                    def __init__(self, timeout=120):
                        super().__init__(timeout=timeout)

                    @discord.ui.button(label="⬅️ Назад", style=discord.ButtonStyle.secondary, disabled=True)
                    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        nonlocal current_page_idx
                        if interaction.user != ctx.author:
                            await interaction.response.send_message("❌ Только автор команды может листать страницы!",
                                                                    ephemeral=True)
                            return

                        current_page_idx -= 1
                        self.update_buttons()
                        await interaction.response.edit_message(embed=pages[current_page_idx], view=self)

                    @discord.ui.button(label="Вперед ➡️", style=discord.ButtonStyle.secondary)
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        nonlocal current_page_idx
                        if interaction.user != ctx.author:
                            await interaction.response.send_message("❌ Только автор команды может листать страницы!",
                                                                    ephemeral=True)
                            return

                        current_page_idx += 1
                        self.update_buttons()
                        await interaction.response.edit_message(embed=pages[current_page_idx], view=self)

                    def update_buttons(self):
                        self.prev_button.disabled = current_page_idx == 0
                        self.next_button.disabled = current_page_idx == len(pages) - 1

                view = FactionListView()
                await ctx.send(embed=pages[0], view=view)

        except Exception as e:
            print(f"Ошибка в команде фракция список: {e}")
            await ctx.send("❌ Произошла ошибка при получении списка фракций", ephemeral=True)

    @faction.command(name="вступить", description="Вступить во фракцию")
    @app_commands.describe(название="Название фракции для вступления")
    async def faction_join(ctx, название: str):
        try:
            # Находим фракцию
            faction = get_faction_by_name(ctx.guild.id, название)
            if not faction:
                await ctx.send("❌ Фракция не найдена!", ephemeral=True)
                return

            faction_id = faction[0]
            is_role_based = faction[9]  # Индекс 9 - is_role_based

            if is_role_based:
                await ctx.send("❌ В ролевую фракцию можно вступить только через получение соответствующей роли!",
                               ephemeral=True)
                return

            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            # Проверяем, не состоит ли уже пользователь в другой фракции
            c.execute('SELECT faction_id FROM faction_members WHERE user_id = ? AND guild_id = ?',
                      (ctx.author.id, ctx.guild.id))
            existing_faction = c.fetchone()

            if existing_faction:
                if existing_faction[0] == faction_id:
                    await ctx.send("❌ Вы уже состоите в этой фракции!", ephemeral=True)
                else:
                    await ctx.send("❌ Вы уже состоите в другой фракции! Сначала покиньте текущую фракцию.",
                                   ephemeral=True)
                conn.close()
                return

            # Добавляем пользователя во фракцию
            c.execute('''INSERT INTO faction_members (user_id, guild_id, faction_id, role, joined_at)
                         VALUES (?, ?, ?, ?, ?)''',
                      (ctx.author.id, ctx.guild.id, faction_id, 'Участник', datetime.now().isoformat()))

            conn.commit()
            conn.close()

            settings = get_formatted_settings(ctx.guild.id)
            embed = discord.Embed(
                title="✅ Вы вступили во фракцию",
                description=f"Теперь вы участник фракции **{faction[2]}**",
                color=settings['color']
            )
            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Ошибка в команде фракция вступить: {e}")
            await ctx.send("❌ Произошла ошибка при вступлении во фракцию", ephemeral=True)

    @faction.command(name="покинуть", description="Покинуть фракцию")
    async def faction_leave(ctx):
        try:
            conn = sqlite3.connect('economy.db')
            c = conn.cursor()

            # Получаем фракцию пользователя
            c.execute('''SELECT f.faction_id, f.name, f.leader_id 
                         FROM factions f
                         JOIN faction_members fm ON f.faction_id = fm.faction_id
                         WHERE fm.user_id = ? AND f.guild_id = ?''',
                      (ctx.author.id, ctx.guild.id))

            faction = c.fetchone()

            if not faction:
                await ctx.send("❌ Вы не состоите во фракции!", ephemeral=True)
                conn.close()
                return

            faction_id, faction_name, leader_id = faction

            # Проверяем, не лидер ли пользователь
            if leader_id == ctx.author.id:
                await ctx.send("❌ Лидер не может покинуть фракцию! Сначала передайте лидерство другому участнику.",
                               ephemeral=True)
                conn.close()
                return

            # Удаляем пользователя из фракции
            c.execute('DELETE FROM faction_members WHERE user_id = ? AND guild_id = ?',
                      (ctx.author.id, ctx.guild.id))

            conn.commit()
            conn.close()

            settings = get_formatted_settings(ctx.guild.id)
            embed = discord.Embed(
                title="✅ Вы покинули фракцию",
                description=f"Вы больше не состоите в фракции **{faction_name}**",
                color=settings['color']
            )
            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Ошибка в команде фракция покинуть: {e}")
            await ctx.send("❌ Произошла ошибка при выходе из фракции", ephemeral=True)

    # Новая команда для перевода в любую фракцию
    @bot.hybrid_command(name="перевод_фракции", description="Перевести деньги в фракцию")
    @app_commands.describe(название="Название фракции", сумма="Сумма перевода")
    async def faction_pay(ctx, название: str, сумма: float):
        try:
            if сумма <= 0:
                await ctx.send("❌ Сумма должна быть положительной!", ephemeral=True)
                return

            # Ищем фракцию по названию
            faction_info = get_faction_by_name(ctx.guild.id, название)
            if not faction_info:
                await ctx.send("❌ Фракция не найдена!", ephemeral=True)
                return

            (faction_id, guild_id, name, faction_balance, leader_id, color,
             created_at, description, role_id, is_role_based) = faction_info

            sender_balance = get_balance(ctx.author.id, ctx.guild.id, DEFAULT_BALANCE)

            if sender_balance < сумма:
                await ctx.send(f"❌ Недостаточно средств! Ваш баланс: {sender_balance:.2f}{CURRENCY}", ephemeral=True)
                return

            # Создаем ожидающий перевод
            transfer_id = create_pending_transfer(
                guild_id=ctx.guild.id,
                from_user_id=ctx.author.id,
                to_user_id=None,
                to_faction_id=faction_id,
                amount=сумма,
                transfer_type='player_to_faction'
            )

            settings = get_formatted_settings(ctx.guild.id)

            class FactionTransferConfirmView(discord.ui.View):
                def __init__(self, timeout=300):
                    super().__init__(timeout=timeout)
                    self.transfer_id = transfer_id

                @discord.ui.button(label="✅ Подтвердить перевод", style=discord.ButtonStyle.success, emoji="✅")
                async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("❌ Только отправитель может подтвердить перевод!",
                                                                ephemeral=True)
                        return

                    # Получаем информацию о переводе
                    transfer = get_pending_transfer(self.transfer_id)
                    if not transfer:
                        await interaction.response.send_message("❌ Перевод не найден или истекло время подтверждения!",
                                                                ephemeral=True)
                        return

                    # Проверяем баланс снова
                    current_balance = get_balance(ctx.author.id, ctx.guild.id, DEFAULT_BALANCE)
                    if current_balance < сумма:
                        await interaction.response.send_message(
                            f"❌ Недостаточно средств! Текущий баланс: {current_balance:.2f}{CURRENCY}", ephemeral=True)
                        delete_pending_transfer(self.transfer_id)
                        return

                    try:
                        # Выполняем перевод
                        update_balance(ctx.author.id, ctx.guild.id, -сумма, DEFAULT_BALANCE)
                        update_faction_balance(faction_id, сумма)
                        delete_pending_transfer(self.transfer_id)

                        # Обновляем сообщение
                        new_faction_balance = get_faction_balance(faction_id)
                        embed = discord.Embed(
                            title="✅ Перевод выполнен",
                            description=f"**{ctx.author.display_name}** → **Фракция {name}**\nСумма: **{сумма:.2f}**{CURRENCY}",
                            color=hex_to_color(color) if color else discord.Color.green()
                        )
                        embed.add_field(name="Новый личный баланс",
                                        value=f"{get_balance(ctx.author.id, ctx.guild.id, DEFAULT_BALANCE):.2f}{CURRENCY}")
                        embed.add_field(name="Новый баланс фракции",
                                        value=f"{new_faction_balance:.2f}{CURRENCY}")
                        embed.set_footer(text=settings['footer'])

                        for child in self.children:
                            child.disabled = True

                        await interaction.response.edit_message(embed=embed, view=self)

                        # Уведомляем лидера фракции (если есть)
                        leader = ctx.guild.get_member(leader_id) if leader_id != 0 else None
                        if leader and leader.id != ctx.author.id:
                            try:
                                notify_embed = discord.Embed(
                                    title="🏛️ Пополнение казны фракции",
                                    description=f"**{ctx.author.display_name}** перевел в казну фракции **{name}** сумму **{сумма:.2f}**{CURRENCY}",
                                    color=discord.Color.green()
                                )
                                notify_embed.add_field(name="Новый баланс фракции",
                                                       value=f"{new_faction_balance:.2f}{CURRENCY}")
                                await leader.send(embed=notify_embed)
                            except:
                                pass
                    except Exception as e:
                        print(f"Ошибка при выполнении перевода фракции: {e}")
                        await interaction.response.send_message("❌ Произошла ошибка при выполнении перевода",
                                                                ephemeral=True)

                @discord.ui.button(label="❌ Отменить перевод", style=discord.ButtonStyle.danger, emoji="❌")
                async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("❌ Только отправитель может отменить перевод!",
                                                                ephemeral=True)
                        return

                    delete_pending_transfer(self.transfer_id)

                    embed = discord.Embed(
                        title="❌ Перевод отменен",
                        description=f"Перевод в казну фракции {name} на сумму {сумма:.2f}{CURRENCY} отменен.",
                        color=discord.Color.red()
                    )

                    for child in self.children:
                        child.disabled = True

                    await interaction.response.edit_message(embed=embed, view=self)

                async def on_timeout(self):
                    try:
                        delete_pending_transfer(self.transfer_id)
                        embed = discord.Embed(
                            title="⏰ Время истекло",
                            description=f"Подтверждение перевода в казну фракции {name} на сумму {сумма:.2f}{CURRENCY} отменено.",
                            color=discord.Color.orange()
                        )

                        for child in self.children:
                            child.disabled = True

                        await self.message.edit(embed=embed, view=self)
                    except:
                        pass

            embed = discord.Embed(
                title="🔐 Подтвердите перевод в казну фракции",
                description=f"**Отправитель:** {ctx.author.mention}\n**Фракция:** {name}\n**Сумма:** {сумма:.2f}{CURRENCY}",
                color=hex_to_color(color) if color else discord.Color.gold()
            )
            embed.add_field(name="Ваш текущий баланс", value=f"{sender_balance:.2f}{CURRENCY}")
            embed.add_field(name="Баланс фракции", value=f"{faction_balance:.2f}{CURRENCY}")
            embed.add_field(name="Баланс после перевода", value=f"{sender_balance - сумма:.2f}{CURRENCY}", inline=False)
            embed.set_footer(text="У вас есть 5 минут на подтверждение")

            view = FactionTransferConfirmView()
            message = await ctx.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            print(f"Ошибка в команде перевод_фракции: {e}")
            await ctx.send("❌ Произошла ошибка при создании перевода фракции", ephemeral=True)