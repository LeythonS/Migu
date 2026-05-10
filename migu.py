import discord
from discord import app_commands
from discord.ext import tasks
import asyncio
import os
import subprocess
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import aiohttp
from aiohttp import web
import secrets

load_dotenv()

TEXT_CHANNEL_NAME = os.getenv("TEXT_CHANNEL_NAME", "now-playing")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

GITHUB_REPO = "LeythonS/Migu"
GITHUB_API  = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"

def get_local_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return None

async def check_for_updates(admin_user: discord.User = None):
    local = get_local_commit()
    try:
        async with aiohttp.ClientSession(headers={"Accept": "application/vnd.github+json"}) as session:
            async with session.get(GITHUB_API) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()
                remote = data.get("sha")
                if not remote:
                    return

        if local and remote.startswith(local[:7]):
            print("✓ Migu is up to date.")
            return

        short = remote[:7]
        msg = data.get("commit", {}).get("message", "").splitlines()[0]
        print("━" * 48)
        print("⚠  A new update is available for Migu!")
        print(f"   Latest commit : {short} — {msg}")
        print("   Run: git pull")
        print("━" * 48)

        if admin_user:
            embed = discord.Embed(
                title="⚠️ Migu Update Available",
                description=(
                    f"A new commit has been pushed to the repository.\n\n"
                    f"**Latest:** `{short}` — {msg}\n\n"
                    f"Run `git pull` in your Migu folder to update."
                ),
                color=0xf0a500
            )
            embed.set_footer(text="github.com/LeythonS/Migu")
            try:
                await admin_user.send(embed=embed)
            except discord.Forbidden:
                print("  Could not DM admin — DMs may be disabled.")
    except Exception as e:
        print(f"Update check failed: {e}")

class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.presences = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced.")

bot = Bot()

session_owner_id = None
session_voice_channel_id = None
session_sp = None
current_track_id = None
is_spotify_paused = False
now_playing_message = None
pending_auths = {}
is_loading_track = False



def format_time(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def build_progress_bar(progress_s, duration_s, length=14):
    if duration_s <= 0:
        return ""
    ratio = min(progress_s / duration_s, 1.0)
    pos = int(ratio * length)
    bar = "─" * pos + "●" + "─" * (length - pos)
    return f"▶ {bar} {format_time(progress_s)} / {format_time(duration_s)}"

def embed_now_playing(title, artist, paused=False, owner=None, progress_s=0, duration_s=0, album_art=None):
    bar = build_progress_bar(progress_s, duration_s)
    description = f"**{title}**\n{artist}"
    if bar:
        prefix = "⏸️ " if paused else ""
        description += f"\n\n{prefix}{bar}"
    embed = discord.Embed(
        title="Paused" if paused else "Now Playing",
        description=description,
        color=0x808080 if paused else 0x1DB954
    )
    if album_art:
        embed.set_thumbnail(url=album_art)
    if owner:
        embed.set_footer(text=f"Session by {owner.display_name} · Streaming via Spotify → YouTube · ☕ ko-fi.com/saypi", icon_url=owner.display_avatar.url)
    else:
        embed.set_footer(text="Streaming via Spotify → YouTube · ☕ ko-fi.com/saypi")
    return embed

def embed_error(description):
    return discord.Embed(description=description, color=0xe74c3c)

def embed_info(description):
    return discord.Embed(description=description, color=0x2f3136)

def embed_success(description):
    return discord.Embed(description=description, color=0x1DB954)

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": True,
}

def get_youtube_url(query):
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        info = ydl.extract_info(f"ytsearch:{query} official audio", download=False)
        if info and "entries" in info and info["entries"]:
            return info["entries"][0]["url"]
    return None

