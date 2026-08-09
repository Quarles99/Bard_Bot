import discord
import wavelink
from discord import app_commands
from discord.ext import commands


def format_duration(ms: int) -> str:
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


@app_commands.guild_only()
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="play", description="Play a song or add it to the queue")
    @app_commands.describe(query="A search term, YouTube/SoundCloud URL, or playlist URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.followup.send("Join a voice channel first.")
            return

        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.disabled

        results: wavelink.Search = await wavelink.Playable.search(query)
        if not results:
            await interaction.followup.send(f"No results found for `{query}`.")
            return

        if isinstance(results, wavelink.Playlist):
            added = await player.queue.put_wait(results)
            await interaction.followup.send(
                f"Queued playlist **{results.name}** ({added} tracks)."
            )
        else:
            track = results[0]
            await player.queue.put_wait(track)
            await interaction.followup.send(f"Queued **{track.title}**.")

        if not player.playing:
            await player.play(player.queue.get())

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None or not player.playing:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        await player.skip(force=True)
        await interaction.response.send_message("Skipped.")

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None or not player.playing:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        await player.pause(True)
        await interaction.response.send_message("Paused.")

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None:
            await interaction.response.send_message("Nothing to resume.", ephemeral=True)
            return
        await player.pause(False)
        await interaction.response.send_message("Resumed.")

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None:
            await interaction.response.send_message("Not playing anything.", ephemeral=True)
            return
        player.queue.clear()
        await player.stop()
        await interaction.response.send_message("Stopped and cleared the queue.")

    @app_commands.command(name="leave", description="Disconnect the bot from voice")
    async def leave(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None:
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return
        await player.disconnect()
        await interaction.response.send_message("Disconnected.")

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None or (not player.playing and player.queue.is_empty):
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return

        lines = []
        if player.current:
            lines.append(f"**Now Playing:** {player.current.title} ({format_duration(player.current.length)})")
        for i, track in enumerate(player.queue, start=1):
            lines.append(f"{i}. {track.title} ({format_duration(track.length)})")
            if i >= 10:
                remaining = len(player.queue) - 10
                if remaining > 0:
                    lines.append(f"...and {remaining} more.")
                break

        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None or player.current is None:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        track = player.current
        await interaction.response.send_message(
            f"**{track.title}** — {format_duration(player.position)}/{format_duration(track.length)}"
        )

    @app_commands.command(name="volume", description="Set playback volume (0-100)")
    @app_commands.describe(level="Volume percentage from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None:
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return
        await player.set_volume(level)
        await interaction.response.send_message(f"Volume set to {level}%.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if player is None:
            return
        if not player.queue.is_empty and not player.playing:
            next_track = player.queue.get()
            await player.play(next_track)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
