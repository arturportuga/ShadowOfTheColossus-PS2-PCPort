# Shadow of the Colossus — PS2 — PC Native Port

**[Português](#português) · [English](#english)**

> Projeto por fã, não oficial. Nenhum conteúdo com direitos autorais é distribuído aqui.
> Fan project, unofficial. No copyrighted content is distributed here.

---

## Português

Launcher que transforma o seu ISO de Shadow of the Colossus (PS2) num jogo nativo de PC.

> [!IMPORTANT]
> **Só funciona com o ISO europeu (PAL) v1.00, código SCES-53326.** A versão americana (SCUS-97472) e outras
> versões não funcionam: o launcher confere o ISO e recusa os outros.

> [!WARNING]
> - **As primeiras vezes jogando ficam lentas**, até os gráficos serem gravados e recompilados (veja abaixo).
> - **Placas de vídeo fracas sofrem:** o vídeo do PS2 é imitado com precisão. Numa GTX 1650 o jogo fica em ~42 FPS.
> - **Use um caminho curto** (ex.: `C:\Jogos\SotC`); caminhos longos quebram a compilação.
> - **O Windows pode avisar que o launcher não é reconhecido** (ele não é assinado): "Mais informações" →
>   "Executar assim mesmo".

### Uso

1. Baixe o zip em **[Releases](../../releases)** e extraia numa pasta com caminho curto (ex.: `C:\Jogos\SotC`).
2. Abra o **`SotC Launcher.exe`** e escolha o seu ISO.
3. **Preparar o jogo** → **Começar** (a primeira vez leva de 20 min a 1 h).
4. **Jogar**.

Nas primeiras vezes o jogo fica lento. Jogue, feche e clique em **Recompilar** quando o launcher pedir;
depois de 3 ou 4 rodadas fica perto de 60 FPS.

### Requisitos

- ISO europeu (PAL) v1.00, SCES-53326
- Windows 10/11 64-bit, processador com AVX2, 8 GB de RAM, ~12 GB livres

### Planos

- Desempenho melhor em placas de vídeo mais fracas
- Recuperar os ~2% de FPS que a versão compilada com clang perde para a do Visual Studio
- Filtro de nitidez/upscale na saída de vídeo
- Pacote com os gráficos (VU1) já prontos, para pular as primeiras rodadas lentas
- Perfis de configuração por placa de vídeo
- Mensagens da preparação também em inglês

---

## English

Launcher that turns your Shadow of the Colossus PS2 ISO into a native PC build of the game.

> [!IMPORTANT]
> **Only works with the European (PAL) v1.00 ISO, SCES-53326.** The US version (SCUS-97472) and other versions
> do not work: the launcher checks the ISO and rejects the others.

> [!WARNING]
> - **The first play sessions are slow**, until the graphics are recorded and rebuilt (see below).
> - **Weak graphics cards struggle:** the PS2 video chip is emulated accurately. A GTX 1650 runs it at ~42 FPS.
> - **Use a short path** (e.g. `C:\Games\SotC`); long paths break the build.
> - **Windows may warn that the launcher is unrecognized** (it is unsigned): "More info" → "Run anyway".

### Usage

1. Download the zip from **[Releases](../../releases)** and extract it to a short path (e.g. `C:\Games\SotC`).
2. Open **`SotC Launcher.exe`** and pick your ISO.
3. **Set up the game** → **Start** (the first time takes 20 min to 1 h).
4. **Play**.

The game is slow at first. Play, close it and click **Rebuild** when the launcher asks; after 3 or 4 rounds it
runs close to 60 FPS.

### Requirements

- European (PAL) v1.00 ISO, SCES-53326
- Windows 10/11 64-bit, CPU with AVX2, 8 GB of RAM, ~12 GB free

### Plans

- Better performance on weaker graphics cards
- Win back the ~2% FPS the clang build loses to the Visual Studio build
- Sharpening/upscaling filter on the video output
- A pack with the graphics (VU1) already built, to skip the slow first sessions
- Per-GPU configuration profiles
- Setup messages in English too

---

## Créditos / Credits

[volstants](https://github.com/volstants/recomp-ShadowOfTheColossus-pc) (port) ·
[PS2Recomp](https://github.com/ran-j/PS2Recomp) · [xwin](https://github.com/Jake-Shadle/xwin) ·
[LLVM](https://llvm.org)

GPL-3.0