def get_spotify_state():
    if not session_sp:
        return None
    try:
        playback = session_sp.current_playback()
        if playback and playback["item"]:
            track = playback["item"]
            images = track.get("album", {}).get("images", [])
            album_art = images[0]["url"] if images else None
            return {
                "id": track["id"],
                "title": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track.get("album", {}).get("name", ""),
                "album_art": album_art,
                "is_playing": playback["is_playing"],
                "progress_s": playback["progress_ms"] / 1000,
                "duration_s": track["duration_ms"] / 1000,
                "shuffle": playback["shuffle_state"],
                "repeat": playback["repeat_state"],
                "volume": playback["device"]["volume_percent"],
            }
    except Exception as e:
        print(f"Spotify error: {e}")
    return None

_text_channel_cache = {}

async def get_text_channel(guild: discord.Guild):
    if guild.id in _text_channel_cache:
        return _text_channel_cache[guild.id]
    ch = discord.utils.get(guild.text_channels, name=TEXT_CHANNEL_NAME)
    if ch:
        _text_channel_cache[guild.id] = ch
    return ch

async def update_presence(title=None, artist=None, paused=False):
    if title and artist:
        name = f"{title} by {artist}"
        if paused:
            await bot.change_presence(
                status=discord.Status.idle,
                activity=discord.Activity(type=discord.ActivityType.listening, name=f"{name} (Paused)")
            )
        else:
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.listening, name=name)
            )
    else:
        await bot.change_presence(status=discord.Status.online, activity=None)

async def purge_now_playing_messages(text_channel):
    global now_playing_message
    if now_playing_message:
        try:
            await now_playing_message.delete()
        except Exception:
            pass
        now_playing_message = None
    try:
        async for msg in text_channel.history(limit=30):
            if msg.author == bot.user and msg.embeds:
                title_text = msg.embeds[0].title or ""
                if title_text in ("Now Playing", "Paused"):
                    try:
                        await msg.delete()
                    except Exception:
                        pass
    except Exception:
        pass

async def send_now_playing(title, artist, paused=False, progress_s=0, duration_s=0, album_art=None):
    global now_playing_message
    owner = bot.get_user(session_owner_id) if session_owner_id else None
    vc_channel = bot.get_channel(session_voice_channel_id)
    if not vc_channel or not hasattr(vc_channel, "guild"):
        return
    text_channel = await get_text_channel(vc_channel.guild)
    if not text_channel:
        return
    await update_presence(title, artist, paused)
    embed = embed_now_playing(title, artist, paused, owner=owner, progress_s=progress_s, duration_s=duration_s, album_art=album_art)
    if now_playing_message:
        try:
            await now_playing_message.edit(embed=embed)
            return
        except Exception:
            pass
    await purge_now_playing_messages(text_channel)
    now_playing_message = await text_channel.send(embed=embed)

async def end_session(guild: discord.Guild):
    global session_owner_id, session_voice_channel_id, session_sp
    global current_track_id, is_spotify_paused, now_playing_message
    vc = guild.voice_client
    if vc:
        if spotify_poll.is_running():
            spotify_poll.stop()
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await vc.disconnect()
    session_owner_id = None
    session_voice_channel_id = None
    session_sp = None
    current_track_id = None
    is_spotify_paused = False
    if now_playing_message:
        try:
            await now_playing_message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass
    now_playing_message = None
    await update_presence()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    admin_user = await bot.fetch_user(ADMIN_ID)
    await check_for_updates(admin_user)

