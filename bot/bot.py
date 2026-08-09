import asyncio
import logging
import os

import discord
import wavelink
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("musicbot")

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
LAVALINK_HOST = os.environ.get("LAVALINK_HOST", "lavalink")
LAVALINK_PORT = os.environ.get("LAVALINK_PORT", "2333")
LAVALINK_PASSWORD = os.environ["LAVALINK_PASSWORD"]

intents = discord.Intents.default()
intents.voice_states = True


class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        node = wavelink.Node(
            uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}",
            password=LAVALINK_PASSWORD,
        )
        await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)

        await self.load_extension("cogs.music")

        global_synced = await self.tree.sync()
        log.info(
            "Synced %d application command(s) globally (can take up to an hour to appear in "
            "servers other than GUILD_ID)",
            len(global_synced),
        )

        guild_ids = [g.strip() for g in os.environ.get("GUILD_IDS", "").split(",") if g.strip()]
        for guild_id in guild_ids:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            guild_synced = await self.tree.sync(guild=guild)
            log.info(
                "Also synced %d application command(s) instantly to guild %s",
                len(guild_synced),
                guild_id,
            )

    async def on_ready(self):
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)


bot = MusicBot()


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    log.info("Wavelink node %s is ready (session=%s)", payload.node.identifier, payload.session_id)


async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
