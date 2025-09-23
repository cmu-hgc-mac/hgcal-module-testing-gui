""" This file is for starting the backend server.
"""

import uvicorn
import threading
import webbrowser
import time
from backend import app,server_ref

#path
front_path = "InteractionGUI/frontend.html"
backend_url = "http://127.0.0.1:8000"

def start_backend():
    # create Config 和 Server manually
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)

    # save to global reference in backend.py
    server_ref["server"] = server

    # run server.run() in a thread
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    print(f">>> Backend started at {backend_url}")

if __name__ == "__main__":
    start_backend()

    # not using frontend because for unknown reason it fails to automatically pop up sometimes
    webbrowser.open_new(backend_url)
    print(">>> Frontend opened in browser")

    # Keep the main thread alive to keep the backend running
    try:
        while True:
            time.sleep(1)
            # shutdown if backend asked to stop ("Close GUI" clicked)
            if server_ref["server"] and server_ref["server"].should_exit:
                    print(">>> Main loop exiting because backend asked to stop")
                    break
    except KeyboardInterrupt:
        print("Stopped manually")
