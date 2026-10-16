"""Monta dist/SotC-PS2-Launcher.zip para um amigo testar: o launcher + o código-fonte do port
(com as nossas correções). Nada do jogo entra: nem ISO, nem código gerado, nem sotc.exe,
nem programas de VU1 capturados, nem saves. Cada um compila a partir do próprio ISO.

    python -I 04_launcher/empacotar.py              (para amigos, sem medição)
    python -I 04_launcher/empacotar.py --medicao    (para as nossas máquinas: liga a medição)
"""

import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
PORT = WORKSPACE / "02_port"
DIST = WORKSPACE / "dist"
NAME = "SotC-PS2-Launcher"

# O que nunca pode ir no pacote (extensão ou pedaço do caminho). Os dois .exe do launcher são a exceção.
FORBIDDEN_EXT = {".iso", ".bin", ".elf", ".irx", ".xff", ".ps2", ".state", ".exe", ".pdb", ".dll", ".obj", ".lib"}
FORBIDDEN_PATH = ("02_port/build/", "02_port/Port/generated/", "03_vu1_capture/", "memcards/", "compilador/")
EXE_DIR = HERE / "exe"  # gerados pelo construir_exe.py
LAUNCHER_EXES = {"SotC Launcher.exe": EXE_DIR / "SotC Launcher.exe",
                 "04_launcher/sotc_tools.exe": EXE_DIR / "sotc_tools.exe"}

README = """SHADOW OF THE COLOSSUS (PS2) NO PC
==================================

Port nativo do SotC de PS2 (projeto do volstants, feito com o PS2Recomp). O código do jogo é
traduzido para C++ e compilado no SEU PC, a partir do SEU ISO. Este pacote não tem nada do jogo:
só o launcher e o código-fonte do port. Projeto de fãs, não oficial.

VOCÊ PRECISA DE
  - O ISO europeu (PAL) v1.00, código SCES-53326. A versão americana não funciona.
  - Windows 10/11 64-bit e um processador com AVX2 (quase todos de 2015 para cá).
  - 8 GB de RAM (16 GB é mais folgado), ~12 GB livres no disco e internet na primeira vez.

COMO USAR
  1. Extraia o zip numa pasta com caminho curto, fora do OneDrive (ex.: C:\\Jogos\\SotC).
  2. Coloque o seu ISO na pasta 01_iso (ou escolha ele no launcher).
  3. Abra "SotC Launcher.exe".
     Se o Windows mostrar "O Windows protegeu o computador", clique em "Mais informações" e
     "Executar assim mesmo": o launcher não é assinado digitalmente.
  4. Clique em "Preparar o jogo", escolha o modo e clique em "Começar". Na primeira vez o
     launcher baixa o compilador (~1,3 GB) e pede para aceitar a licença da Microsoft das
     bibliotecas do Visual C++. A preparação leva de 20 min a 1 h; dá para parar e continuar.
  5. Clique em "Jogar". O idioma do launcher troca no canto superior direito.

NAS PRIMEIRAS VEZES O JOGO FICA LENTO
  Os gráficos dependem de programas (VU1) que o jogo só envia enquanto roda. Com "Gravar
  gráficos novos" ligado (vem ligado): jogue, feche o jogo e clique em "Recompilar" quando o
  launcher pedir. Depois de 3 ou 4 rodadas o jogo fica perto de 60 FPS.

CONTROLES
  Controles de Xbox e PlayStation são detectados sozinhos. Teclado: WASD anda, o mouse gira
  a câmera e o resto fica na aba Controles. F11 = tela cheia.

DEU PROBLEMA?
  Mande os arquivos preparacao.log e ultima_sessao.log da pasta 04_launcher.
MEDICAO
IMPORTANTE
  Não compartilhe a pasta 02_port\\build depois de compilar: ela contém o jogo traduzido.
  Licença do código: GPL-3.0 (02_port\\LICENSE). O código do launcher está em 04_launcher.
"""


