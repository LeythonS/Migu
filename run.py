#!/usr/bin/env python3

import os
import sys
import time
import platform
import subprocess
import threading
import shutil
import signal

USE_COLOR = platform.system() != "Windows" or os.environ.get("TERM")

def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def green(t):  return c(t, "92")
def yellow(t): return c(t, "93")
def red(t):    return c(t, "91")
def cyan(t):   return c(t, "96")
def bold(t):   return c(t, "1")

def ok(msg):   print(f"  {green('✓')} {msg}")
def warn(msg): print(f"  {yellow('!')} {msg}")
def fail(msg): print(f"  {red('✗')} {msg}")
def info(msg): print(f"  {cyan('→')} {msg}")

def read_env():
    env = {}
    if not os.path.exists(".env"):
        return env
    with open(".env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

def stream_output(proc, prefix, color_fn):
    """Stream subprocess output to terminal with a colored prefix."""
    for line in iter(proc.stdout.readline, b""):
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            print(f"{color_fn(f'[{prefix}]')} {text}")
    proc.stdout.close()

def check_env(env):
    required = [
        "DISCORD_TOKEN",
        "ADMIN_ID",
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI",
    ]
    missing = [k for k in required if not env.get(k)]
    if missing:
        fail("Missing required .env values: " + ", ".join(missing))
        fail("Run setup.py first to configure your environment.")
        sys.exit(1)
    ok(".env loaded successfully.")

def check_files():
    if not os.path.exists("migu.py"):
        fail("migu.py not found. Make sure you're running this from the Migu folder.")
        sys.exit(1)
    if not os.path.exists(".env"):
        fail(".env not found. Run setup.py first.")
        sys.exit(1)
    ok("All required files found.")

def check_ngrok():
    if not shutil.which("ngrok"):
        fail("ngrok is not installed or not in PATH.")
        fail("Download it from https://ngrok.com/download and add it to your PATH.")
        sys.exit(1)
    ok("ngrok found.")

def check_python_deps():
    try:
        import discord
        import spotipy
        import yt_dlp
        import dotenv
        import aiohttp
        ok("Python dependencies are installed.")
    except ImportError as e:
        fail(f"Missing dependency: {e}")
        fail("Run: pip install -r requirements.txt")
        sys.exit(1)

def get_ngrok_domain(env):
    uri = env.get("SPOTIFY_REDIRECT_URI", "")
    if uri.startswith("https://"):
        domain = uri.replace("https://", "").split("/")[0]
        return domain
    return None

def wait_for_ngrok(timeout=15):
    """Poll ngrok local API until the tunnel is up."""
    import urllib.request
    import json
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=2) as r:
                data = json.loads(r.read())
                tunnels = data.get("tunnels", [])
                if tunnels:
                    return tunnels[0].get("public_url")
        except Exception:
            pass
        time.sleep(1)
    return None

def start_ngrok(domain):
    cmd = f"ngrok http --url={domain} 8888"
    info(f"Starting ngrok tunnel → {domain}")
    proc = subprocess.Popen(
        cmd, shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    t = threading.Thread(target=stream_output, args=(proc, "ngrok", yellow), daemon=True)
    t.start()
    return proc

def start_bot():
    python = sys.executable
    info("Starting Migu bot...")
    proc = subprocess.Popen(
        [python, "migu.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    t = threading.Thread(target=stream_output, args=(proc, "migu", cyan), daemon=True)
    t.start()
    return proc

ngrok_proc = None
bot_proc = None

def shutdown(sig=None, frame=None):
    print()
    print(yellow("  Shutting down Migu..."))
    if bot_proc and bot_proc.poll() is None:
        bot_proc.terminate()
        ok("Bot stopped.")
    if ngrok_proc and ngrok_proc.poll() is None:
        ngrok_proc.terminate()
        ok("ngrok stopped.")
    print()
    sys.exit(0)

def main():
    global ngrok_proc, bot_proc

    print()
    print(cyan("╔══════════════════════════════════════╗"))
    print(cyan("║") + bold("            Migu Launcher              ") + cyan("║"))
    print(cyan("║") + "      github.com/LeythonS/Migu         " + cyan("║"))
    print(cyan("╚══════════════════════════════════════╝"))
    print()

    signal.signal(signal.SIGINT, shutdown)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, shutdown)

    print(bold("  Pre-flight checks..."))
    env = read_env()
    check_files()
    check_env(env)
    check_ngrok()
    check_python_deps()

    domain = get_ngrok_domain(env)
    if not domain:
        fail("Could not parse ngrok domain from SPOTIFY_REDIRECT_URI in .env.")
        fail("Make sure it looks like: https://your-domain.ngrok-free.app/callback")
        sys.exit(1)

    print()
    print(bold("  Starting services..."))
    print()

    ngrok_proc = start_ngrok(domain)
    info("Waiting for ngrok tunnel to come up...")
    tunnel_url = wait_for_ngrok(timeout=20)
    if tunnel_url:
        ok(f"ngrok tunnel active → {tunnel_url}")
    else:
        warn("Could not confirm ngrok tunnel via API — continuing anyway.")
        warn("If the bot fails to authorize Spotify, check your ngrok setup.")

    print()

    bot_proc = start_bot()

    print()
    print(green("  ✓ Migu is running! Press Ctrl+C to stop."))
    print()

    while True:
        time.sleep(2)

        if bot_proc.poll() is not None:
            fail("Bot process exited unexpectedly.")
            warn("Check the output above for errors.")
            shutdown()

        if ngrok_proc.poll() is not None:
            fail("ngrok process exited unexpectedly.")
            warn("The Spotify OAuth callback may stop working.")
            warn("Restart run.py to bring ngrok back up.")

if __name__ == "__main__":
    main()