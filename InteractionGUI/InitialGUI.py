""" This file is for starting the backend server.
"""

import uvicorn
import threading
import webbrowser
import time
from backend import app,server_ref

#path
front_path = "InteractionGUI/frontend.html"

def start_backend():
    global server
    config = uvicorn.Config("backend:app", host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

def start_backend():
    # 手动创建 Config 和 Server
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)

    # 保存到 backend.py 里的全局引用
    server_ref["server"] = server

    # 在线程里跑 server.run()
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    print(">>> Backend started at http://127.0.0.1:8000")

if __name__ == "__main__":
    start_backend()

    webbrowser.open(front_path)

    # Keep the main thread alive to keep the backend running
    try:
        while True:
            time.sleep(1)
            if server_ref["server"] and server_ref["server"].should_exit:
                    print(">>> Main loop exiting because backend asked to stop")
                    break
    except KeyboardInterrupt:
        print("Stopped manually")