README_EN = """SHADOW OF THE COLOSSUS (PS2) ON PC
==================================

Native port of the PS2 Shadow of the Colossus (by volstants, built with PS2Recomp). The game code
is translated to C++ and built on YOUR PC, from YOUR ISO. This package contains nothing from the
game: only the launcher and the port's source code. Unofficial fan project.

YOU NEED
  - The European (PAL) v1.00 ISO, SCES-53326. The US version does not work.
  - Windows 10/11 64-bit and a CPU with AVX2 (almost every CPU since 2015).
  - 8 GB of RAM (16 GB is more comfortable), ~12 GB free and internet the first time.

HOW TO USE
  1. Extract the zip to a short path outside OneDrive (e.g. C:\\Games\\SotC).
  2. Put your ISO in the 01_iso folder (or pick it in the launcher).
  3. Open "SotC Launcher.exe". If Windows says "Windows protected your PC", click "More info"
     and "Run anyway": the launcher is not digitally signed.
  4. Click "Set up the game", choose a mode and click "Start". The first time it downloads the
     compiler (~1.3 GB) and asks you to accept Microsoft's license for the Visual C++ libraries.
     Setup takes 20 min to 1 h; you can stop and resume.
  5. Click "Play". The launcher language can be changed in the top-right corner.

THE GAME IS SLOW THE FIRST FEW TIMES
  The graphics depend on programs (VU1) the game only sends while running. With "Record new
  graphics" on (default): play, close the game and click "Rebuild" when the launcher asks.
  After 3 or 4 rounds the game runs close to 60 FPS.

SOMETHING WENT WRONG?
  Send preparacao.log and ultima_sessao.log from the 04_launcher folder.

IMPORTANT
  Do not share the 02_port\\build folder after building: it contains the translated game.
  Code license: GPL-3.0 (02_port\\LICENSE). The launcher source is in 04_launcher.
"""


# Só no pacote das nossas máquinas (--medicao): liga a medição do pipeline.
MEASURE_README = """
MEDIÇÃO (este pacote é só para as nossas máquinas)
  Cada preparação grava 04_launcher\\medicoes\\<data>.json: tempo de cada etapa, uso de
  memória e o modelo do processador, da placa de vídeo e do disco. Depois de preparar,
  traga essa pasta e o preparacao.log.

"""


def git_files(repo):
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [repo / p for p in out.decode("utf-8").split("\0") if p]


def collect():
    files = {}
    # O port como no GitHub (+ o submódulo PS2Recomp) com as nossas mudanças por cima.
    for f in git_files(PORT) + git_files(PORT / "External" / "PS2Recomp"):
        if f.is_file():
            files["02_port/" + f.relative_to(PORT).as_posix()] = f
    for extra in ("Tools/split_register_functions.py", "Tools/win/clang-cl.cmake"):
        files["02_port/" + extra] = PORT / extra
    for name in ("sotc_launcher.pyw", "pipeline.py", "compilador.py", "sotc_tools.py", "textos.py",
                 "construir_exe.py"):
        files["04_launcher/" + name] = HERE / name
    missing = [str(p) for p in LAUNCHER_EXES.values() if not p.is_file()]
    if missing:
        sys.exit("Faltam os executáveis (rode antes o construir_exe.py):\n  " + "\n  ".join(missing))
    files.update(LAUNCHER_EXES)
    return files


def check(files):
    bad = [arc for arc in files if arc not in LAUNCHER_EXES and
           (Path(arc).suffix.lower() in FORBIDDEN_EXT or any(part in arc for part in FORBIDDEN_PATH))]
    if bad:
        sys.exit("Recusado: arquivos que não podem ir no pacote:\n  " + "\n  ".join(bad[:30]))


def main():
    measure = "--medicao" in sys.argv[1:]
    files = collect()
    check(files)
    DIST.mkdir(exist_ok=True)
    target = DIST / (f"{NAME}-medicao.zip" if measure else f"{NAME}.zip")
    readme = README.replace("MEDICAO\n", MEASURE_README if measure else "\n")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arc, src in sorted(files.items()):
            z.write(src, f"{NAME}/{arc}")
        z.writestr(f"{NAME}/LEIA-ME.txt", readme.replace("\n", "\r\n").encode("utf-8-sig"))
        z.writestr(f"{NAME}/README.txt", README_EN.replace("\n", "\r\n").encode("utf-8-sig"))
        if measure:
            z.writestr(f"{NAME}/04_launcher/medir.txt", "Liga a medição do pipeline (pasta medicoes).\r\n")
        z.writestr(f"{NAME}/01_iso/COLOQUE O SEU ISO AQUI.txt", "SCES-53326 (PAL) v1.00\r\n")
        z.writestr(f"{NAME}/03_vu1_capture/LEIA-ME.txt",
                   "Os programas de VU1 gravados enquanto você joga ficam aqui (um .bin cada).\r\n")
    size = target.stat().st_size / 2**20
    print(f"{target}  ({len(files)} arquivos, {size:.1f} MB)")


if __name__ == "__main__":
    main()
