# Sprints da Etapa 2 — motor de voz

Etapa 2 da ADR-030 do NewClaw, autorizada pela operadora em 29/10/2026, para ser feita em sprints. Cada sprint termina com
testes e um commit local. Nada de push nem publicação sem o OK dela. Antes de instalar qualquer coisa na máquina ou de gastar
cota de nuvem, aviso e peço.

**Pronto da Etapa 2 (ADR-030):**
- testes das funções puras;
- interrupção por voz real provada;
- sem configuração, o motor sai com um aviso claro.

| Sprint | O que entrega | Precisa de | Estado |
|---|---|---|---|
| 1 — Base sem dependências | Repositório; configuração da tabela 4 com ausência reportada; texto → frases para a fala (H2/D4); protocolo `falar`/`interromper`; `diagnostico` com saída 0/1/2 | Nada além do Python 3.10+ | **feita** (29/10) |
| 2 — Pipecat no Windows | Instalar o Pipecat num ambiente isolado (`.venv` do projeto); conferir os binários (PyAV/FFmpeg e codecs, ONNX) e as licenças instaladas; fixar as versões | **OK para instalar** (dado em 29/10) | **feita** (29/10) |
| 3 — Pipeline do motor | `VAD → STT → user-transcription` e `client-message falar → TTS frase a frase`, com o servidor HTTP só em `127.0.0.1`; teste com áudio gravado no lugar do microfone | Um servidor de STT e um de TTS que você indicar | a fazer |
| 4 — Interrupção por voz real | VAD do usuário corta a fala; prova com microfone de verdade | Você falando no microfone | a fazer |
| 5 — Linux | Repetir as provas 2–4 numa máquina Linux | Qual máquina usar (indicação sua) | a fazer |

## Sprint 1 — resultado (29/10/2026)

- `newclaw_ivox/configuracao.py`:
  - lê `VOZ_STT_*`, `VOZ_TTS_*`, `VOZ_IDIOMA`, `VOZ_ICE_SERVIDORES` e `HARNESS_PORTA`, do ambiente e de um `.env` opcional;
  - sem URL, o serviço fica desligado e isso é reportado;
  - com URL, mas sem modelo (ou sem voz, na síntese), é erro: nada é escolhido no código;
  - a chave nunca aparece no resumo.
- `newclaw_ivox/frases.py`:
  - tira a marcação Markdown que seria lida em voz alta;
  - divide o texto por pontuação e quebra de linha;
  - frase acima de 160 caracteres é partida na pausa mais próxima. O limite vem da Etapa 0: 234 caracteres levaram 3,39 s, e o
    Pipecat avisa aos ~3 s.
  - Blocos de código não são falados; ficam na tela e no histórico.
- `newclaw_ivox/controle.py`:
  - traduz `{"t":"falar","d":{"texto":…}}` e `{"t":"interromper"}` na ação do motor;
  - mensagens inválidas, texto vazio ou com mais de 20 000 caracteres são ignorados, com o motivo;
  - "falar" com a síntese desligada também.
- `python -m newclaw_ivox diagnostico [--json]`: 0 = pronto, 1 = erro, 2 = nada configurado.
- **Testes:**
  - 31 testes de unidade (`python -m unittest discover -s tests -t .`), todos passando.
  - O diagnóstico foi rodado de verdade pela linha de comando: códigos 2, 1 e 64 conferidos.
  - A rodada achou acentos estragados quando a saída vai para um pipe no Windows; consertado.

**Limitações conhecidas:**
- TURN com usuário e senha ainda não tem variável; só a URL é aceita.
- Se o idioma estiver vazio, a leitura do idioma configurado no NewClaw fica para o servidor do harness (Etapa 3).

## Sprint 2 — resultado (29/10/2026)

**Instalação:**
- `pipecat-ai[webrtc,silero,openai,runner]==1.12.0`, a versão da Etapa 0, foi para o `.venv` do projeto, com Python 3.12.10
  no Windows 11.
- Foram 106 pacotes e 537 MB, em 49 s, sem nada fora da pasta.
- A 1.15.0 já existe; trocar de versão fica para depois da voz funcionando, com nova auditoria.
- As versões exatas estão em `requisitos-motor-windows.txt`.

**Funciona no Windows** (era limitação da D1):
- O transporte SmallWebRTC, o VAD Silero, o STT e o TTS compatíveis com OpenAI e o RTVI importam.
- O VAD roda o modelo ONNX de verdade: silêncio dá `QUIET`. Coberto por `tests/test_motor_disponivel.py`, que é pulado sem o
  Pipecat instalado.

**Binários de terceiros** (`ferramentas/inventario_terceiros.py` → `docs/terceiros/windows.md` e `.json`):
- **PyAV 17.1.0, FFmpeg 8.1.1:**
  - foi compilado sem `--enable-gpl`, e o próprio FFmpeg informa "LGPL version 3 or later";
  - mesmo assim, traz `libx264` e `libx265` como DLLs separadas, de origem GPL-2.0+, igual ao pacote de Linux da Etapa 0;
  - traz Opus, que é o áudio do WebRTC.
- **Outras nativas LGPL:**
  - `libsndfile` (soundfile);
  - FFmpeg do `opencv-python-headless`, que o extra `webrtc` do Pipecat exige;
  - LAME, dentro do PyAV.
- **Pacotes Python LGPL:** `soxr` e `num2words`, ambos dependências diretas do Pipecat.
- **Modelos ONNX no Pipecat:** `silero_vad.onnx` e `smart-turn-v3.2-cpu.onnx`.
  - O pacote não traz licença deles; o SHA-256 de cada um está no inventário.
  - A origem e a licença dos modelos continuam a conferir antes de qualquer publicação (L1).
- **Pacotes que vieram sem serem pedidos:**
  - `fastapi-cloud-cli` e `sentry-sdk`, pelo FastAPI;
  - exportadores OpenTelemetry;
  - `pipecat-ai-prebuilt`, pelo extra `runner`; o harness não precisa dele (ADR-030).
- **Telemetria:**
  - o Sentry só é iniciado dentro do comando `fastapi cloud`;
  - o rastreamento do Pipecat tem `enable_tracing=False` como padrão (conferido no código instalado).

**Testes:**
- 34 de 34 com o Pipecat, em três rodadas seguidas.
- Sem o Pipecat: 31 passam e 3 são pulados, com o motivo.

**Limitações:**
- Tudo isto vale para o Windows; o Linux é a Sprint 5.
- Só há o arquivo de versões fixas para Windows.
- O extra `runner` entra só como apoio de desenvolvimento para a Sprint 3. O servidor próprio do harness é a Etapa 3.
