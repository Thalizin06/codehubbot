import discord
from discord.ext import commands
import json, random, string, asyncio, io
import chat_exporter
from discord.utils import get, utcnow
from pathlib import Path

from discord.ui import Button, View

class TicketView(discord.ui.View):
    def __init__(self, config, guild_id):
        super().__init__(timeout=None)
        self.config = config
        self.guild_id = guild_id

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.grey, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild

        categorias = self.config["TICKET_CONFIG"]["TICKET_CATEGORIES"]
        if not categorias:
            return await interaction.response.send_message("❌ Nenhuma categoria configurada.", ephemeral=True)

        tipo = list(categorias.keys())[0]
        categoria_id = categorias[tipo]
        categoria = get(guild.categories, id=categoria_id)

        serial = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        ticket_name = f"ticket-{user.name}-{serial}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        for role_id in self.config["TICKET_CONFIG"]["TICKET_ROLES"]:
            role = get(guild.roles, id=role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)


        await interaction.response.send_message("🔄 Iniciando criação do ticket...", ephemeral=True)
        await asyncio.sleep(0.15)
        msg = await interaction.original_response()

        # Animação de carregamento
        frames = ["|", "/", "-", "\\"]
        for _ in range(2):  # repete o ciclo 2 vezes
            for frame in frames:
                await msg.edit(content=f"🎟️ Criando seu ticket... {frame}")
                await asyncio.sleep(0.1)

        ticket_channel = await guild.create_text_channel(
            name=ticket_name,
            category=categoria,
            topic=f"OWNER: {user} | ID TICKET: {interaction.channel.id} | OWNER ID: {user.id}",
            overwrites=overwrites
        )

        substituicoes = {
            "{user}": user.mention,
            "{channel.id}": str(interaction.channel.id),
            # Adicione outras substituições conforme necessário
        }

        # Fazendo as substituições em DESCRIPTION
        msg_data = self.config["TICKET_CONFIG"]["TICKET_MESSAGES"]["TICKET_OPENED"]
        descricao = msg_data["DESCRIPTION"]
        for chave, valor in substituicoes.items():
            descricao = descricao.replace(chave, valor)

        embed = discord.Embed(
            title=msg_data["TITLE"],
            description=descricao,
            color=discord.Color.random()
        )
        await ticket_channel.send(embed=embed, view=ManageTicketView(user, self.config))
        await msg.edit(content=f"✅ Ticket criado com sucesso: {ticket_channel.mention}")

class ManageTicketView(discord.ui.View):
    def __init__(self, user, config):
        super().__init__(timeout=None)
        self.creator = user
        self.config = config
        self.claimed_by = None
        self.ticket_closed = False

    @discord.ui.button(label="Assumir", style=discord.ButtonStyle.secondary, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in self.config["TICKET_CONFIG"]["TICKET_ROLES"] for role in interaction.user.roles):
            return await interaction.response.send_message("🚫 Sem permissão para assumir.", ephemeral=True)

        if self.claimed_by:
            return await interaction.response.send_message(f"Já assumido por {self.claimed_by.mention}.", ephemeral=True)

        self.claimed_by = interaction.user
        button.label = f"Assumido por: {interaction.user.display_name}"
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Fechar", style=discord.ButtonStyle.secondary, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in self.config["TICKET_CONFIG"]["TICKET_ROLES"] for role in interaction.user.roles):
            return await interaction.response.send_message("🚫 Sem permissão para fechar.", ephemeral=True)

        self.ticket_closed = True
        button.label = "Fechado"
        button.disabled = True

        # 👉 Habilita o botão de deletar
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == "delete_ticket":
                item.disabled = False
                break

        await interaction.response.edit_message(view=self)

        overwrites = interaction.channel.overwrites
        try:
            overwrites[self.creator].send_messages = False
        except:
            pass
        await interaction.channel.edit(overwrites=overwrites)

    @discord.ui.button(label="Deletar", style=discord.ButtonStyle.danger, custom_id="delete_ticket", disabled=True)
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in self.config["TICKET_CONFIG"]["TICKET_ROLES"] for role in interaction.user.roles):
            return await interaction.response.send_message("🚫 Sem permissão para deletar.", ephemeral=True)

        # Exportando o transcript
        transcript = await chat_exporter.export(interaction.channel, tz_info="UTC", military_time=True, bot=interaction.client)
        
        if transcript:
            # Criando o arquivo de transcrição
            file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.html")
            
            # Enviando a transcrição para o canal de transcrições
            ts_channel = interaction.guild.get_channel(self.config["TICKET_CONFIG"]["TRANSCRIPTS"])
            message = await ts_channel.send(f"📝| Transcrição: {interaction.channel.name}", file=file)

            # Obtendo a URL do arquivo enviado
            transcript_url = message.attachments[0].url
            
            # Enviando um embed para o canal de logs com um botão para abrir o link do transcript
            logs_channel = interaction.guild.get_channel(self.config["TICKET_CONFIG"]["TICKET_LOG"])

            # Criando o botão de link
            transcript_button = Button(label="Abrir Transcrição", url=transcript_url)

            # Criando a View para o botão
            view = View()
            view.add_item(transcript_button)

            # Criando o embed
            embed = discord.Embed(
                title=f"Transcrição de Ticket | ID: {interaction.channel.id}",
                description=f"O ticket {interaction.channel.name} foi deletado. Você pode visualizar a transcrição clicando no botão abaixo.",
                color=discord.Color.green()
            )

            # Enviando o embed com o botão para o canal de logs
            await logs_channel.send(embed=embed, view=view)

        # Deletando o canal de ticket
        await interaction.channel.delete()

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ticket(self, ctx):
        guild_id = str(ctx.guild.id)
        config_path = Path(f"guilds/{guild_id}.json")
        settings_path = Path("settings.json")

        if not config_path.exists() or not settings_path.exists():
            print("GUILD ID:", guild_id)
            print("settings_path.exists():", settings_path.exists())
            print("config_path.exists():", config_path.exists())
            return await ctx.send("⚠️ Configuração não encontrada.")

        with open(settings_path, "r", encoding="utf-8") as f:
            global_config = json.load(f)
        if guild_id not in global_config["GUILDS"] or not global_config["GUILDS"][guild_id]["PAID"]:
            return await ctx.send("❌ Seu servidor não está autorizado a usar o sistema de tickets.")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        msg = config["TICKET_CONFIG"]["TICKET_MESSAGES"]["TICKET_MENU"]
        embed = discord.Embed(title=msg["TITLE"], description=msg["DESCRIPTION"], color=discord.Color.orange())
        if msg["THUMBNAIL"]:
            embed.set_thumbnail(url=msg["THUMBNAIL"])
        if msg["IMAGE"]:
            embed.set_image(url=msg["IMAGE"])

        await ctx.send(embed=embed, view=TicketView(config, guild_id))

async def setup(bot):
    from .cog_main_ticket import TicketCog, TicketView  # ou ajuste conforme o nome real da sua view/cog
    await bot.add_cog(TicketCog(bot))

    settings_path = Path("settings.json")

    if not settings_path.exists():
        print("[⚠️] Arquivo settings.json não encontrado.")
        return

    with open(settings_path, "r", encoding="utf-8") as f:
        global_config = json.load(f)

    for guild_id in global_config.get("GUILDS", {}).keys():
        path = Path(f"guilds/{guild_id}.json")
        if not path.exists():
            print(f"[⚠️] Arquivo de config para {guild_id} não encontrado.")
            continue

        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Adiciona a view persistente para esse servidor
        bot.add_view(TicketView(config, guild_id))
        bot.add_view(ManageTicketView("", config))


