# launch_gradio_ui.py
"""
Launch the Computer Interface Gradio UI (host mode).
Make sure `python -m computer_server` is already running.
"""

# You can load environment variables here if you have a .env file:
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Import the Gradio UI launcher
try:
    from computer.ui.gradio.app import create_gradio_ui
except ImportError:
    try:
        # Some versions package it differently
        from computer.ui.app import create_gradio_ui
    except ImportError as e:
        raise RuntimeError(
            "Could not import Gradio UI. Ensure you installed the extras: \n\n"
            "    pip install 'cua-computer[ui]'"
        ) from e

if __name__ == "__main__":
    print("Launching Computer Interface Gradio UI…")
    app = create_gradio_ui()
    app.launch(
        share=True,
        server_name="0.0.0.0",  # use "127.0.0.1" if you only want local
        server_port=7860,
    )
