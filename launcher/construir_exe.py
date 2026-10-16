"""Gera os executáveis do launcher com o PyInstaller (só na máquina de desenvolvimento; quem usa o pacote não
precisa de Python):

    04_launcher/exe/SotC Launcher.exe   a janela (vai na raiz do pacote)
    04_launcher/exe/sotc_tools.exe      faz o papel do Python para o pipeline e os scripts do port

    python -m pip install pyinstaller
    python -I 04_launcher/construir_exe.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICON = HERE.parent / "02_port" / "game_icon.ico"
OUT = HERE / "exe"


def build(script, name, windowed):
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
               "--windowed" if windowed else "--console", "--name", name,
               "--distpath", str(OUT), "--workpath", tmp, "--specpath", tmp,
               "--paths", str(HERE), str(HERE / script)]
        if ICON.is_file():
            cmd[3:3] = ["--icon", str(ICON)]
        subprocess.run(cmd, check=True, cwd=HERE)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    build("sotc_launcher.pyw", "SotC Launcher", windowed=True)
    build("sotc_tools.py", "sotc_tools", windowed=False)
    for exe in sorted(OUT.glob("*.exe")):
        print(f"{exe}  ({exe.stat().st_size / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
