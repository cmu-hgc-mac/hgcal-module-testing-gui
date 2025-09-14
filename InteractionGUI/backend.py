import sys
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.responses import FileResponse
import os

app = FastAPI()
server_ref = {"server": None}  # 用 dict 存全局引用，避免作用域问题

# allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# events
@app.get("/")
def serve_frontend():
    return FileResponse(os.path.abspath("frontend.html"))

@app.post("/shutdown")
def shutdown():
    server = server_ref.get("server")
    if server:
        print(">>> Shutting down backend ...")
        server.should_exit = True # signal to stop the server
        return {"status": "success", "message": "Backend shutting down"}
    return {"status": "error", "message": "No server instance found"}