@tasks.loop(seconds=2)
async def spotify_poll(vc):
    global current_track_id, is_spotify_paused, now_playing_message, is_loading_track
    if not vc.is_connected():
        spotify_poll.stop()
        return
    if is_loading_track:
        return
    state = get_spotify_state()
    if not state:
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        current_track_id = None
        return
    if state["id"] == current_track_id:
        if not state["is_playing"] and vc.is_playing():
            vc.pause()
            is_spotify_paused = True
            await send_now_playing(state["title"], state["artist"], paused=True, progress_s=state["progress_s"], duration_s=state["duration_s"], album_art=state.get("album_art"))
        elif state["is_playing"] and vc.is_paused() and is_spotify_paused:
            vc.resume()
            is_spotify_paused = False
            await send_now_playing(state["title"], state["artist"], paused=False, progress_s=state["progress_s"], duration_s=state["duration_s"], album_art=state.get("album_art"))
        elif state["is_playing"] and now_playing_message:
            owner = bot.get_user(session_owner_id) if session_owner_id else None
            try:
                await now_playing_message.edit(embed=embed_now_playing(state["title"], state["artist"], paused=False, owner=owner, progress_s=state["progress_s"], duration_s=state["duration_s"], album_art=state.get("album_art")))
            except Exception:
                pass
        return
    if not state["is_playing"]:
        return
    is_loading_track = True
    try:
        current_track_id = state["id"]
        is_spotify_paused = False
        query = f"{state['title']} {state['artist']}"
        print(f"Now playing: {state['title']} by {state['artist']}")
        url = await asyncio.get_event_loop().run_in_executor(None, get_youtube_url, query)
        if not url:
            print("Could not find song on YouTube.")
            return
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await asyncio.sleep(0.3)
        seek_seconds = max(0, state["progress_s"] - 1)
        print(f"Seeking to {seek_seconds:.1f}s")
        vc.play(
            discord.FFmpegPCMAudio(url, before_options=f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {seek_seconds}", options="-vn"),
            after=lambda e: print(f"Playback error: {e}") if e else None
        )
        await send_now_playing(state["title"], state["artist"], progress_s=state["progress_s"], duration_s=state["duration_s"], album_art=state.get("album_art"))
    except Exception as e:
        current_track_id = None
    finally:
        is_loading_track = False

@bot.tree.command(name="join", description="Start a session and stream your Spotify to the voice channel.")
async def join(interaction: discord.Interaction):
    global session_owner_id, session_voice_channel_id
    if interaction.user.voice is None:
        await interaction.response.send_message(embed=embed_error("You must be in a voice channel to start a session."), ephemeral=True)
        return
    if session_owner_id is not None:
        owner = bot.get_user(session_owner_id)
        name = owner.display_name if owner else "someone"
        await interaction.response.send_message(embed=embed_error(f"A session is already active by **{name}**. Wait for them to end it with `/leave`."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    state_token = secrets.token_urlsafe(16)
    pending_auths[state_token] = {
        "user_id": interaction.user.id,
        "voice_channel_id": interaction.user.voice.channel.id,
        "guild_id": interaction.guild.id,
    }
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state user-read-currently-playing user-modify-playback-state",
        state=state_token,
        show_dialog=True
    )
    auth_url = await asyncio.get_event_loop().run_in_executor(None, auth_manager.get_authorize_url)
    embed = discord.Embed(
        title="Spotify Authorization Required",
        description=f"[Click here to connect your Spotify]({auth_url})\n\nThis link is personal and expires shortly. Do not share it.",
        color=0x1DB954
    )
    embed.set_footer(text="You will be redirected back automatically after authorizing.")
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="leave", description="End your session and disconnect the bot.")
async def leave(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("There is no active session."), ephemeral=True)
        return
    is_admin = interaction.user.id == ADMIN_ID
    is_owner = interaction.user.id == session_owner_id
    if not is_owner and not is_admin:
        owner = bot.get_user(session_owner_id)
        name = owner.display_name if owner else "the session owner"
        await interaction.response.send_message(embed=embed_error(f"Only **{name}** or an admin can end this session."), ephemeral=True)
        return
    ended_by = "Admin" if is_admin and not is_owner else interaction.user.display_name
    await interaction.response.send_message(embed=embed_info(f"Session ended by **{ended_by}**."), delete_after=8)
    await end_session(interaction.guild)

@bot.tree.command(name="play", description="Resume Spotify playback.")
async def play(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        session_sp.start_playback()
        await interaction.followup.send(embed=embed_success("Playback resumed."), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to resume: `{e}`"), ephemeral=True)

@bot.tree.command(name="pause", description="Pause Spotify playback.")
async def pause(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        session_sp.pause_playback()
        await interaction.followup.send(embed=embed_info("Playback paused."), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to pause: `{e}`"), ephemeral=True)

@bot.tree.command(name="skip", description="Skip to the next track.")
async def skip(interaction: discord.Interaction):
    global current_track_id
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        session_sp.next_track()
        current_track_id = None
        await interaction.followup.send(embed=embed_success("Skipped to next track."), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to skip: `{e}`"), ephemeral=True)

@bot.tree.command(name="prev", description="Go back to the previous track.")
async def prev(interaction: discord.Interaction):
    global current_track_id
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        session_sp.previous_track()
        current_track_id = None
        await interaction.followup.send(embed=embed_success("Playing previous track."), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to go back: `{e}`"), ephemeral=True)

@bot.tree.command(name="shuffle", description="Toggle shuffle on or off.")
async def shuffle(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        state = await asyncio.get_event_loop().run_in_executor(None, get_spotify_state)
        if not state:
            await interaction.followup.send(embed=embed_error("Nothing is playing on Spotify."), ephemeral=True)
            return
        new_state = not state["shuffle"]
        session_sp.shuffle(new_state)
        await interaction.followup.send(embed=embed_success(f"Shuffle {'enabled' if new_state else 'disabled'}."), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to toggle shuffle: `{e}`"), ephemeral=True)

@bot.tree.command(name="repeat", description="Cycle repeat mode: off → playlist → track.")
async def repeat(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        state = await asyncio.get_event_loop().run_in_executor(None, get_spotify_state)
        if not state:
            await interaction.followup.send(embed=embed_error("Nothing is playing on Spotify."), ephemeral=True)
            return
        modes = {"off": "context", "context": "track", "track": "off"}
        labels = {"off": "Repeat off.", "context": "Repeating playlist.", "track": "Repeating current track."}
        new_mode = modes.get(state["repeat"], "off")
        session_sp.repeat(new_mode)
        await interaction.followup.send(embed=embed_success(labels[new_mode]), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to set repeat: `{e}`"), ephemeral=True)

@bot.tree.command(name="volume", description="Get or set Spotify volume (0–100).")
@app_commands.describe(level="Volume level between 0 and 100.")
async def volume(interaction: discord.Interaction, level: int = None):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    if interaction.user.id != session_owner_id and interaction.user.id != ADMIN_ID:
        await interaction.response.send_message(embed=embed_error("Only the session owner can control playback."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if level is None:
        state = await asyncio.get_event_loop().run_in_executor(None, get_spotify_state)
        if state:
            await interaction.followup.send(embed=embed_info(f"Current volume: **{state['volume']}%**"), ephemeral=True)
        else:
            await interaction.followup.send(embed=embed_error("Nothing is playing on Spotify."), ephemeral=True)
        return
    if not 0 <= level <= 100:
        await interaction.followup.send(embed=embed_error("Volume must be between 0 and 100."), ephemeral=True)
        return
    try:
        session_sp.volume(level)
        await interaction.followup.send(embed=embed_success(f"Volume set to **{level}%**."), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=embed_error(f"Failed to set volume: `{e}`"), ephemeral=True)

@bot.tree.command(name="nowplaying", description="Show the currently playing track.")
async def nowplaying(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_error("No active session. Use `/join` to start one."), ephemeral=True)
        return
    await interaction.response.defer()
    state = await asyncio.get_event_loop().run_in_executor(None, get_spotify_state)
    if state:
        owner = bot.get_user(session_owner_id)
        await interaction.followup.send(embed=embed_now_playing(state["title"], state["artist"], paused=not state["is_playing"], owner=owner, progress_s=state["progress_s"], duration_s=state["duration_s"], album_art=state.get("album_art")))
    else:
        await interaction.followup.send(embed=embed_error("Nothing is currently playing on Spotify."), ephemeral=True)

@bot.tree.command(name="session", description="Show who currently has an active session.")
async def session(interaction: discord.Interaction):
    if session_owner_id is None:
        await interaction.response.send_message(embed=embed_info("No active session. Use `/join` to start one."), ephemeral=True)
        return
    owner = bot.get_user(session_owner_id)
    name = owner.mention if owner else "Unknown"
    channel = bot.get_channel(session_voice_channel_id)
    channel_name = channel.name if channel else "Unknown"
    embed = embed_info(f"Active session by {name} in **{channel_name}**.")
    embed.set_footer(text="Enjoying Migu? Support the dev · ☕ ko-fi.com/saypi")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Check the bot latency.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = embed_info(f"Latency: **{latency}ms**")
    embed.set_footer(text="Enjoying Migu? Support the dev · ☕ ko-fi.com/saypi")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="support", description="Support the developer and view project links.")
async def support(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Support Migu",
        description=(
            "Migu is a free, open-source Discord bot made with ❤️ by **Saypi**.\n\n"
            "If you enjoy using it, consider supporting development!\n\n"
            "☕ **Ko-fi:** [ko-fi.com/saypi](https://ko-fi.com/saypi)\n"
            "💻 **GitHub:** [github.com/LeythonS](https://github.com/LeythonS/)\n"
            "💬 **Discord:** saypi.cyefi"
        ),
        color=0x1DB954
    )
    embed.set_footer(text="Thank you for your support!")
    await interaction.response.send_message(embed=embed)

async def handle_callback(request):
    global session_owner_id, session_voice_channel_id, session_sp
    code = request.rel_url.query.get("code")
    state_token = request.rel_url.query.get("state")
    error = request.rel_url.query.get("error")
    if error:
        return web.Response(text="Authorization was denied. You can close this tab.", content_type="text/html")
    if not code or not state_token or state_token not in pending_auths:
        return web.Response(text="Invalid or expired authorization request. Please try /join again.", content_type="text/html")
    pending = pending_auths.pop(state_token)
    user_id = pending["user_id"]
    voice_channel_id = pending["voice_channel_id"]
    guild_id = pending["guild_id"]
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state user-read-currently-playing user-modify-playback-state",
        state=state_token
    )
    try:
        token_info = auth_manager.get_access_token(code, as_dict=True, check_cache=False)
    except Exception as e:
        print(f"Token exchange error: {e}")
        return web.Response(text="Failed to authenticate with Spotify. Please try again.", content_type="text/html")
    auth_manager_refresh = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state user-read-currently-playing user-modify-playback-state"
    )
    sp_user = spotipy.Spotify(auth_manager=auth_manager_refresh)
    sp_user.auth_manager.token_info = token_info
    session_sp = sp_user
    session_owner_id = user_id
    session_voice_channel_id = voice_channel_id
    guild = bot.get_guild(guild_id)
    if guild:
        channel = bot.get_channel(voice_channel_id)
        vc = guild.voice_client
        if vc is not None:
            await vc.move_to(channel)
        else:
            vc = await channel.connect()
        if not spotify_poll.is_running():
            spotify_poll.start(vc)
        owner = guild.get_member(user_id)
        text_channel = discord.utils.get(guild.text_channels, name=TEXT_CHANNEL_NAME)
        if text_channel and owner:
            embed = embed_success(f"Session started. Streaming **{owner.display_name}'s** Spotify to **{channel.name}**.\nUse `/leave` to end the session.")
            embed.set_footer(text="Enjoying Migu? Support the dev · ☕ ko-fi.com/saypi")
            msg = await text_channel.send(embed=embed)
            async def _delete_later(m):
                await asyncio.sleep(10)
                try:
                    await m.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            asyncio.create_task(_delete_later(msg))
    return web.Response(
        text="<html><body style='font-family:sans-serif;text-align:center;padding-top:80px;background:#111;color:#fff'><h2 style='color:#1DB954'>✓ Connected to Spotify</h2><p>You can close this tab and return to Discord.</p></body></html>",
        content_type="text/html"
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get("/callback", handle_callback)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8888)
    await site.start()
    print("OAuth server running on port 8888.")

async def main():
    await start_web_server()
    await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())