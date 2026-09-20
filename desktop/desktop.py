import os
import threading
import time
import webview

from app import app

PORT = 5050

def start_server():
    app.run(
        host=os.environ.get("SAZGAN_HOST", "0.0.0.0"),
        port=PORT,
        debug=False,
        use_reloader=False,
    )

def main():
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(1.5)

    webview.create_window(
        title="Sazgan",
        url=f"http://127.0.0.1:{PORT}",
        width=1440,
        height=900,
        min_size=(1000, 700),
        resizable=True,
    )
    webview.start()

if __name__ == "__main__":
    main()
