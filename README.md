# Shadow of the Colossus — PS2 → PC

**[Português](#português) · [English](#english)**

> Projeto de fãs, não oficial. Nada do jogo é distribuído aqui: nem ISO, nem arquivos do disco, nem BIOS.
> Fan project, unofficial. No game data is distributed here: no ISO, no disc files, no BIOS.

---

## Português

Um launcher que transforma o **seu** ISO de Shadow of the Colossus (PS2) num jogo nativo de PC, sem emulador.
Não precisa instalar Python, Git nem Visual Studio.

### Download e uso

1. Baixe o `SotC-PS2-Launcher.zip` em **[Releases](../../releases)** e extraia numa pasta com caminho curto
   (ex.: `C:\Jogos\SotC`).
2. Abra o **`SotC Launcher.exe`** e escolha o seu ISO.
3. Clique em **Preparar o jogo** e em **Começar**. Na primeira vez ele baixa o compilador (~1,3 GB) e leva de
   20 min a 1 h, conforme o PC.
4. Clique em **Jogar**.

Nas primeiras vezes o jogo fica lento: os gráficos do PS2 (programas de VU1) só aparecem com o jogo rodando.
Jogue, feche e clique em **Recompilar** quando o launcher pedir. Depois de 3 ou 4 rodadas fica perto de 60 FPS.

### Você precisa de

- ISO europeu (PAL) **v1.00, SCES-53326**. A versão americana não funciona.
- Windows 10/11 64-bit e processador com AVX2.
- 8 GB de RAM, ~12 GB livres e internet na primeira vez.

### Como funciona

O launcher baixa um compilador portátil (LLVM/clang, mais as bibliotecas do Visual C++ e o Windows SDK direto
da Microsoft, pelo [xwin](https://github.com/Jake-Shadle/xwin)). O [PS2Recomp](https://github.com/ran-j/PS2Recomp)
traduz o código do jogo para C++ a partir do ISO, e o
[port do volstants](https://github.com/volstants/recomp-ShadowOfTheColossus-pc) compila esse código com um
runtime que faz o papel do PS2.

---

## English

A launcher that turns **your own** Shadow of the Colossus PS2 disc image into a native PC build of the game,
no emulator involved. No Python, Git or Visual Studio needed.

### Download and use

1. Get `SotC-PS2-Launcher.zip` from **[Releases](../../releases)** and extract it to a short path
   (e.g. `C:\Games\SotC`).
2. Open **`SotC Launcher.exe`** and pick your ISO.
3. Click **Set up the game**, then **Start**. The first time it downloads the compiler (~1.3 GB) and takes
   20 min to 1 h depending on the PC.
4. Click **Play**.

The game is slow at first: the PS2's graphics programs (VU1) only show up while the game runs. Play, close it
and click **Rebuild** when the launcher asks. After 3 or 4 rounds it runs close to 60 FPS.

### You need

- The European (PAL) **v1.00, SCES-53326** ISO. The US version does not work.
- Windows 10/11 64-bit and a CPU with AVX2.
- 8 GB of RAM, ~12 GB free and an internet connection the first time.

### How it works

The launcher fetches a portable compiler (LLVM/clang, plus the Visual C++ libraries and Windows SDK straight from
Microsoft, through [xwin](https://github.com/Jake-Shadle/xwin)). [PS2Recomp](https://github.com/ran-j/PS2Recomp)
translates the game code from your ISO into C++, and
[volstants' port](https://github.com/volstants/recomp-ShadowOfTheColossus-pc) builds it with a runtime that
stands in for the PS2.

---

## Créditos / Credits

- [volstants](https://github.com/volstants/recomp-ShadowOfTheColossus-pc) — o port / the port
- [ran-j/PS2Recomp](https://github.com/ran-j/PS2Recomp) — o recompilador / the recompiler
- [Jake-Shadle/xwin](https://github.com/Jake-Shadle/xwin), [LLVM](https://llvm.org), [CMake](https://cmake.org),
  [Ninja](https://ninja-build.org)
- Launcher escrito com a ajuda do Claude (Anthropic) / launcher written with help from Claude (Anthropic)

Código do launcher em [`launcher/`](launcher). Licença / License: **GPL-3.0**.
