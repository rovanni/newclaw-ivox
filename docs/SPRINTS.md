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
| 3 — Instalador + transcrição local | `python instalar.py`: mede a máquina, pergunta, instala, baixa o modelo e testa; transcrição com faster-whisper, GPU medida | OK para instalar e baixar; modelo escolhido por você (`large-v3-turbo`, 29/10) | **feita** (29/10) |
| 4 — Síntese local | Kokoro na máquina, frase a frase; o instalador passa a perguntar a voz | OK para baixar o Kokoro | a fazer |
| 5 — Fluxo completo + interrupção real | `VAD → STT → user-transcription` e `falar → TTS`; a fala do usuário corta a do motor; prova com microfone de verdade | Você falando no microfone | a fazer |
| 6 — Linux | Repetir as provas 2–5 numa máquina Linux | Qual máquina usar (indicação sua) | a fazer |

Revisão de 29/10/2026 (ADR-030 do NewClaw, "voz na máquina do usuário"): as sprints 3 a 6 substituem o plano anterior,
que dependia de servidores de transcrição e síntese noutra máquina. A ideia do instalador já nesta sprint é da operadora:
cada sprint é testada do jeito que uma pessoa nova vai instalar.

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

## Sprint 3 — resultado (29/10/2026)

**Instalador** (`python instalar.py`, ou `--simular` para só ver os passos):
- **Base:** só a biblioteca padrão, um arquivo para Windows, Linux e macOS. Segue os passos do instalador do NewClaw: medir →
  instalar → baixar modelo → configurar → testar → resumo.
- **Mede:** sistema, Python, GPU NVIDIA (`nvidia-smi`) e espaço livre.
- **Pergunta, sem resposta padrão:**
  - onde transcrever: nesta máquina, num servidor ou desligada;
  - qual modelo, com a lista vinda do faster-whisper e os tamanhos medidos na hora no Hugging Face;
  - qual idioma.
- **Instala** no `.venv` os extras `motor` e `stt-local`, mais o `cuda` só quando mede uma GPU NVIDIA. Antes, mostra o que
  vai instalar e as licenças, e pergunta.
- **Baixa** o modelo para `modelos/` só depois de mostrar o tamanho e perguntar; se o modelo já existe, não baixa de novo.
- **Grava** o `.env` só nas chaves de voz e preserva o resto.
- **No final**, roda o diagnóstico e `testar-stt`.

**Transcrição local:**
- `stt_local.py` monta o `WhisperSTTService` do Pipecat com modelo, idioma, dispositivo e tipo de cálculo sempre explícitos.
  Sem isso, o Pipecat cairia no padrão dele: um modelo só de inglês, com o idioma em inglês.
- `dispositivo.py` mede a GPU pelo CTranslate2 e registra as DLLs CUDA do pip no Windows.
  - O tipo de cálculo é escolhido entre os medidos.
  - Nesta máquina: `cuda/float16`.

**Prova real** — instalação limpa (cópia do repositório sem `.venv`), Windows 11, RTX 5060 Ti 16 GB, `large-v3-turbo`:

| Medida | Resultado |
|---|---|
| Instalação completa (ambiente + modelo de 1,5 GB) | 1 min 53 s; o modelo baixou em 37 s. Ambiente: 2,6 GB |
| Carga do modelo na GPU | 8,5–9,3 s |
| Primeiríssima transcrição na placa (a NVIDIA compila e guarda os kernels) | 19,9 s, uma vez só por máquina |
| Primeira transcrição de cada processo (aquecimento) | 1,9–3,4 s |
| Uso, 10 s de fala (frase pt-BR gerada pela voz Maria do Windows) | 0,54–0,62 s (~18x mais rápido que a fala), texto idêntico ao falado |
| Mesmo modelo na CPU (`cpu/int8`) | 14,3–14,5 s para 10 s de fala: **mais lento que a fala** |

**Achados:**
- **Silêncio:**
  - o Whisper inventa texto em silêncio ("Obrigado.");
  - o primeiro teste do instalador esperava vazio, e foi corrigido: agora mede o tempo, sem julgar o texto;
  - no uso, o VAD só entrega trechos com fala.
- **Ordem das mensagens:** saía trocada quando a saída ia para um pipe; consertado com `flush`.
- **Licença proprietária:** as bibliotecas CUDA (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, `nvidia-cuda-nvrtc-cu12`) têm
  licença proprietária da NVIDIA.
  - Vêm do PyPI para a máquina e não podem ser redistribuídas.
  - O instalador diz isso, e o inventário ganhou uma seção para elas.
- **Licença do modelo:** o `large-v3-turbo` (`mobiuslabsgmbh/faster-whisper-large-v3-turbo`, conversão do
  `openai/whisper-large-v3-turbo`) declara MIT no Hugging Face.

**Testes:**
- 52 de unidade; sem o Pipecat, 3 deles são pulados. Com o Pipecat (`.venv`), passam os 52.
- Os de instalador cobrem: escolha sem padrão, recusa sem executar nada, `.env` preservado e chave oculta.

**Limitações e próximos passos:**
- **Sem GPU:** o `large-v3-turbo` na CPU é mais lento que a fala. O `testar-stt` agora diz isso e sugere modelo menor ou GPU,
  sem escolher por ninguém.
- **Aquecimento:** o motor deve aquecer o modelo ao iniciar (Sprint 5), para a primeira fala não pagar os ~2–3 s.
- **Avisos de terceiros na tela:** o do Hugging Face sobre requisições sem token e o do Pipecat "pt-BR not verified; usando
  'pt'". Ficam, porque são das bibliotecas.
- **Inventário:** `docs/terceiros/windows.md` foi refeito a partir da instalação limpa (117 pacotes).
