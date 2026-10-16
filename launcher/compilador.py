"""Monta o compilador portátil, sem Visual Studio, numa pasta só: LLVM (clang-cl, lld-link, llvm-lib,
llvm-rc, llvm-mt), CMake e Ninja dos lançamentos oficiais, e as bibliotecas C/C++ do MSVC + o Windows SDK
baixados pelo xwin direto dos servidores da Microsoft (cada um na máquina da própria pessoa: nada da
Microsoft vai no nosso pacote). Nada é instalado no Windows e não precisa de administrador.

Baixa ~1,3 GB na primeira vez; a pasta final fica com ~1,1 GB.
"""

import hashlib
import json
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
GH = "https://github.com"
LLVM_VERSION = "23.1.3"
DOWNLOADS = {
    "llvm": (f"{GH}/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/"
             f"clang+llvm-{LLVM_VERSION}-x86_64-pc-windows-msvc.tar.zst",
             "7e69dc07a4536b79ff24a651a2611990bf8eaab17ea560f1092707c4f31ba01d"),
    "xwin": (f"{GH}/Jake-Shadle/xwin/releases/download/0.10.0/xwin-0.10.0-x86_64-pc-windows-msvc.tar.gz",
             "96e83665ef5c1406aabd0be603a8d08e67e604f36fda630b6807ee948a614e26"),
    "cmake": (f"{GH}/Kitware/CMake/releases/download/v4.4.4/cmake-4.4.4-windows-x86_64.zip",
              "bace36e94b31c68ab6fa295f26dfa11219e0701cf7c94b0284a7d1cb13dac536"),
    "ninja": (f"{GH}/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip",
              "07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65"),
    # Só se o Python não tiver o módulo zstd (antes do 3.14).
    "zstd": (f"{GH}/facebook/zstd/releases/download/v1.5.7/zstd-v1.5.7-win64.zip",
             "acb4e8111511749dc7a3ebedca9b04190e37a17afeb73f55d4425dbf0b90fad9"),
}
# Bibliotecas que o CMake baixaria com o Git (FetchContent). Baixamos o .zip da mesma versão direto do GitHub
# e passamos FETCHCONTENT_SOURCE_DIR_<NOME>: assim a pessoa não precisa ter o Git. As outras bibliotecas do
# PS2Recomp (imgui, SDL2...) são do estúdio/analisador, que a pipeline desliga.
DEPS = {
    "ELFIO": f"{GH}/serge1/ELFIO/archive/refs/tags/Release_3.12.zip",
    "FMT": f"{GH}/fmtlib/fmt/archive/refs/tags/12.1.0.zip",
    "LIBDWARF": f"{GH}/davea42/libdwarf-code/archive/refs/tags/v2.2.0.zip",
    "RABBITIZER": f"{GH}/Decompollaborate/rabbitizer/archive/refs/tags/1.14.3.zip",
    "TOML11": f"{GH}/ToruNiina/toml11/archive/refs/tags/v4.4.0.zip",
    "RAYLIB": f"{GH}/raysan5/raylib/archive/refs/tags/5.5.zip",
}
# Do LLVM (4 GB extraído) só precisamos disto (~350 MB).
LLVM_BIN = {"clang-cl.exe", "lld-link.exe", "llvm-lib.exe", "llvm-rc.exe", "llvm-mt.exe"}
VERSION_KEY = json.dumps({k: v[1] for k, v in DOWNLOADS.items() if k != "zstd"}, sort_keys=True)
LICENSE_URL = "https://visualstudio.microsoft.com/license-terms/"


class Erro(Exception):
    pass


def paths(root):
    root = Path(root)
    return {"llvm_bin": root / "llvm" / "bin", "sysroot": root / "winsysroot",
            "cmake": root / "cmake" / "bin" / "cmake.exe", "ninja": root / "ninja" / "ninja.exe"}


def ready(root):
    try:
        return (Path(root) / "pronto.json").read_text(encoding="utf-8") == VERSION_KEY
    except OSError:
        return False


