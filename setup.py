#!/usr/bin/env python3

# ──────────────────────────────────────────────
#  Migu Setup Script
#  Developed by Saypi
#  GitHub  : https://github.com/LeythonS/
#  Ko-fi   : https://ko-fi.com/saypi
#  Discord : saypi.cyefi
# ──────────────────────────────────────────────

import os
import sys
import platform
import subprocess
import shutil

# ── Colors (disabled on Windows if no ANSI support) ──
USE_COLOR = platform.system() != "Windows" or os.environ.get("TERM")

def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def green(t):  return c(t, "92")
def yellow(t): return c(t, "93")
def red(t):    return c(t, "91")
def cyan(t):   return c(t, "96")
def bold(t):   return c(t, "1")

# ── Helpers ──────────────────────────────────

def header():
    print()
    print(cyan("╔══════════════════════════════════════╗"))
    print(cyan("║") + bold("           Migu Setup Script          ") + cyan("║"))
    print(cyan("║") + "      github.com/LeythonS/Migu        " + cyan("║"))
    print(cyan("╚══════════════════════════════════════╝"))
    print()

def step(n, total, msg):
    print(f"\n{cyan(f'[{n}/{total}]')} {bold(msg)}")

def ok(msg):
    print(f"  {green('✓')} {msg}")

def warn(msg):
    print(f"  {yellow('!')} {msg}")

def fail(msg):
    print(f"  {red('✗')} {msg}")

def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {cyan('→')} {prompt}{suffix}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    return val if val else default

def ask_required(prompt):
    while True:
        val = ask(prompt)
        if val:
            return val
        warn("This field is required.")

