
import subprocess, sys, webbrowser, time, shutil, os

def ensure_playwright():
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:
        pass
    # Make sure chromium is available
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        print("Warning: couldn't auto-install Playwright Chromium:", e)

def main():
    ensure_playwright()
    app_path = os.path.join(os.path.dirname(__file__), "app_streamlit.py")
    if not os.path.exists(app_path):
        print("Eroare: nu găsesc app_streamlit.py lângă executabil.")
        sys.exit(1)

    # Start streamlit server
    port = "8501"
    cmd = [sys.executable, "-m", "streamlit", "run", app_path, "--server.port", port, "--server.headless", "true"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # Try to open browser
    url = f"http://localhost:{port}"
    for _ in range(30):
        time.sleep(0.3)
        try:
            webbrowser.open(url)
            break
        except Exception:
            time.sleep(0.2)

    # Pipe server output (basic)
    try:
        for line in iter(proc.stdout.readline, b""):
            sys.stdout.write(line.decode(errors="ignore"))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
