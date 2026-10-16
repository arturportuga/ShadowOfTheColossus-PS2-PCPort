"""Textos do launcher em português e inglês. tr("chave", **valores) devolve no idioma escolhido."""

import ctypes

LANGS = {"pt": "Português", "en": "English"}
_lang = "pt"


def default_lang():
    """Português se o Windows estiver em português; senão, inglês."""
    try:
        return "pt" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x16 else "en"
    except (AttributeError, OSError):
        return "en"


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else "en"


def lang():
    return _lang


def tr(key, **values):
    text = T[key][_lang] if isinstance(T[key], dict) else T[key]
    return text.format(**values) if values else text


def p(pt, en):
    return {"pt": pt, "en": en}


T = {
    # janela
    "subtitle": p("Port nativo do PS2 para PC · projeto de fãs, não oficial",
                  "Native PS2-to-PC port · unofficial fan project"),
    "language": p("Idioma", "Language"),
    "tab_game": p("Jogo", "Game"),
    "tab_video": p("Vídeo", "Video"),
    "tab_controls": p("Controles", "Controls"),
    "tab_advanced": p("Avançado", "Advanced"),
    "tab_prepare": p("Preparação", "Setup"),
    "play": p("▶  Jogar", "▶  Play"),
    "prepare_game": p("⚙  Preparar o jogo", "⚙  Set up the game"),
    "preparing": p("Preparando…", "Setting up…"),
    "game_open": p("Jogo aberto", "Game running"),
    "save": p("Salvar", "Save"),
    "saved": p("Salvo.", "Saved."),
    "saved_running": p("Salvo. Vale na próxima vez que o jogo abrir.", "Saved. Takes effect next time the game starts."),

    # aba Jogo
    "iso_label": p("Imagem do jogo (ISO)", "Game disc image (ISO)"),
    "browse": p("Procurar…", "Browse…"),
    "port_label": p("Pasta do port", "Port folder"),
    "minimize": p("Minimizar o launcher ao jogar", "Minimize the launcher while playing"),
    "capture": p("Gravar gráficos novos (programas de VU1) enquanto joga",
                 "Record new graphics (VU1 programs) while playing"),
    "capture_hint": p("Deixe ligado até o jogo ficar rápido em todo lugar. Custa ~2 FPS.",
                      "Keep it on until the game runs fast everywhere. Costs ~2 FPS."),
    "recompile": p("Recompilar", "Rebuild"),
    "game_folder": p("Pasta do jogo", "Game folder"),
    "game_log": p("Log do jogo", "Game log"),
    "iso_missing": p("✘ Arquivo não encontrado", "✘ File not found"),
    "iso_found": p("Encontrado ({gb:.2f} GB)", "Found ({gb:.2f} GB)"),
    "iso_ok": p("✔ Shadow of the Colossus {serial} v{version} (PAL)", "✔ Shadow of the Colossus {serial} v{version} (PAL)"),
    "iso_unreadable": p("✘ Não consegui ler o ISO", "✘ Could not read the ISO"),
    "iso_not_sotc": p("✘ Esse ISO não é do Shadow of the Colossus", "✘ This ISO is not Shadow of the Colossus"),
    "iso_wrong_version": p("✘ Versão não suportada: só a {serial} v{version} (PAL)",
                           "✘ Unsupported version: only {serial} v{version} (PAL)"),
    "not_port": p("✘ Essa pasta não é o port (falta Tools\\generate.py)",
                  "✘ This folder is not the port (Tools\\generate.py is missing)"),
    "path_too_long": p("✘ Caminho longo demais ({n} caracteres, máximo {max}). Mova a pasta para um lugar curto, "
                       "como C:\\Jogos\\SotC.",
                       "✘ Path too long ({n} characters, max {max}). Move the folder somewhere short, "
                       "like C:\\Games\\SotC."),
    "st_ok": p("✔ Jogo compilado e atualizado", "✔ Game built and up to date"),
    "st_pre_launcher": p("✔ Jogo compilado", "✔ Game built"),
    "st_not_built": p("⚠ Precisa preparar: o jogo ainda não foi compilado", "⚠ Setup needed: the game is not built yet"),
    "st_changed": p("⚠ Precisa preparar: o ISO ou as ferramentas mudaram",
                    "⚠ Setup needed: the ISO or the tools changed"),
    "st_vu1_new": p("⚠ {n} gráficos novos (VU1) para traduzir: recompile para ganhar velocidade",
                    "⚠ {n} new graphics (VU1) to translate: rebuild to speed things up"),
    "vu1_some": p("✔ Gráficos: {n} programas de VU1 gravados", "✔ Graphics: {n} VU1 programs recorded"),
    "vu1_none": p("⚠ Gráficos: nenhum programa de VU1 ainda (lento até gravar e recompilar)",
                  "⚠ Graphics: no VU1 programs yet (slow until recorded and rebuilt)"),

    # aba Preparação
    "mode_frame": p(" Modo de compilação ", " Build mode "),
    "mode_rapido": p("Rápido", "Fast"),
    "mode_equilibrado": p("Equilibrado", "Balanced"),
    "mode_economia": p("Economizar RAM", "Save RAM"),
    "hint_rapido": p("evite usar o PC enquanto isso", "avoid using the PC meanwhile"),
    "hint_equilibrado": p("recomendado", "recommended"),
    "hint_economia": p("para usar o PC enquanto compila", "to keep using the PC while it builds"),
    "mode_line": p("~{time} · até ~{gb} GB de RAM · {hint}", "~{time} · up to ~{gb} GB of RAM · {hint}"),
    "compiler_portable": p("portátil (baixado na 1ª vez, ~1,3 GB)", "portable (downloaded the first time, ~1.3 GB)"),
    "compiler_vs": p("Visual Studio (usado nesta pasta)", "Visual Studio (used in this folder)"),
    "compiler_line": p("Compilador: {which}   ·   Tempos da 1ª vez; depois só recompila o que mudou.",
                       "Compiler: {which}   ·   First-time estimates; later only changes are rebuilt."),
    "ready_to_prepare": p("Pronto para preparar.", "Ready to set up."),
    "choose_mode": p("Escolha o modo de compilação e clique em Começar.", "Choose a build mode and click Start."),
    "start": p("Começar", "Start"),
    "stop": p("Parar", "Stop"),
    "starting": p("Começando…", "Starting…"),
    "step": p("Etapa {i} de {n}: {text}", "Step {i} of {n}: {text}"),
    "steps": p(["Conferindo o ISO e o espaço livre", "Compilador e bibliotecas", "Ferramentas de recompilação",
                "Gerando o código C++ do jogo a partir do ISO", "Traduzindo os programas de VU1",
                "Preparando a compilação", "Compilando o jogo"],
               ["Checking the ISO and free space", "Compiler and libraries", "Recompiler tools",
                "Generating the game's C++ code from the ISO", "Translating the VU1 programs",
                "Configuring the build", "Building the game"]),
    "elapsed": p("{t} no total", "{t} elapsed"),
    "eta": p(" · faltam ~{t}", " · ~{t} left"),
    "files": p("{done} de {total} arquivos{eta} · {t} no total", "{done} of {total} files{eta} · {t} elapsed"),
    "done": p("✔ Pronto! ({t})", "✔ Done! ({t})"),
    "game_ready": p("Jogo preparado. Pode jogar.", "The game is ready to play."),
    "stopped": p("Parado. Da próxima vez continua de onde parou.", "Stopped. Next time it resumes where it left off."),
    "failed": p("✘ Falhou: {reason}", "✘ Failed: {reason}"),
    "failed_box": p("A preparação falhou:\n\n{reason}\n\nO log completo fica em:\n{log}",
                    "Setup failed:\n\n{reason}\n\nThe full log is at:\n{log}"),
    "start_failed": p("Não consegui iniciar a preparação:\n{e}", "Could not start the setup:\n{e}"),
    "stop_confirm": p("Parar a preparação?\nO que já foi compilado é aproveitado na próxima vez.",
                      "Stop the setup?\nWhat is already built will be reused next time."),
    "license_title": p("Compilador", "Compiler"),
    "license_body": p("Na primeira preparação o launcher baixa o compilador (~1,3 GB, nada é instalado no Windows):\n\n"
                      "• LLVM/clang, CMake e Ninja (código aberto)\n"
                      "• bibliotecas do Visual C++ e Windows SDK, direto da Microsoft\n\n"
                      "As bibliotecas da Microsoft seguem a licença dela:\n{url}\n\nAceitar e continuar?",
                      "The first setup downloads the compiler (~1.3 GB, nothing is installed in Windows):\n\n"
                      "• LLVM/clang, CMake and Ninja (open source)\n"
                      "• Visual C++ libraries and Windows SDK, straight from Microsoft\n\n"
                      "Microsoft's libraries are under Microsoft's license:\n{url}\n\nAccept and continue?"),

    # aba Vídeo
    "maximized": p("Abrir maximizado", "Start maximized"),
    "maximized_hint": p("F11 alterna a tela cheia durante o jogo.", "F11 toggles fullscreen in game."),
    "widescreen": p("Widescreen", "Widescreen"),
    "widescreen_hint": p("Desligado: 4:3 como no PS2.", "Off: 4:3 like on the PS2."),
    "vsync": p("VSync", "VSync"),
    "vsync_hint": p("Evita cortes na imagem.", "Prevents screen tearing."),
    "motion_blur": p("Motion blur da câmera", "Camera motion blur"),
    "frequency": p("Frequência", "Refresh rate"),
    "res_native": p("Resolução interna: nativa do PS2", "Internal resolution: native PS2"),

    # aba Controles
    "controls_intro": p("Teclado e mouse. Controles de Xbox e PlayStation são detectados automaticamente.",
                        "Keyboard and mouse. Xbox and PlayStation controllers are detected automatically."),
    "fixed_keys": p("Fixos: WASD andar · mouse câmera · F5/F9 estado rápido · F11 tela cheia",
                    "Fixed: WASD move · mouse camera · F5/F9 quick state · F11 fullscreen"),
    "mouse_sens": p("Sensibilidade do mouse", "Mouse sensitivity"),
    "vertical": p("vertical", "vertical"),
    "invert_camera": p("Inverter câmera", "Invert camera"),
    "invert_options": p(["Não inverter", "Inverter horizontal", "Inverter vertical", "Inverter os dois"],
                        ["Don't invert", "Invert horizontal", "Invert vertical", "Invert both"]),
    "restore_defaults": p("Restaurar padrão", "Restore defaults"),
    "change_key": p("Alterar tecla", "Change key"),
    "button_n": p("Botão {b}", "Button {b}"),
    "press_key": p("Aperte uma tecla\nou clique aqui com o mouse", "Press a key\nor click here with the mouse"),
    "cancel": p("Cancelar", "Cancel"),
    "key_rejected": p("“{k}” não é aceita pelo jogo.\nTente outra tecla.", "“{k}” is not supported by the game.\nTry another key."),
    "key_reserved": p("{key} já é usado para {use} ({button}).", "{key} is already used for {use} ({button})."),
    "key_twice": p("{key} está em dois botões: {a} e {b}.", "{key} is on two buttons: {a} and {b}."),
    "use_walk": p("andar (analógico esquerdo)", "moving (left stick)"),
    "use_quicksave": p("salvar estado rápido", "quick save state"),
    "use_quickload": p("carregar estado rápido", "quick load state"),
    "use_fullscreen": p("tela cheia", "fullscreen"),

    # aba Avançado
    "adv_intro": p("Se não souber o que é, deixe como está.", "If you're not sure, leave these as they are."),
    "hw_raster": p("Rasterização por hardware", "Hardware rasterization"),
    "experimental_slower": p("Experimental. Ficou mais lenta nas placas AMD e NVIDIA testadas.",
                             "Experimental. Was slower on the AMD and NVIDIA cards tested."),
    "direct_present": p("Apresentação direta", "Direct presentation"),
    "gs_thread": p("Gráficos em thread separada", "Graphics on a separate thread"),
    "mtvu": p("VU1 em thread separada (MTVU)", "VU1 on a separate thread (MTVU)"),
    "four_cores": p("Recomendado com 4 núcleos ou mais.", "Recommended with 4 or more cores."),
    "vu1_recomp": p("VU1 recompilado", "Recompiled VU1"),
    "vu1_recomp_hint": p("Desligado: interpretador (muito lento).", "Off: interpreter (very slow)."),
    "memcard": p("Memory card", "Memory card"),
    "memcard_hint": p("Saves em memcards\\Mcd001.ps2, na pasta do jogo.", "Saves go to memcards\\Mcd001.ps2 in the game folder."),
    "script_trace": p("Registrar decisões dos scripts", "Log the game's script decisions"),
    "script_trace_hint": p("Para estudo: grava em script_trace.log o que os scripts do jogo executam.",
                           "For study: writes what the game's scripts run to script_trace.log."),
    "edit_ini": p("Editar sotc.ini", "Edit sotc.ini"),

    # jogar e diálogos
    "already_open": p("O jogo já está aberto.", "The game is already running."),
    "open_failed": p("Não consegui abrir o jogo:\n{e}", "Could not start the game:\n{e}"),
    "early_exit": p("O jogo fechou logo ao abrir (código {code}).\n\nFinal do log:\n{tail}",
                    "The game closed right after starting (code {code}).\n\nEnd of the log:\n{tail}"),
    "empty": p("(vazio)", "(empty)"),
    "game_closed": p("O jogo foi fechado.", "The game was closed."),
    "pick_iso": p("Escolha o ISO do Shadow of the Colossus", "Choose the Shadow of the Colossus ISO"),
    "disc_image": p("Imagem de disco", "Disc image"),
    "all_files": p("Todos", "All files"),
    "pick_port": p("Pasta do port (a que tem Tools, Port e External)", "Port folder (the one with Tools, Port and External)"),
    "no_log": p("Ainda não há log: o jogo não foi aberto pelo launcher.", "No log yet: the game hasn't been started from the launcher."),
    "close_confirm": p("A preparação está em andamento e vai ser interrompida.\nFechar mesmo assim?",
                       "Setup is running and will be interrupted.\nClose anyway?"),
}