def download(name, dest, log, url=None, sha=None):
    if url is None:
        url, sha = DOWNLOADS[name]
    for attempt in range(3):
        try:
            h = hashlib.sha256()
            req = urllib.request.Request(url, headers={"User-Agent": "sotc-launcher"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done, shown = 0, -1
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    pct = done * 100 // total if total else -1
                    if total and pct // 10 != shown:
                        shown = pct // 10
                        log(f"  {name}: {done / 2**20:.0f} de {total / 2**20:.0f} MB")
            if sha and h.hexdigest() != sha:
                raise Erro(f"o download do {name} veio diferente do esperado (SHA-256 não bate)")
            return dest
        except (OSError, Erro) as e:
            if attempt == 2:
                raise Erro(f"não consegui baixar o {name}: {e}")
            log(f"  {name}: falhou ({e}), tentando de novo…")
            time.sleep(3)


def unzip(src, dest, strip=True):
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            parts = Path(info.filename).parts[1 if strip else 0:]
            if not parts or info.is_dir():
                continue
            target = dest.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as s, open(target, "wb") as d:
                shutil.copyfileobj(s, d)


def extract_llvm(src, dest, work, log):
    """O .tar.zst do LLVM usa janela longa (o tar do Windows recusa). Extrai só os arquivos que usamos."""
    def wanted(parts):
        if len(parts) == 2 and parts[0] == "bin":
            return parts[1] in LLVM_BIN
        return len(parts) > 3 and parts[0] == "lib" and parts[1] == "clang" and parts[3] == "include"

    def take(tar):
        for member in tar:
            parts = Path(member.name).parts[1:]
            if parts and wanted(parts):
                member.name = str(Path(*parts))
                tar.extract(member, dest, filter="data")

    try:
        from compression import zstd  # Python 3.14+
    except ImportError:
        zstd = None
    if zstd:
        with zstd.open(src, "rb", options={zstd.DecompressionParameter.window_log_max: 31}) as raw, \
                tarfile.open(fileobj=raw, mode="r|") as tar:
            take(tar)
        return
    log("  Python sem zstd: usando o zstd.exe oficial")
    zdir = work / "zstd"
    unzip(download("zstd", work / "zstd.zip", log), zdir)
    p = subprocess.Popen([str(zdir / "zstd.exe"), "-d", "--long=31", "--memory=2048MB", "-c", str(src)],
                         stdout=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
    with tarfile.open(fileobj=p.stdout, mode="r|") as tar:
        take(tar)
    if p.wait():
        raise Erro("o zstd não conseguiu abrir o LLVM")


def ensure_deps(root, log):
    """Baixa (uma vez) o código das bibliotecas do CMake. Devolve {NOME: pasta} para FETCHCONTENT_SOURCE_DIR_*.
    Os .zip de tag do GitHub não têm SHA-256 garantido, então aqui não fixamos hash (só HTTPS)."""
    deps_dir = Path(root) / "bibliotecas"
    out = {}
    for name, url in DEPS.items():
        target = deps_dir / name.lower()
        if not (target / "CMakeLists.txt").is_file():
            shutil.rmtree(target, ignore_errors=True)
            deps_dir.mkdir(parents=True, exist_ok=True)
            log(f"Baixando a biblioteca {name.lower()}…")
            archive = download(name.lower(), deps_dir / f"{name.lower()}.zip", log, url=url)
            unzip(archive, target)
            archive.unlink()
        out[name] = target
    return out


def ensure(root, accepted_license, log):
    """Monta (ou confere) o compilador em root. Devolve os caminhos de paths()."""
    root = Path(root)
    if ready(root):
        log("Compilador portátil já está montado.")
        return paths(root)
    if not accepted_license:
        raise Erro("para montar o compilador portátil é preciso aceitar a licença da Microsoft das bibliotecas "
                   f"do Visual C++ e do Windows SDK ({LICENSE_URL}). O launcher pergunta antes de começar.")
    work = root / "_baixando"
    for sub in ("llvm", "cmake", "ninja", "xwin", "winsysroot", "_baixando", "_xwin-cache"):
        shutil.rmtree(root / sub, ignore_errors=True)
    work.mkdir(parents=True)

    log("Baixando o CMake e o Ninja…")
    unzip(download("cmake", work / "cmake.zip", log), root / "cmake")
    unzip(download("ninja", work / "ninja.zip", log), root / "ninja", strip=False)

    log(f"Baixando o LLVM {LLVM_VERSION} (264 MB)…")
    llvm = download("llvm", work / "llvm.tar.zst", log)
    log("Extraindo só o compilador e o linker (1–2 min)…")
    extract_llvm(llvm, root / "llvm", work, log)
    llvm.unlink()

    log("Baixando as bibliotecas do Visual C++ e o Windows SDK da Microsoft (~1 GB, alguns minutos)…")
    with tarfile.open(download("xwin", work / "xwin.tar.gz", log)) as tar:
        member = next(m for m in tar if m.name.endswith("xwin.exe"))
        member.name = "xwin.exe"
        tar.extract(member, root / "xwin", filter="data")
    cmd = [str(root / "xwin" / "xwin.exe"), "--accept-license", "--arch", "x86_64",
           "--cache-dir", str(root / "_xwin-cache"), "splat", "--use-winsysroot-style",
           "--preserve-ms-arch-notation", "--output", str(root / "winsysroot")]
    out = subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW)
    if out.returncode:
        tail = out.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise Erro("o xwin não conseguiu baixar as bibliotecas da Microsoft: " + " | ".join(tail))

    shutil.rmtree(root / "_xwin-cache", ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    p = paths(root)
    missing = [k for k, v in p.items() if not v.exists()]
    if missing:
        raise Erro(f"faltou {', '.join(missing)} depois de montar o compilador")
    (root / "pronto.json").write_text(VERSION_KEY, encoding="utf-8")
    log("Compilador portátil pronto.")
    return p
