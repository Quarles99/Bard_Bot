import asyncio

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
    history_group = app_commands.Group(name="history", description="This server's play history")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _ensure_player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.followup.send("Join a voice channel first.")
            return None

        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player is None:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.disabled
            player.text_channel = interaction.channel
        return player

    @app_commands.command(name="play", description="Play a song or add it to the queue")
    @app_commands.describe(query="A search term, YouTube/SoundCloud URL, or playlist URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        player = await self._ensure_player(interaction)
        if player is None:
            return

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
            await self.bot.history.record_play(interaction.guild.id, track)
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

    @history_group.command(name="list", description="Show songs tracked from this server's play history")
    async def history_list(self, interaction: discord.Interaction):
        records = await self.bot.history.list_tracks(interaction.guild.id, limit=200)
        if not records:
            await interaction.response.send_message(
                "No play history yet for this server.", ephemeral=True
            )
            return

        lines = []
        for i, record in enumerate(records, start=1):
            lines.append(
                f"{i}. {record.title} ({format_duration(record.length_ms)}) "
                f"— requested {record.request_count}x"
            )
            if i >= 10:
                remaining = len(records) - 10
                if remaining > 0:
                    lines.append(f"...and {remaining} more.")
                break

        await interaction.response.send_message("\n".join(lines))

    @history_group.command(name="shuffle", description="Queue a random shuffle from this server's play history")
    @app_commands.describe(count="How many songs to shuffle in (1-25)")
    async def history_shuffle(
        self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 25] = 10
    ):
        await interaction.response.defer()

        player = await self._ensure_player(interaction)
        if player is None:
            return

        records = await self.bot.history.sample_tracks(interaction.guild.id, count)
        if not records:
            await interaction.followup.send("No play history yet for this server.")
            return

        results = await asyncio.gather(
            *(wavelink.Playable.search(record.uri) for record in records),
            return_exceptions=True,
        )

        queued = 0
        for result in results:
            if isinstance(result, BaseException) or not result:
                continue
            track = result.tracks[0] if isinstance(result, wavelink.Playlist) else result[0]
            await player.queue.put_wait(track)
            queued += 1

        if queued == 0:
            await interaction.followup.send(
                "Couldn't resolve any tracks from history (they may no longer be available)."
            )
            return

        if not player.playing:
            await player.play(player.queue.get())

        skipped = len(records) - queued
        message = f"Shuffled in {queued} song(s) from this server's history."
        if skipped:
            message += f" ({skipped} couldn't be resolved.)"
        await interaction.followup.send(message)

    @history_group.command(name="remove", description="Remove a song from this server's play history")
    @app_commands.describe(song="The song to remove (pick from the suggestions)")
    async def history_remove(self, interaction: discord.Interaction, song: str):
        try:
            record_id = int(song)
        except ValueError:
            record_id = -1

        removed = await self.bot.history.remove_track(interaction.guild.id, record_id)
        if removed is None:
            await interaction.response.send_message(
                "Couldn't find that song in the history — pick one of the autocomplete suggestions.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Removed **{removed.title}** from this server's play history."
        )

    @history_remove.autocomplete("song")
    async def history_remove_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        records = await self.bot.history.search_titles(interaction.guild.id, current)
        return [
            app_commands.Choice(name=record.title[:100], value=str(record.id))
            for record in records
        ]

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if player is None:
            return
        if not player.queue.is_empty and not player.playing:
            next_track = player.queue.get()
            await player.play(next_track)

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        # Fires when nothing has played for 5 minutes, or the bot has been
        # alone in the channel for a few tracks (wavelink's built-in
        # defaults - see Player.inactive_timeout / inactive_channel_tokens).
        channel = getattr(player, "text_channel", None)
        if channel is not None:
            await channel.send("Leaving the voice channel due to inactivity.")
        await player.disconnect()


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
