import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from database import (
    get_balance, update_balance, get_user_faction, get_faction_balance,
    update_faction_balance, create_pending_transfer, get_pending_transfer,
    delete_pending_transfer, get_formatted_settings, hex_to_color,
    get_faction_by_name,
    get_admin_roles, get_admin_users, add_admin_role, remove_admin_role,
    add_admin_user, remove_admin_user, get_formatted_settings, save_ui_settings,
    get_balance, update_balance, get_faction_by_name, hex_to_color,
    create_faction, get_role_based_factions, get_all_balances,
    get_total_balance, add_role_salary, remove_role_salary,
    get_all_role_salaries, get_role_salary
)
from datetime import datetime


def setup_balance_commands(bot: commands.Bot, config: dict):
    """Регистрация команд баланса и переводов"""

    PREFIX = config['prefix']
    DEFAULT_BALANCE = config['default_balance']
    CURRENCY = config['currency']

    @bot.hybrid_command(name="баланс", description="Показать баланс")
    @app_commands.describe(участник="Участник для проверки баланса")
    async def balance_command(ctx, участник: Optional[discord.Member] = None):
        try:
            target = участник or ctx.author
            balance_amount = get_balance(target.id, ctx.guild.id, DEFAULT_BALANCE)

            # Получаем информацию о фракции, если есть
            faction_info = get_user_faction(target.id, ctx.guild.id)

            settings = get_formatted_settings(ctx.guild.id)
            embed = discord.Embed(
                title=f"💰 Баланс {target.display_name}",
                description=f"**Личный баланс:** {balance_amount:.2f}{CURRENCY}",
                color=settings['color']
            )

            if faction_info:
                embed.add_field(name="🏛️ Фракция", value=faction_info[2], inline=True)
                embed.add_field(name="Роль во фракции",
                                value="Лидер" if faction_info[4] == target.id else "Участник",
                                inline=True)

            embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
            embed.set_footer(text=settings['footer'])

            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Ошибка в команде баланс: {e}")
            await ctx.send("❌ Произошла ошибка при получении баланса", ephemeral=True)

    @bot.hybrid_command(name="перевод", description="Перевести деньги другому игроку")
    @app_commands.describe(участник="Участник для перевода", сумма="Сумма перевода")
    async def pay_command(ctx, участник: discord.Member, сумма: float):
        try:
            if сумма <= 0:
                await ctx.send("❌ Сумма должна быть положительной!", ephemeral=True)
                return

            if участник == ctx.author:
                await ctx.send("❌ Нельзя переводить самому себе!", ephemeral=True)
                return

            sender_balance = get_balance(ctx.author.id, ctx.guild.id, DEFAULT_BALANCE)

            if sender_balance < сумма:
                await ctx.send(f"❌ Недостаточно средств! Ваш баланс: {sender_balance:.2f}{CURRENCY}", ephemeral=True)
                return

            # Создаем ожидающий перевод
            transfer_id = create_pending_transfer(
                guild_id=ctx.guild.id,
                from_user_id=ctx.author.id,
                to_user_id=участник.id,
                to_faction_id=None,
                amount=сумма,
                transfer_type='player_to_player'
            )

            settings = get_formatted_settings(ctx.guild.id)

            class TransferConfirmView(discord.ui.View):
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
                        update_balance(участник.id, ctx.guild.id, сумма, DEFAULT_BALANCE)
                        delete_pending_transfer(self.transfer_id)

                        # Обновляем сообщение
                        embed = discord.Embed(
                            title="✅ Перевод выполнен",
                            description=f"**{ctx.author.display_name}** → **{участник.display_name}**\nСумма: **{сумма:.2f}**{CURRENCY}",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Новый баланс отправителя",
                                        value=f"{get_balance(ctx.author.id, ctx.guild.id, DEFAULT_BALANCE):.2f}{CURRENCY}")
                        embed.add_field(name="Новый баланс получателя",
                                        value=f"{get_balance(участник.id, ctx.guild.id, DEFAULT_BALANCE):.2f}{CURRENCY}")
                        embed.set_footer(text=settings['footer'])

                        for child in self.children:
                            child.disabled = True

                        await interaction.response.edit_message(embed=embed, view=self)

                        # Отправляем уведомление получателю
                        try:
                            notify_embed = discord.Embed(
                                title="💰 Вы получили перевод!",
                                description=f"**{ctx.author.display_name}** перевел вам **{сумма:.2f}**{CURRENCY}",
                                color=discord.Color.green()
                            )
                            notify_embed.add_field(name="Ваш новый баланс",
                                                   value=f"{get_balance(участник.id, ctx.guild.id, DEFAULT_BALANCE):.2f}{CURRENCY}")
                            await участник.send(embed=notify_embed)
                        except:
                            pass
                    except Exception as e:
                        print(f"Ошибка при выполнении перевода: {e}")
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
                        description=f"Перевод {участник.display_name} на сумму {сумма:.2f}{CURRENCY} отменен.",
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
                            description=f"Подтверждение перевода на сумму {сумма:.2f}{CURRENCY} отменено из-за неактивности.",
                            color=discord.Color.orange()
                        )

                        for child in self.children:
                            child.disabled = True

                        await self.message.edit(embed=embed, view=self)
                    except:
                        pass

            embed = discord.Embed(
                title="🔐 Подтвердите перевод",
                description=f"**Отправитель:** {ctx.author.mention}\n**Получатель:** {участник.mention}\n**Сумма:** {сумма:.2f}{CURRENCY}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Баланс отправителя", value=f"{sender_balance:.2f}{CURRENCY}")
            embed.add_field(name="Баланс после перевода", value=f"{sender_balance - сумма:.2f}{CURRENCY}")
            embed.set_footer(text="У вас есть 5 минут на подтверждение")

            view = TransferConfirmView()
            message = await ctx.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            print(f"Ошибка в команде перевод: {e}")
            await ctx.send("❌ Произошла ошибка при создании перевода", ephemeral=True)