def confirm(prompt):
    try:
        val = input(f"  {cyan('→')} {prompt} [y/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    return val in ("y", "yes")

def run(cmd, check=True, capture=False):
    return subprocess.run(
        cmd, shell=True, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None
    )

def command_exists(cmd):
    return shutil.which(cmd) is not None

# ── Checks ───────────────────────────────────

TOTAL_STEPS = 6

def check_python():
    step(1, TOTAL_STEPS, "Checking Python version...")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        fail(f"Python 3.10+ required. You have {major}.{minor}.")
        fail("Download it from https://www.python.org/downloads/")
        sys.exit(1)
    ok(f"Python {major}.{minor} detected.")

def check_ffmpeg():
    step(2, TOTAL_STEPS, "Checking FFmpeg...")
    if command_exists("ffmpeg"):
        ok("FFmpeg is already installed.")
        return

    warn("FFmpeg not found.")
    system = platform.system()

    if system == "Windows":
        print(f"\n  {yellow('Please install FFmpeg manually:')}")
        print("  1. Download from https://ffmpeg.org/download.html")
        print("  2. Extract and add the bin/ folder to your system PATH")
        print("  3. Re-run this script after installing.")
        if not confirm("Continue anyway (FFmpeg is required to run the bot)?"):
            sys.exit(0)

    elif system == "Darwin":
        if command_exists("brew"):
            print("  Installing FFmpeg via Homebrew...")
            run("brew install ffmpeg")
            ok("FFmpeg installed.")
        else:
            warn("Homebrew not found. Install FFmpeg manually: brew install ffmpeg")
            warn("Or install Homebrew first: https://brew.sh")

    elif system == "Linux":
        if command_exists("apt"):
            print("  Installing FFmpeg via apt...")
            run("sudo apt install -y ffmpeg")
            ok("FFmpeg installed.")
        elif command_exists("pacman"):
            print("  Installing FFmpeg via pacman...")
            run("sudo pacman -S --noconfirm ffmpeg")
            ok("FFmpeg installed.")
        else:
            warn("Could not auto-install FFmpeg. Install it manually for your distro.")

def install_dependencies():
    step(3, TOTAL_STEPS, "Installing Python dependencies...")
    if not os.path.exists("requirements.txt"):
        fail("requirements.txt not found. Make sure you're running this from the Migu folder.")
        sys.exit(1)

    system = platform.system()
    pip_cmd = "pip" if command_exists("pip") else "pip3"

    # Use --break-system-packages on Linux to avoid venv requirement errors
    extra = " --break-system-packages" if system == "Linux" else ""

    result = run(f"{pip_cmd} install -r requirements.txt{extra}", check=False)
    if result.returncode != 0:
        fail("Failed to install dependencies. Try running manually:")
        fail(f"  {pip_cmd} install -r requirements.txt")
        sys.exit(1)
    ok("All dependencies installed.")

# ── .env Setup ───────────────────────────────

def setup_env():
    step(4, TOTAL_STEPS, "Setting up .env file...")

    existing = {}
    if os.path.exists(".env"):
        warn(".env already exists.")
        if not confirm("Overwrite it with new values?"):
            ok("Keeping existing .env.")
            return
        # Read existing values to use as defaults
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    print()
    print(f"  {bold('Discord Bot Token')}")
    print(f"  Get it from: https://discord.com/developers/applications → Bot → Token")
    discord_token = ask_required("DISCORD_TOKEN")

    print()
    print(f"  {bold('Your Discord User ID')} (for admin commands)")
    print(f"  Enable Developer Mode in Discord settings → right-click your name → Copy User ID")
    admin_id = ask_required("ADMIN_ID")

    print()
    print(f"  {bold('Text channel name')} where Now Playing messages will appear")
    text_channel = ask("TEXT_CHANNEL_NAME", default=existing.get("TEXT_CHANNEL_NAME", "now-playing"))

    print()
    print(f"  {bold('Spotify Developer App')}")
    print(f"  Create one at: https://developer.spotify.com/dashboard")
    spotify_client_id = ask_required("SPOTIFY_CLIENT_ID")
    spotify_client_secret = ask_required("SPOTIFY_CLIENT_SECRET")

    print()
    print(f"  {bold('Spotify Redirect URI')} (your ngrok callback URL)")
    print(f"  Format: https://your-domain.ngrok-free.app/callback")
    spotify_redirect_uri = ask_required("SPOTIFY_REDIRECT_URI")

    env_content = f"""# Migu Environment Variables
# Generated by setup.py — https://github.com/LeythonS/Migu

DISCORD_TOKEN={discord_token}
ADMIN_ID={admin_id}
TEXT_CHANNEL_NAME={text_channel}
SPOTIFY_CLIENT_ID={spotify_client_id}
SPOTIFY_CLIENT_SECRET={spotify_client_secret}
SPOTIFY_REDIRECT_URI={spotify_redirect_uri}
"""

    with open(".env", "w") as f:
        f.write(env_content)

    ok(".env file created successfully.")

# ── ngrok Check ──────────────────────────────

def check_ngrok():
    step(5, TOTAL_STEPS, "Checking ngrok...")
    if command_exists("ngrok"):
        ok("ngrok is already installed.")
        return

    warn("ngrok not found.")
    print(f"\n  {bold('To install ngrok:')}")
    print("  1. Sign up at https://ngrok.com")
    print("  2. Download from https://ngrok.com/download")
    print("  3. Get your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken")
    print("  4. Claim a free static domain: https://dashboard.ngrok.com/cloud-edge/domains")
    print("  5. Run: ngrok config add-authtoken YOUR_TOKEN")
    print()
    warn("ngrok is required for Spotify OAuth to work.")

# ── Summary ──────────────────────────────────

def summary():
    step(6, TOTAL_STEPS, "Setup complete!")
    print()
    print(f"  {bold('To run Migu:')}")
    print()

    system = platform.system()
    if system == "Windows":
        print(f"  {cyan('Step 1:')} Open a terminal and start ngrok:")
        print(f"          ngrok http --url=your-domain.ngrok-free.app 8888")
        print()
        print(f"  {cyan('Step 2:')} Open another terminal and run the bot:")
        print(f"          python migu.py")
    else:
        print(f"  {cyan('Step 1:')} Start ngrok in a separate terminal:")
        print(f"          ngrok http --url=your-domain.ngrok-free.app 8888")
        print()
        print(f"  {cyan('Step 2:')} Run the bot:")
        print(f"          python3 migu.py")

    print()
    print(f"  {bold('Need help?')}")
    print(f"  ☕ Ko-fi   : https://ko-fi.com/saypi")
    print(f"  💻 GitHub  : https://github.com/LeythonS/Migu")
    print(f"  💬 Discord : saypi.cyefi")
    print()
    print(cyan("══════════════════════════════════════════"))
    print()

# ── Entry Point ──────────────────────────────

def main():
    header()
    print(f"  This script will set up everything needed to run Migu.")
    print(f"  {yellow('Make sure you are running this from the Migu project folder.')}")

    print()
    if not confirm("Ready to begin?"):
        print("\n  Cancelled. Run this script again whenever you're ready.")
        sys.exit(0)

    check_python()
    check_ffmpeg()
    install_dependencies()
    setup_env()
    check_ngrok()
    summary()

if __name__ == "__main__":
    main()