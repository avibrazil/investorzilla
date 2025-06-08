import os
import subprocess
import sys
import time
import importlib
import webbrowser
import investorzilla

def main():
    # Investorzilla deserves its own port
    port=8601

    # Getting path to python executable (full path of deployed python on Windows)
    executable = sys.executable

    # Running streamlit server in a subprocess and writing to log file
    proc = subprocess.Popen(
        [
            executable,
            "-m",
            "streamlit",
            "run",
            str(importlib.resources.files(investorzilla) / 'streamlit_ui.py'),
            "--server.enableWebsocketCompression=true",

            # For reverse proxy
            "--server.enableCORS=false",

            f"--server.port={port}",

            # The following option appears to be necessary to correctly start
            # the streamlit server, but it should start without it. More
            # investigations should be carried out.
            "--server.headless=true",
            "--global.developmentMode=false",
        ],
    )

    # Force the opening (does not open automatically) of the browser tab after a brief delay to let
    # the streamlit server start.
    time.sleep(2)
    webbrowser.open(f"http://localhost:{port}")

    proc.wait()


if "__main__" in __name__:
    main()
