import sys
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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
@app.post("/run_test")
def run_test():
    return {"status": "success", "message": "Test1 executed from backend"}

@app.post("/shutdown")
def shutdown():
    server = server_ref.get("server")
    if server:
        print(">>> Shutting down backend ...")
        server.should_exit = True
        return {"status": "success", "message": "Backend shutting down"}
    else:
        return {"status": "error", "message": "No server instance found"}
