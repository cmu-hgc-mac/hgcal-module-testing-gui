import sys
import re
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.responses import FileResponse

import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = FastAPI()
server_ref = {"server": None} 

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
    return FileResponse(os.path.abspath("InteractionGUI/frontend.html"))

@app.post("/shutdown")
def shutdown():
    server = server_ref.get("server")
    if server:
        print(">>> Shutting down backend ...")
        server.should_exit = True # signal to stop the server
        return {"status": "success", "message": "Backend shutting down"}
    return {"status": "error", "message": "No server instance found"}



def check_valid_module_serial(moduleserial):
    """Check if the module or hexaboard serial is valid.
    """

    # Module: 320-[M][Resolution]-[Shape][Thickness][BP_Material][ROC]-[MAC]-[NNNN]
    pattern_module = r"^320-(ML|MH)-([FTBLR5])([123])([WTPC])([A-Z0-9])-([A-Z0-9]{2})-(\d{4})$"
    # Hxb: 320-[X][Resolution]-[Shape][Version][ROC]-[PCB][Assembly]-[NNNNN]
    pattern_hxb    = r"^320-(XL|XH)-([FTBLR5])([0-4])([A-Z0-9])-([A-Z])([A-Z])-\d{5}$"

    match_module = re.match(pattern_module, moduleserial)
    match_hxb = re.match(pattern_hxb, moduleserial)

    # Initialize the output result
    module_type = 'invalid'
    valid = False

    # -------- MODULE CHECK --------
    if match_module:
        major_type = match_module.group(1)  # ML or MH
        shape = match_module.group(2)
        thickness = match_module.group(3)
        material = match_module.group(4)
        roc_code = match_module.group(5)

        valid = True    # temp-assert it to be valid

        # HD modules (MH) cannot have shape = '5'
        if major_type == 'MH' and shape == '5':
            valid = False

        # Valid thickness
        valid_thickness = {
            'ML': ['2', '3'],  # 200/300 µm
            'MH': ['1', '2'],  # 120/200 µm
        }
        if thickness not in valid_thickness[major_type]:
            valid = False

        # Valid ROC code
        valid_roc_codes = ['X', '1', '2', '3', '4', 'C', 'B']
        if roc_code not in valid_roc_codes:
            valid = False

        if valid:
            module_type = 'live'


    # -------- HXB CHECK --------
    elif match_hxb:
        major_type = match_hxb.group(1)  # XL or XH
        shape = match_hxb.group(2)
        roc_code = match_hxb.group(4)

        valid = True    # temp-assert it to be valid

        # HD modules (XH) cannot have shape = '5'
        if major_type == 'XH' and shape == '5':
            valid = False
        
        # Valid ROC code
        valid_roc_codes = ['X', '1', '2', '3', '4', 'C', 'B']
        if roc_code not in valid_roc_codes:
            valid = False

        if valid:
            module_type = 'hxb'

    return module_type, valid