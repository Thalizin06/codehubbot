import discord, os, asyncio
from discord.ext import commands, tasks
from colorama import Fore
import json

class MeuHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="Central de Ajuda 🤖",
            description="Esses são os comandos disponíveis:",
            color=discord.Color.purple()
        )

        for cog, commands_list in mapping.items():
            command_names = [f"`{command.name}`" for command in commands_list if not command.hidden]
            if command_names:
                nome_cog = cog.qualified_name if cog else "Sem Categoria"
                embed.add_field(name=nome_cog, value=" ".join(command_names), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

with open("settings.json", "r") as f: # Load settings file
    settings = json.load(f)

bot = commands.Bot(f'{settings["PREFIX"]}', intents=discord.Intents.all(), help_command=MeuHelpCommand())

async def carregar_cogs(): # Load cogs in Code
    for arquivo in os.listdir('cogs'):
        if arquivo.endswith('.py'):
            await bot.load_extension(f"cogs.{arquivo[:-3]}")

@bot.event # Load Cogs in Bot
async def on_ready():
    await carregar_cogs()
    status_task.start()
    print(f"\n{Fore.LIGHTWHITE_EX}[LOG]{Fore.BLACK}︰Started as {Fore.GREEN}{bot.application.name}{Fore.RESET}\n")

@bot.event # Pass Errors
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error
    
@tasks.loop() # Discord Status
async def status_task() -> None:
    await bot.change_presence(status=discord.Status.idle, activity=discord.Game("﹒Developed: Thalizin & Team"))
    await asyncio.sleep(10)
    await bot.change_presence(status=discord.Status.idle, activity=discord.Game("🌟Code Hub®"))
    await asyncio.sleep(10)

@bot.command() # Sincronize app commands
async def sincronize(ctx:commands.Context):
    if ctx.author.id == 786919164668411926:
        sincs = await bot.tree.sync()
        await ctx.reply(f"**{len(sincs)}** Comandos Sincronizados!")
    else: await ctx.reply("Apenas meu dono pode utilizar esse comando!")

bot.run(settings["TOKEN"])