[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/saypi)

# Migu

A Discord bot that streams any user's Spotify into a voice channel via YouTube. Users start a session with `/join`, authorize their Spotify account, and the bot follows their playback in real time.

---

## How It Works

1. A user runs `/join` in Discord
2. The bot sends them a private Spotify login link
3. They authorize the bot joins their voice channel and starts streaming whatever they're playing on Spotify
4. When they're done, they run `/leave` to end the session and free the bot for someone else

Audio is sourced from YouTube to match what's playing on Spotify, so **Spotify Premium is not required to listen** only the person sharing their session needs it for playback control.

---

## Requirements

- Python 3.10+
- FFmpeg
- A Spotify Developer account
- A Discord bot application
- ngrok (for OAuth callbacks)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/migu.git
cd migu
```

### 2. Install FFmpeg

**Arch Linux**
```bash
sudo pacman -S ffmpeg
```

**Ubuntu / Debian**
```bash
sudo apt install ffmpeg
```

**macOS**
```bash
brew install ffmpeg
```

**Windows**
Download from https://ffmpeg.org and add to PATH.

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Set up ngrok

ngrok exposes your local OAuth callback server to the internet so Spotify can redirect users back after login.

1. Sign up at https://ngrok.com
2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
3. Claim your free static domain at https://dashboard.ngrok.com/cloud-edge/domains
4. Configure ngrok:

```bash
ngrok config add-authtoken your_authtoken_here
```

### 5. Create a Spotify Developer app

1. Go to https://developer.spotify.com/dashboard and create a new app
2. Under **Settings**, add your ngrok callback as a Redirect URI:
   ```
   https://your-domain.ngrok-free.app/callback
   ```
3. Under **User Management**, add the Spotify email of each person who will use the bot (up to 5 users in development mode)
4. Copy your **Client ID** and **Client Secret**

### 6. Create a Discord bot

1. Go to https://discord.com/developers/applications and create a new application
2. Under **Bot**, enable the **Message Content Intent**
3. Under **OAuth2**, generate an invite URL with the following scopes:
   - `bot`
   - `applications.commands`
4. Under **Bot Permissions**, enable:
   - `Connect`
   - `Speak`
   - `Send Messages`
   - `Embed Links`
5. Invite the bot to your server using the generated URL

### 7. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
DISCORD_TOKEN=your_discord_bot_token
ADMIN_ID=your_discord_user_id
TEXT_CHANNEL_NAME=now-playing
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=https://your-domain.ngrok-free.app/callback
```

To get your Discord user ID: enable Developer Mode in Discord settings, then right-click your name and select **Copy User ID**.

### 8. Run ngrok

Open a separate terminal and start ngrok:

```bash
ngrok http --url=your-domain.ngrok-free.app 8888
```

Keep this running whenever the bot is active.

### 9. Run the bot

```bash
python migu.py
```

---

## Commands

| Command | Description | Access |
|---|---|---|
| `/join` | Start a session with your Spotify | Anyone |
| `/leave` | End the current session | Session owner or Admin |
| `/play` | Resume Spotify playback | Session owner or Admin |
| `/pause` | Pause Spotify playback | Session owner or Admin |
| `/skip` | Skip to next track | Session owner or Admin |
| `/prev` | Go to previous track | Session owner or Admin |
| `/shuffle` | Toggle shuffle | Session owner or Admin |
| `/repeat` | Cycle repeat mode | Session owner or Admin |
| `/volume [0–100]` | Get or set volume | Session owner or Admin |
| `/nowplaying` | Show the current track | Anyone |
| `/session` | Show who has an active session | Anyone |
| `/ping` | Check bot latency | Anyone |

---

## Notes

- Spotify limits development apps to **5 whitelisted users**. Each person who wants to use `/join` must have their Spotify email added under User Management in your Spotify Developer Dashboard.
- If you self-host this bot, you create your own Spotify app with your own set of 5 users and the limit is per app, not per bot.
- User tokens are kept in memory only and cleared when the session ends. No credentials are ever stored to disk.
- There is a natural delay of 2–5 seconds when switching tracks due to YouTube search and FFmpeg startup time.
- The bot seeks to your current position in the song when a new track is detected to stay as close to in sync as possible.