# (chave do ini, nome do botão de PS2 em pt/en, tecla padrão)
BUTTONS = [
    ("PS2X_BIND_CROSS", p("✕  Xis", "✕  Cross"), "F"),
    ("PS2X_BIND_CIRCLE", p("○  Bola", "○  Circle"), "MOUSE_RIGHT"),
    ("PS2X_BIND_SQUARE", p("□  Quadrado", "□  Square"), "MOUSE_LEFT"),
    ("PS2X_BIND_TRIANGLE", p("△  Triângulo", "△  Triangle"), "SPACE"),
    ("PS2X_BIND_L1", "L1", "Q"),
    ("PS2X_BIND_R1", "R1", "LEFT_SHIFT"),
    ("PS2X_BIND_L2", "L2", "LEFT_CTRL"),
    ("PS2X_BIND_R2", "R2", "RIGHT_SHIFT"),
    ("PS2X_BIND_L3", "L3", "H"),
    ("PS2X_BIND_R3", "R3", "G"),
    ("PS2X_BIND_START", "Start", "ENTER"),
    ("PS2X_BIND_SELECT", "Select", "TAB"),
    ("PS2X_BIND_UP", p("Direcional ↑", "D-pad ↑"), "UP"),
    ("PS2X_BIND_DOWN", p("Direcional ↓", "D-pad ↓"), "DOWN"),
    ("PS2X_BIND_LEFT", p("Direcional ←", "D-pad ←"), "LEFT"),
    ("PS2X_BIND_RIGHT", p("Direcional →", "D-pad →"), "RIGHT"),
]

PRETTY = {
    "MOUSE_LEFT": p("Mouse: esquerdo", "Mouse: left"), "MOUSE_RIGHT": p("Mouse: direito", "Mouse: right"),
    "MOUSE_MIDDLE": p("Mouse: meio", "Mouse: middle"), "LEFT_SHIFT": p("Shift esquerdo", "Left Shift"),
    "RIGHT_SHIFT": p("Shift direito", "Right Shift"), "LEFT_CTRL": p("Ctrl esquerdo", "Left Ctrl"),
    "RIGHT_CTRL": p("Ctrl direito", "Right Ctrl"), "SPACE": p("Espaço", "Space"), "ENTER": "Enter", "TAB": "Tab",
    "BACKSPACE": "Backspace", "ESCAPE": "Esc", "UP": p("Seta ↑", "Up ↑"), "DOWN": p("Seta ↓", "Down ↓"),
    "LEFT": p("Seta ←", "Left ←"), "RIGHT": p("Seta →", "Right →"),
}


def local(value):
    """Um texto que pode ser fixo ("L1") ou por idioma (p(...))."""
    return value[_lang] if isinstance(value, dict) else value
