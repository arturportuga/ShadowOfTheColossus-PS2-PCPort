"""Prepara o jogo a partir do ISO: confere, gera o código C++, traduz o VU1 capturado e compila.

    python pipeline.py --iso <ISO> [--port <pasta do 02_port>] [--mode rapido|equilibrado|economia]
                       [--compilador portatil|vs] [--aceito-licenca-ms] [--jobs N] [--force] [--debug-info]
    python pipeline.py --iso <ISO> --status        (só diz se precisa compilar)

Cada etapa só roda se for preciso: a geração tem uma impressão digital das entradas
(build/launcher_stamp.json) e o Ninja só recompila o que mudou.

Linhas para o launcher (o resto é log):
    @@STEP i n texto      @@PROGRESS feitos total      @@DONE      @@FAIL motivo
"""

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

if getattr(sys, "frozen", False):
    # Congelado: sotc_tools.exe fica em 04_launcher; o "SotC Launcher.exe" (que importa este módulo), na pasta
    # de cima. Nos dois casos a pasta de trabalho é a 04_launcher.
    _exe_dir = Path(sys.executable).resolve().parent
    HERE = _exe_dir / "04_launcher" if (_exe_dir / "04_launcher").is_dir() else _exe_dir
else:
    HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compilador  # noqa: E402

DEFAULT_PORT = HERE.parent / "02_port"
DEFAULT_CAPTURE = HERE.parent / "03_vu1_capture"
DEFAULT_COMPILER_DIR = HERE.parent / "compilador"
STEPS = 7
NINJA_PROGRESS = re.compile(r"^\[(\d+)/(\d+)\]")
CREATE_NO_WINDOW = 0x08000000
GB = 1024 ** 3
# O caminho mais fundo do build tem ~195 caracteres a partir da pasta do port (um .obj do
# rabbitizer), e o compilador não passa de 260: a pasta do port precisa ser curta.
MAX_PORT_PATH = 60
OEM = f"cp{ctypes.windll.kernel32.GetOEMCP()}"


class Fail(Exception):
    """Erro com mensagem em português (log) e um código para o launcher mostrar no idioma escolhido."""

    def __init__(self, message, code=None, **values):
        super().__init__(message)
        self.code = code
        self.values = values


def emit(text):
    print(text, flush=True)


def step(i, text):
    emit(f"@@STEP {i} {STEPS} {text}")
    if MEASURE:
        MEASURE.step(i, text)


# ------------------------------------------------------------------ medição

MEASURE = None
# A medição só liga com --medir ou com este arquivo na pasta do launcher (nossas máquinas);
# o pacote para amigos não traz o arquivo.
MEASURE_FLAG = HERE / "medir.txt"


class Measurement:
    """Grava em 04_launcher/medicoes/<data>.json a máquina, a memória e o tempo de cada etapa, para
    calibrar as estimativas dos modos. Regrava a cada poucos segundos: se o PC dormir ou a pessoa
    apertar Parar, o que já foi medido fica."""

    def __init__(self, info):
        self.path = HERE / "medicoes" / time.strftime("%Y-%m-%d_%H%M%S.json")
        self.path.parent.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.t0 = self.t_step = time.time()
        total, free = memory_gb()
        self.data = dict(info, inicio=time.strftime("%Y-%m-%d %H:%M:%S"), resultado="em andamento",
                         maquina=machine_info(), etapas=[],
                         memoria={"total_gb": round(total, 1), "usada_antes_gb": round(total - free, 1),
                                  "pico_usada_gb": round(total - free, 1), "menor_livre_gb": round(free, 1)})
        self.save()
        threading.Thread(target=self._sample, daemon=True).start()

    def _sample(self):
        while True:
            time.sleep(5)
            total, free = memory_gb()
            with self.lock:
                m = self.data["memoria"]
                m["pico_usada_gb"] = max(m["pico_usada_gb"], round(total - free, 1))
                m["menor_livre_gb"] = min(m["menor_livre_gb"], round(free, 1))
            self.save()

    def step(self, i, text):
        now = time.time()
        with self.lock:
            if self.data["etapas"]:
                self.data["etapas"][-1]["segundos"] = round(now - self.t_step)
            self.data["etapas"].append({"etapa": i, "nome": text})
            self.t_step = now
        self.save()

    def progress(self, done, total):
        now = time.time()
        with self.lock:
            s = self.data["etapas"][-1] if self.data["etapas"] else None
            if s is None:
                return
            if "arquivos" not in s:
                s["arquivos"] = {"total": total, "de": done}
                self.progress_start = now
            a = s["arquivos"]
            a["ate"] = done
            a["total"] = total  # o Ninja começa com [0/2] (checar o CMake) antes do total de verdade
            if now - self.progress_start > 30:
                a["por_minuto"] = round((done - a["de"]) / (now - self.progress_start) * 60, 1)

    def finish(self, result):
        now = time.time()
        with self.lock:
            if self.data["etapas"]:
                self.data["etapas"][-1]["segundos"] = round(now - self.t_step)
            self.data["resultado"] = result
            self.data["minutos_total"] = round((now - self.t0) / 60, 1)
        self.save()
        m = self.data["memoria"]
        emit(f"Medição: RAM usada {m['usada_antes_gb']} GB antes, pico de {m['pico_usada_gb']} GB, "
             f"mínimo livre {m['menor_livre_gb']} GB. Salva em {self.path}")

    def save(self):
        with self.lock:
            text = json.dumps(self.data, indent=2, ensure_ascii=False, default=str)
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass


