<img width="1920" height="710" alt="migu" src="https://github.com/user-attachments/assets/e225ab77-bf51-4bfd-93b3-1e2c364f2ac7" />

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/saypi)

![Stars](https://img.shields.io/github/stars/LeythonS/Migu?style=flat-square&color=1DB954)
![Forks](https://img.shields.io/github/forks/LeythonS/Migu?style=flat-square&color=1DB954)
![Last Commit](https://img.shields.io/github/last-commit/LeythonS/Migu?style=flat-square&color=1DB954)
![Issues](https://img.shields.io/github/issues/LeythonS/Migu?style=flat-square&color=1DB954)
![Python](https://img.shields.io/badge/Python-3.10%2B-1DB954?style=flat-square)
![License](https://img.shields.io/github/license/LeythonS/Migu?style=flat-square&color=1DB954)

# Migu (Discord Music Bot)

A Discord bot that streams any user's Spotify into a voice channel via YouTube. Users start a session with `/join`, authorize their Spotify account, and the bot follows their playback in real time.

---

## How It Works

1. A user runs `/join` in Discord
2. The bot sends them a private Spotify login link
3. They authorize — the bot joins their voice channel and starts streaming whatever they're playing on Spotify
4. When they're done, they run `/leave` to end the session and free the bot for someone else

Audio is sourced from YouTube to match what's playing on Spotify, so **Spotify Premium is not required to listen** — only the person sharing their session needs it for playback control.

---

## Quick Setup (Recommended)

The easiest way to get started is with the included setup script. It handles dependencies, FFmpeg detection, and walks you through creating your `.env` file interactively.

### 1. Clone the repository

```bash
git clone https://github.com/LeythonS/Migu.git
cd Migu
```

### 2. Run the setup script

**Windows**
```bash
python setup.py
```

**Linux / macOS**
```bash
python3 setup.py
```

The script will:
- Check your Python version
- Detect and install FFmpeg if missing (Linux/macOS)
- Install all Python dependencies from `requirements.txt`
- Walk you through filling in your `.env` file step by step
- Check for ngrok and guide you if it's not installed

---

## Manual Setup

Prefer to do it yourself? Follow the steps below.

### Requirements

- Python 3.10+
- FFmpeg
- A Spotify Developer account
- A Discord bot application
- ngrok (for OAuth callbacks)

### 1. Clone the repository

```bash
git clone https://github.com/LeythonS/Migu.git
cd Migu
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

**Windows** — Download from https://ffmpeg.org and add to PATH.

### 3. Install Python dependencies

```bash
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

Create a `.env` file in the project root:

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
| --- | --- | --- |
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
| `/support` | Support the developer & view links | Anyone |

---

## Notes

- Spotify limits development apps to **5 whitelisted users**. Each person who wants to use `/join` must have their Spotify email added under User Management in your Spotify Developer Dashboard.
- If you self-host this bot, you create your own Spotify app with your own set of 5 users — the limit is per app, not per bot.
- User tokens are kept in memory only and cleared when the session ends. No credentials are ever stored to disk.
- There is a natural delay of 2–5 seconds when switching tracks due to YouTube search and FFmpeg startup time.
- The bot seeks to your current position in the song when a new track is detected to stay as close to in sync as possible.

---

## Support

If you enjoy Migu, consider supporting development!

☕ **Ko-fi** — [ko-fi.com/saypi](https://ko-fi.com/saypi)
💻 **GitHub** — [github.com/LeythonS](https://github.com/LeythonS/)
💬 **Discord** — saypi.cyefi
