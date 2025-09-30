# streamlit_teams_coords.py
import streamlit as st
import asyncio
import json
from pathlib import Path
import time
import traceback

try:
    from computer import Computer
except Exception as e:
    Computer = None
    IMPORT_ERROR = str(e)
else:
    IMPORT_ERROR = None

COORD_FILE = Path("teams_coords.json")

st.set_page_config(page_title="Teams Automation (CUA)", layout="centered")
st.title("CUA Teams Automation — Coordinate Based")

if IMPORT_ERROR:
    st.error("Could not import Computer SDK.")
    st.code("pip install cua-computer\n\nError:\n" + IMPORT_ERROR)
    st.stop()

# ---------------- Utilities ----------------
def load_coords():
    if COORD_FILE.exists():
        return json.loads(COORD_FILE.read_text(encoding="utf-8"))
    return {}

def save_coords(c):
    COORD_FILE.write_text(json.dumps(c, indent=2), encoding="utf-8")

# ---------------- Session State ----------------
if "computer" not in st.session_state:
    st.session_state.computer = None
if "connected" not in st.session_state:
    st.session_state.connected = False

# ---------------- Connection ----------------
async def _async_connect():
    comp = Computer(use_host_computer_server=True)
    await comp.run()
    return comp

def connect_computer():
    try:
        comp = asyncio.run(_async_connect())
        st.session_state.computer = comp
        st.session_state.connected = True
        st.success("Connected to Computer server.")
    except Exception as e:
        st.error(f"Failed to connect: {e}")
        st.exception(traceback.format_exc())

# ---------------- Calibration ----------------
TARGETS = [
    ("search_box", "Search box at top of Teams"),
    ("first_result", "First search result (optional)"),
    ("message_box", "Message input area"),
]

async def _capture_cursor(comp):
    pos = await comp.interface.get_cursor_position()
    if isinstance(pos, dict):
        return {"x": int(pos["x"]), "y": int(pos["y"])}
    else:
        return {"x": int(getattr(pos, "x")), "y": int(getattr(pos, "y"))}

# ---------------- Send Sequence ----------------
async def _async_send(comp, coords, recipient, message):
    # Click search box
    sx, sy = coords["search_box"]["x"], coords["search_box"]["y"]
    await comp.interface.left_click(sx, sy)
    await comp.interface.hotkey("ctrl", "a")
    await comp.interface.press_key("backspace")
    await asyncio.sleep(0.2)
    await comp.interface.type_text(recipient, delay=0.01)
    await asyncio.sleep(0.5)
    await comp.interface.press_key("enter")
    await asyncio.sleep(1.0)

    # Optional: click first result
    if "first_result" in coords:
        fx, fy = coords["first_result"]["x"], coords["first_result"]["y"]
        await comp.interface.left_click(fx, fy)
        await asyncio.sleep(0.5)

    # Click message box
    mx, my = coords["message_box"]["x"], coords["message_box"]["y"]
    await comp.interface.left_click(mx, my)
    await asyncio.sleep(0.2)

    # Type and send message
    await comp.interface.type_text(message, delay=0.01)
    await asyncio.sleep(0.2)
    await comp.interface.press_key("enter")
    await asyncio.sleep(0.5)

def send_message(coords, recipient, message):
    comp = st.session_state.computer
    try:
        asyncio.run(_async_send(comp, coords, recipient, message))
        st.success("Message sent (best-effort).")
    except Exception as e:
        st.error(f"Failed to send: {e}")
        st.exception(traceback.format_exc())

# ---------------- UI ----------------
st.subheader("1) Connect")
if st.button("Connect to Computer server"):
    connect_computer()

st.markdown("---")
st.subheader("2) Calibrate coordinates")

coords = load_coords()
st.json(coords if coords else {"notice": "No coords yet."})

if st.session_state.connected:
    for key, desc in TARGETS:
        if st.button(f"Capture {key} ({desc})"):
            st.info("Move mouse over the target. Capturing in 3 seconds...")
            time.sleep(3)
            try:
                pos = asyncio.run(_capture_cursor(st.session_state.computer))
                coords[key] = pos
                save_coords(coords)
                st.success(f"Captured {key}: {pos}")
                st.rerun()
            except Exception as e:
                st.error(f"Capture failed: {e}")
                st.exception(traceback.format_exc())

if st.button("Clear coordinates"):
    if COORD_FILE.exists():
        COORD_FILE.unlink()
    st.success("Cleared.")
    st.rerun()

st.markdown("---")
st.subheader("3) Send message")

recipient = st.text_input("Recipient (Teams search):")
message = st.text_area("Message:", value="Hello from CUA automation!")

if st.button("Send message"):
    if not st.session_state.connected:
        st.error("Not connected.")
    elif not coords:
        st.error("No coordinates. Calibrate first.")
    elif not recipient.strip():
        st.error("Enter a recipient.")
    else:
        st.info("Make sure Teams is open and visible in the same position as calibration.")
        send_message(coords, recipient.strip(), message.strip())