def machine_info():
    """Processador, placa de vídeo, disco e Windows (para comparar máquinas sem pedir as especificações)."""
    drive = (HERE.drive or "C:")[0]
    script = (
        "$c=Get-CimInstance Win32_Processor|Select-Object -First 1;"
        "$g=(Get-CimInstance Win32_VideoController|ForEach-Object Name) -join ' + ';"
        "$d=try{$n=(Get-Partition -DriveLetter DRIVE -ErrorAction Stop).DiskNumber;"
        "$p=Get-PhysicalDisk|Where-Object DeviceId -eq \"$n\";\"$($p.MediaType) $($p.BusType) $($p.FriendlyName)\"}catch{''};"
        "@{processador=$c.Name.Trim();nucleos=$c.NumberOfCores;threads=$c.NumberOfLogicalProcessors;"
        "video=$g;disco=$d;windows=(Get-CimInstance Win32_OperatingSystem).Caption}|ConvertTo-Json -Compress"
    ).replace("DRIVE", drive)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                             timeout=30, creationflags=CREATE_NO_WINDOW).stdout
        return json.loads(out.decode(OEM, errors="replace"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"processador": "?", "threads": os.cpu_count()}


# ------------------------------------------------------------------ conferências

def iso_identity(port, iso):
    """O executável do jogo dentro do ISO bate com a versão suportada? Retorna o perfil."""
    profile = json.loads((port / "Port" / "profile" / "SCES-53326_v1.00.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(port / "Tools"))
    try:
        from iso9660 import Iso9660
    finally:
        sys.path.pop(0)
    try:
        disc = Iso9660(str(iso))
        entry = disc.find(profile["boot_elf"]["path"])
    except Exception as e:  # ISO corrompido ou não-ISO
        raise Fail(f"não consegui ler o ISO ({e})", "iso_unreadable")
    if not entry:
        raise Fail("esse ISO não é do Shadow of the Colossus (falta o SCES_533.26)", "iso_not_sotc")
    disc.f.seek(entry.lba * 2048)
    got = hashlib.sha256(disc.f.read(entry.size)).hexdigest()
    disc.f.close()
    if got != profile["boot_elf"]["sha256"]:
        raise Fail(f"versão do jogo não suportada: só a {profile['serial']} v{profile['version']} (PAL)",
                   "iso_wrong_version", serial=profile["serial"], version=profile["version"])
    return profile, got


def path_problem(port):
    length = len(str(port)) + 1
    if length > MAX_PORT_PATH:
        return (f"o caminho da pasta é longo demais ({length} caracteres, máximo {MAX_PORT_PATH}) e a compilação "
                f"falharia. Mova a pasta inteira para um lugar curto, como C:\\Jogos\\SotC")
    return None


def memory_gb():
    """(RAM total, RAM livre) em GB."""
    class MEMSTATUS(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("avail", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                    ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
    m = MEMSTATUS()
    m.len = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.total / GB, m.avail / GB


def ram_gb():
    return memory_gb()[0]


# Modos de compilação, como o "limitar o uso de RAM" dos instaladores de repack.
# Cada compilador do código gerado chegou a ~3 GB com dados de depuração (medido); sem eles deve ser
# menos, mas ainda não medimos. (nome, GB deixados para o resto do PC, máximo de compilações, prioridade)
#
# Compiladores: "portatil" = clang-cl + lld-link montados pelo compilador.py (padrão, sem Visual Studio);
# "vs" = o Visual Studio 2022 instalado. Uma build já configurada continua com o compilador dela.
# Por compilação: o MSVC chegou a ~2,8 GB nos arquivos enormes do jogo; o clang-cl a ~0,4 GB (no notebook,
# 8 compilações juntas somaram +1,3 GB).
COMPILERS = ("portatil", "vs")
DEFAULT_COMPILER = "portatil"
JOB_GB = {"vs": 3, "portatil": 0.5}
MODES = {
    "rapido": ("Rápido", 2, 99, "normal"),
    "equilibrado": ("Equilibrado", 6, 99, "baixa"),
    "economia": ("Economizar RAM", 8, 2, "baixa"),
}
DEFAULT_MODE = "equilibrado"
BELOW_NORMAL_PRIORITY_CLASS = 0x4000
# Arquivos por minuto, por compilação em paralelo. MSVC: ~34 (Ryzen 5 3350G, 4 compilações, 135/min).
# clang-cl: ~104 no notebook (i5-10300H, SSD, 8 compilações, 829/min) e ~113 no desktop (3, HD).
FILES_PER_JOB_MIN = {"vs": 34, "portatil": 100}
GENERATED_FILES = 9354
# Antes de compilar o jogo, na primeira vez: ferramentas + geração + configuração (+ montar o compilador
# portátil). Notebook: 2,2 + 3,7 + 1,5 + 1,5 min.
SETUP_MIN = {"vs": 9, "portatil": 9}


def mode_jobs(mode, ram=None, compiler=DEFAULT_COMPILER):
    _, reserve, cap, _ = MODES[mode]
    free = round(ram if ram is not None else ram_gb()) - reserve
    return max(1, min(os.cpu_count() or 1, cap, int(free // JOB_GB[compiler])))


def mode_estimate(mode, ram=None, compiler=DEFAULT_COMPILER):
    """(compilações, GB de RAM no pico, minutos da primeira preparação) — estimativa."""
    jobs = mode_jobs(mode, ram, compiler)
    return (jobs, round(jobs * JOB_GB[compiler] + 1),
            SETUP_MIN[compiler] + GENERATED_FILES / (FILES_PER_JOB_MIN[compiler] * jobs))


def find_vs():
    """Pasta do Visual Studio 2022 com o compilador C++ (VSROOT, vswhere ou caminhos comuns)."""
    candidates = []
    if os.environ.get("VSROOT"):
        candidates.append(os.environ["VSROOT"])
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
        "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.is_file():
        out = subprocess.run([str(vswhere), "-products", "*", "-requires",
                              "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                             capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout
        candidates += [line.strip() for line in out.splitlines() if line.strip()]
    candidates += [r"D:\VisualStudio\2022", r"C:\Program Files\Microsoft Visual Studio\2022\Community"]
    for c in candidates:
        if (Path(c) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat").is_file():
            return c
    return None


def find_windows_sdk():
    """Versão do Windows 10/11 SDK com cabeçalhos e o rc.exe, ou None. O instalador do VS pode deixar
    o SDK de fora; aí o vcvars64 falha em silêncio e o CMake só reclama do rc no teste do compilador."""
    import winreg
    roots = []
    for key in (r"SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots",
                r"SOFTWARE\Microsoft\Windows Kits\Installed Roots"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                roots.append(Path(winreg.QueryValueEx(k, "KitsRoot10")[0]))
        except OSError:
            pass
    roots.append(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10")
    for root in roots:
        include = root / "Include"
        versions = sorted((p.name for p in include.glob("10.*") if p.is_dir()), reverse=True) if include.is_dir() else []
        for v in versions:
            if (include / v / "ucrt" / "stdio.h").is_file() and (root / "bin" / v / "x64" / "rc.exe").is_file():
                return v
    return None


def find_git(vs):
    """Pasta do git.exe: o do PATH, o instalado no lugar padrão, ou o que vem junto com o Visual Studio."""
    found = shutil.which("git")
    if found:
        return str(Path(found).parent)
    candidates = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd"]
    vs = vs or find_vs()
    if vs:
        candidates.append(Path(vs) / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "TeamFoundation" /
                          "Team Explorer" / "Git" / "cmd")
    return next((str(c) for c in candidates if (c / "git.exe").is_file()), None)


def generation_fingerprint(port, boot_sha):
    """Entradas da geração: o jogo e as ferramentas/perfil que transformam ele em C++."""
    h = hashlib.sha256(boot_sha.encode())
    for rel in ("Tools/generate.py", "Tools/sotc_link.py", "Tools/split_register_functions.py",
                "Port/recomp/sotc.toml", "Port/profile/SCES-53326_v1.00.json",
                "build/ps2recomp-tools/ps2xRecomp/ps2_recomp.exe"):
        p = port / rel
        h.update(rel.encode() + (p.read_bytes() if p.is_file() else b"-"))
    return h.hexdigest()


def stamp_path(port):
    return port / "build" / "launcher_stamp.json"


def read_stamp(port):
    try:
        return json.loads(stamp_path(port).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def captured(capture):
    """Nomes dos programas de VU1 gravados (um .bin por programa)."""
    capture = Path(capture) if capture else None
    return sorted(p.name for p in capture.glob("*.bin")) if capture and capture.is_dir() else []


def status(port, iso, capture=None):
    """O que falta: dict com 'ok', 'reason' (texto) e 'code' (para o launcher traduzir). Não muda nada no disco."""
    _, boot_sha = iso_identity(port, iso)
    exe = port / "build" / "port" / "bin" / "sotc.exe"
    if not exe.is_file():
        return {"ok": False, "code": "not_built", "reason": "o jogo ainda não foi compilado"}
    stamp = read_stamp(port)
    if not stamp:
        return {"ok": True, "code": "pre_launcher", "reason": "compilado (antes do launcher)"}
    if stamp.get("generation") != generation_fingerprint(port, boot_sha):
        return {"ok": False, "code": "changed", "reason": "o ISO ou as ferramentas mudaram desde a última compilação"}
    if "vu1" in stamp:
        new = set(captured(capture)) - set(stamp["vu1"])
        if new:
            return {"ok": False, "code": "vu1_new", "n": len(new),
                    "reason": f"{len(new)} programas de VU1 novos para traduzir (deixa o jogo mais rápido)"}
    return {"ok": True, "code": "ok", "reason": "compilado e atualizado"}


# ------------------------------------------------------------------ execução

def run(cmd, cwd, env=None, progress=False, low_priority=False):
    """Roda um comando repassando a saída; com progress=True lê o [x/y] do Ninja.
    low_priority: o comando e tudo o que ele abre (ninja, cl) cedem a vez ao resto do PC."""
    if isinstance(cmd, str):
        shown, name = cmd, "cmake"
    else:
        cmd = [str(c) for c in cmd]
        shown, name = " ".join(f'"{c}"' if " " in c else c for c in cmd), Path(cmd[0]).name
    emit("+ " + shown)
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=CREATE_NO_WINDOW | (BELOW_NORMAL_PRIORITY_CLASS if low_priority else 0))
    for raw in iter(p.stdout.readline, b""):
        try:
            line = raw.decode("utf-8").rstrip()
        except UnicodeDecodeError:  # cmd, vswhere e o MSVC escrevem na página OEM (cp850 aqui)
            line = raw.decode(OEM, errors="replace").rstrip()
        if progress:
            m = NINJA_PROGRESS.match(line)
            if m:
                emit(f"@@PROGRESS {m.group(1)} {m.group(2)}")
                if MEASURE:
                    MEASURE.progress(int(m.group(1)), int(m.group(2)))
        emit(line)
    code = p.wait()
    if code:
        raise Fail(f"o comando falhou (código {code}): {name}")


def vs_cmd(port, *args):
    """Um comando dentro do ambiente do Visual Studio (vsenv.cmd do port). O cmd /s /c tira só
    o par de aspas de fora, então caminhos com espaço chegam inteiros."""
    inner = " ".join(f'"{a}"' for a in (port / "Tools" / "win" / "vsenv.cmd", *args))
    return f'cmd.exe /d /s /c "{inner}"'


def sync_vu1(port, capture, env):
    programs = sorted(capture.glob("*.bin")) if capture.is_dir() else []
    if not programs:
        emit("Nenhum programa de VU1 capturado: o jogo vai rodar no interpretador (muito lento) "
             "até a captura ser feita.")
        return
    stage = port / "build" / "vu1_staging"
    out = port / "Port" / "generated" / "vu1"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    run([port / "build" / "ps2recomp-tools" / "ps2xTest" / "vu1_recomp.exe", capture, stage], port, env)
    changed = 0
    for f in stage.iterdir():
        dst = out / f.name
        data = f.read_bytes()
        if not dst.is_file() or dst.read_bytes() != data:
            dst.write_bytes(data)
            changed += 1
    emit(f"VU1: {len(programs)} programas capturados, {changed} arquivos novos ou alterados")


def build_type_args(debug_info):
    """O port ajusta /Ob2 e /LTCG para RelWithDebInfo, então ficamos nele. Sem debug_info tiramos
    só o /Zi e o /debug: mesmo código gerado, sem o sotc.pdb de ~480 MB nem o mspdbsrv na memória."""
    args = ["-DCMAKE_BUILD_TYPE=RelWithDebInfo"]
    if not debug_info:
        for lang in ("C", "CXX"):
            args.append(f"-DCMAKE_{lang}_FLAGS_RELWITHDEBINFO=/O2 /Ob1 /DNDEBUG")
        for kind in ("EXE", "SHARED", "MODULE"):
            args.append(f"-DCMAKE_{kind}_LINKER_FLAGS_RELWITHDEBINFO=/INCREMENTAL:NO")
    return args


def configured_compiler(build):
    """Com qual compilador essa pasta de build foi configurada ("vs", "portatil" ou None se nunca foi)."""
    try:
        cache = (build / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"^CMAKE_CXX_COMPILER:\w+=(.*)$", cache, re.M)
    if not m:
        return None
    return "portatil" if "clang-cl" in m.group(1).lower() else "vs"


class Toolchain:
    """Monta os comandos do CMake para um dos compiladores."""

    def __init__(self, kind, port, vs=None, tools=None):
        self.kind, self.port, self.vs, self.tools = kind, port, vs, tools

    def cmake(self, *args):
        if self.kind == "vs":
            return vs_cmd(self.port, "cmake", *args)
        return [self.tools["cmake"], *args]

    def configure_args(self):
        if self.kind == "vs":
            return []
        return [f"-DCMAKE_TOOLCHAIN_FILE={(self.port / 'Tools' / 'win' / 'clang-cl.cmake').as_posix()}",
                f"-DCMAKE_MAKE_PROGRAM={Path(self.tools['ninja']).as_posix()}"]

    def env(self, git):
        path = [git] if git else []
        env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.longpaths", GIT_CONFIG_VALUE_0="true")
        if self.kind == "vs":
            env["VSROOT"] = self.vs
        else:
            path += [str(self.tools["llvm_bin"]), str(Path(self.tools["ninja"]).parent),
                     str(Path(self.tools["cmake"]).parent)]
            env["SOTC_LLVM_BIN"] = str(self.tools["llvm_bin"])
            env["SOTC_WINSYSROOT"] = str(self.tools["sysroot"])
        env["PATH"] = os.pathsep.join(path + [os.environ.get("PATH", "")])
        return env


def configured_debug_info(build):
    try:
        cache = (build / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"^CMAKE_CXX_FLAGS_RELWITHDEBINFO:STRING=(.*)$", cache, re.M)
    return bool(m and "/Zi" in m.group(1))


def prepare(port, iso, capture, mode, jobs, force, debug_info, measure=False, compiler=DEFAULT_COMPILER,
            compiler_dir=DEFAULT_COMPILER_DIR, accepted_license=False):
    t0 = time.time()
    name, _, _, priority = MODES[mode]
    low = priority == "baixa"
    global MEASURE
    build = port / "build" / "port"
    tools_build = port / "build" / "ps2recomp-tools"
    fresh = not (build / "build.ninja").is_file()
    had = None if fresh else configured_debug_info(build)
    # Uma build já configurada continua com o compilador dela (trocar = recompilar tudo do zero).
    compiler = configured_compiler(build) or compiler
    jobs = jobs or mode_jobs(mode, compiler=compiler)
    if measure:
        MEASURE = Measurement({"modo": mode, "compilador": compiler, "compilacoes": jobs, "primeira_vez": fresh,
                               "dados_de_depuracao": debug_info if fresh else had})
    exe = build / "bin" / "sotc.exe"

    step(1, "Conferindo o ISO e o espaço livre")
    profile, boot_sha = iso_identity(port, iso)
    emit(f"ISO: {profile['serial']} v{profile['version']} confirmado ({boot_sha[:12]}…)")
    if path_problem(port):
        raise Fail(path_problem(port))
    portable = compiler == "portatil"
    need = (8 if fresh else 2) + (3 if portable and not compilador.ready(compiler_dir) else 0)
    free = shutil.disk_usage(port).free / GB
    emit(f"Espaço livre: {free:.1f} GB (precisa de ~{need} GB)")
    if free < need:
        raise Fail(f"pouco espaço livre em {port.drive}: {free:.1f} GB, precisa de ~{need} GB")
    vs = None
    if not portable:
        vs = find_vs()
        if not vs:
            raise Fail("esta pasta foi compilada com o Visual Studio 2022, que não foi encontrado")
        sdk = find_windows_sdk()
        if not sdk:
            raise Fail("o Windows SDK não está instalado (o Visual Studio sozinho não basta). Abra o Visual Studio "
                       "Installer > Modificar > Componentes individuais, marque o \"Windows 11 SDK\" mais novo e "
                       "clique em Modificar. Depois é só preparar de novo.")
        emit(f"Visual Studio: {vs} (Windows SDK {sdk})")
    emit(f"Modo {name}: {jobs} compilações em paralelo, prioridade {priority} "
         f"({ram_gb():.0f} GB de RAM, {os.cpu_count()} threads)")
    # O Git não é mais necessário (as bibliotecas vêm em .zip); se existir, fica no PATH para quem usar.
    git = find_git(vs)

    step(2, "Compilador e bibliotecas")
    deps_args = []
    try:
        if portable:
            tc = Toolchain("portatil", port, tools=compilador.ensure(compiler_dir, accepted_license, emit))
            emit(f"Compilador portátil: clang-cl {compilador.LLVM_VERSION} em {compiler_dir}")
        else:
            tc = Toolchain("vs", port, vs=vs)
            emit("Compilador: Visual Studio (esta pasta já foi configurada com ele)")
        if fresh or not (tools_build / "build.ninja").is_file():
            deps = compilador.ensure_deps(compiler_dir, emit)
            deps_args = [f"-DFETCHCONTENT_SOURCE_DIR_{name}={path.as_posix()}" for name, path in deps.items()]
            emit(f"Bibliotecas: {', '.join(n.lower() for n in deps)}")
    except compilador.Erro as e:
        raise Fail(str(e))
    env = tc.env(git)

    step(3, "Ferramentas de recompilação")
    if all((tools_build / p).is_file() for p in ("ps2xRecomp/ps2_recomp.exe", "ps2xTest/vu1_recomp.exe")):
        emit("Já estão compiladas.")
    else:
        if not (tools_build / "build.ninja").is_file():
            # No clang-cl o Release do PS2Recomp usa /Qspectre-, que ele não aceita: vai o RelWithDebInfo leve.
            build_type = ["-DCMAKE_BUILD_TYPE=Release"] if tc.kind == "vs" else build_type_args(False)
            # Só o recompilador e o vu1_recomp: sem estúdio, analisador nem interface de depuração (e sem as
            # bibliotecas deles: imgui, SDL2, nlohmann_json).
            run(tc.cmake("-S", port / "External" / "PS2Recomp", "-B", tools_build, "-G", "Ninja",
                         *build_type, *tc.configure_args(), *deps_args, "-DPS2X_BUILD_ANALYZER=OFF",
                         "-DPS2X_BUILD_STUDIO=OFF", "-DPS2X_ENABLE_DEBUG_UI=OFF", "-DPS2X_ENABLE_FFMPEG=OFF"),
                port, env)
        run(tc.cmake("--build", tools_build, "--target", "ps2_recomp", "vu1_recomp", "-j", str(jobs)),
            port, env, progress=True, low_priority=low)

    step(4, "Gerando o código C++ do jogo a partir do ISO")
    fingerprint = generation_fingerprint(port, boot_sha)
    generated = port / "Port" / "generated"
    count = len(list(generated.glob("*.cpp"))) if generated.is_dir() else 0
    if not force and read_stamp(port).get("generation") == fingerprint and count > 9000:
        emit(f"Nada mudou desde a última vez ({count} arquivos).")
    else:
        run([sys.executable, "-I", port / "Tools" / "generate.py", "--iso", iso], port, env)

    step(5, "Traduzindo os programas de VU1 capturados")
    sync_vu1(port, capture, env)

    step(6, "Preparando a compilação")
    if fresh:
        emit("Dados de depuração: " + ("sim (sotc.pdb)" if debug_info else "não (compilação mais leve)"))
        run(tc.cmake("-S", port, "-B", build, "-G", "Ninja", *build_type_args(debug_info), *tc.configure_args(),
                     *deps_args), port, env)
    else:
        # Trocar isso numa compilação já feita obrigaria a recompilar tudo: fica como está.
        emit("Já está configurada" + ("" if had is None else f" (dados de depuração: {'sim' if had else 'não'})") + ".")

    step(7, "Compilando o jogo (a primeira vez leva bastante tempo)")
    run(tc.cmake("--build", build, "--target", "sotc", "-j", str(jobs)), port, env, progress=True, low_priority=low)
    if not exe.is_file():
        raise Fail("a compilação terminou mas o sotc.exe não apareceu")

    stamp_path(port).write_text(json.dumps({"generation": fingerprint, "iso": str(iso), "vu1": captured(capture),
                                            "compiler": compiler, "built": time.strftime("%Y-%m-%d %H:%M")},
                                           indent=2), encoding="utf-8")
    emit(f"Pronto em {(time.time() - t0) / 60:.1f} min.")
    if MEASURE:
        MEASURE.finish("pronto")
    emit("@@DONE")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iso", required=True, type=Path)
    ap.add_argument("--port", type=Path, default=DEFAULT_PORT)
    ap.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE, help="pasta com os programas de VU1 gravados")
    ap.add_argument("--mode", choices=MODES, default=DEFAULT_MODE,
                    help="rapido = mais RAM e prioridade normal; economia = no máximo 2 compilações")
    ap.add_argument("--jobs", type=int, default=0, help="compilações em paralelo (0 = pelo modo e pela RAM)")
    ap.add_argument("--debug-info", action="store_true",
                    help="gera o sotc.pdb (só para investigar travamentos; vale numa pasta de build nova)")
    ap.add_argument("--force", action="store_true", help="gera o código de novo mesmo sem mudanças")
    ap.add_argument("--medir", action="store_true",
                    help="grava a máquina, a memória e o tempo em medicoes/ (liga sozinho com medir.txt)")
    ap.add_argument("--compilador", choices=COMPILERS, default=DEFAULT_COMPILER,
                    help="portatil = clang-cl baixado na hora (sem Visual Studio); vs = Visual Studio 2022. "
                         "Uma build já configurada continua com o dela")
    ap.add_argument("--compilador-dir", type=Path, default=DEFAULT_COMPILER_DIR,
                    help="onde montar o compilador portátil")
    ap.add_argument("--aceito-licenca-ms", action="store_true",
                    help="aceita a licença da Microsoft das bibliotecas do Visual C++ e do Windows SDK (xwin)")
    ap.add_argument("--status", action="store_true", help="só diz se precisa compilar")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    port, iso = args.port.resolve(), args.iso.resolve()
    try:
        if args.status:
            emit(json.dumps(status(port, iso, args.capture.resolve()), ensure_ascii=False))
        else:
            prepare(port, iso, args.capture.resolve(), args.mode, args.jobs, args.force, args.debug_info,
                    args.medir or MEASURE_FLAG.is_file(), args.compilador, args.compilador_dir.resolve(),
                    args.aceito_licenca_ms)
    except Fail as e:
        if MEASURE:
            MEASURE.finish(f"falhou: {e}")
        emit(f"@@FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
