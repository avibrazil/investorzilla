import os
import subprocess
import sys
import time
import importlib
import webbrowser
import investorzilla

def main():
    # Getting path to python executable (full path of deployed python on Windows)
    executable = sys.executable

    print('acabarei')

    # Running streamlit server in a subprocess and writing to log file
    proc = subprocess.Popen(
        [
            executable,
            "-m",
            "streamlit",
            "run",
            str(importlib.resources.files(investorzilla) / 'investorzilla_ui.py'),
            # The following option appears to be necessary to correctly start the streamlit server,
            # but it should start without it. More investigations should be carried out.
            "--server.headless=true",
            "--global.developmentMode=false",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    proc.stdin.close()

    # Force the opening (does not open automatically) of the browser tab after a brief delay to let
    # the streamlit server start.
    time.sleep(3)
    webbrowser.open("http://localhost:8501")

    while True:
        s = proc.stdout.read()
        if not s:
            break
        print(s, end="")

    proc.wait()
    print('acabei')

print(f'Meu nome: {__name__}')

if "__main__" in __name__:
    print('vou rodar main')
    main()
# else:
#     print('antes do streamlit')
#     if streamlit.runtime.scriptrunner.get_script_run_ctx():
#         print('vou rodar 1')
#         StreamlitInvestorzillaApp(refresh=False)

