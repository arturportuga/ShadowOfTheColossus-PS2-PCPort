"""Executável auxiliar do launcher (congelado com o PyInstaller em sotc_tools.exe): faz o papel do Python para
quem não tem Python instalado.

    sotc_tools.exe pipeline [argumentos]          roda o pipeline.py (preparar o jogo)
    sotc_tools.exe [-I] [-u] script.py [args]     roda um script .py, como o python faria

O pipeline chama os scripts do port (Tools/generate.py, que chama sotc_link.py, split_register_functions.py
e verify_reloc_sites.py) com sys.executable; congelado, sys.executable é este .exe, que cai no segundo caso.
"""

import runpy
import sys
from pathlib import Path

# Módulos da biblioteca padrão que os scripts do port usam. O PyInstaller só embute o que vê importado aqui.
import argparse, bisect, csv, glob, hashlib, json, os, re, shutil, struct, subprocess  # noqa: E401,F401


def main():
    args = sys.argv[1:]
    while args and args[0] in ("-I", "-u", "-B", "-E", "-s"):
        args.pop(0)
    if args and args[0] == "pipeline":
        sys.argv = ["pipeline.py", *args[1:]]
        import pipeline
        return pipeline.main()
    if args and args[0].lower().endswith(".py"):
        script = Path(args[0]).resolve()
        sys.argv = [str(script), *args[1:]]
        sys.path.insert(0, str(script.parent))  # os scripts do port importam os vizinhos (iso9660, xff)
        runpy.run_path(str(script), run_name="__main__")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
