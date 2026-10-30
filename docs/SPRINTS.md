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
| 4 — Síntese local | Kokoro na máquina, frase a frase; o instalador passa a perguntar a voz | OK para baixar o Kokoro (dado em 29/10); a voz é escolha sua | **feita** (29/10) |
| 5 — Fluxo completo + interrupção real | `VAD → STT → user-transcription` e `falar → TTS`; a fala do usuário corta a do motor; prova com microfone de verdade | Você falando no microfone | **feita** (29/10): automático e com a operadora no microfone |
| 6 — Linux | Repetir as provas 2–5 numa máquina Linux | Qual máquina usar (indicação sua) | **feita** (29/10, VPS <IP da VPS>): funciona; sem GPU, o large-v3-turbo é lento demais |

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

## Sprint 4 — resultado (29/10/2026)

**Síntese local:**
- `tts_local.py` monta o `KokoroTTSService` do Pipecat com os arquivos já baixados, a voz escolhida e o idioma configurado.
  - Sem isso, o Pipecat baixaria sozinho para uma pasta dele e falaria em inglês.
  - A voz é conferida no arquivo de vozes antes de usar.
- A síntese é frase a frase (H2), pelo mesmo `run_tts` do pipeline, com o texto preparado por `frases.py`.

**Modelos:**
- `modelos.py` sabe o tamanho do Kokoro (perguntado ao GitHub), baixa e lista as vozes que estão de fato no arquivo.
- Os endereços vêm das constantes do Pipecat instalado.
- O download vai primeiro para um arquivo `.parcial`, para um download interrompido não parecer completo.

**Instalador:**
- passou a perguntar a síntese (nesta máquina, servidor ou desligada) e a voz, numa lista das vozes do arquivo, sem resposta
  padrão;
- pergunta antes de baixar, mostrando o tamanho;
- avisa da licença GPL do phonemizer e do espeak-ng.

**`testar-tts`:**
- sintetiza uma frase de teste no idioma configurado e grava o WAV para ouvir;
- se a transcrição local também estiver ligada, faz a **ida e volta**: fala → Whisper → texto.

**Prova real:**
- **Instalação:** limpa, Windows 11, RTX 5060 Ti. Só o Whisper já estava na pasta de modelos; o Kokoro foi baixado pelo
  instalador.
- **Voz e idioma:** `pf_dora` e `pt-BR`, escolhidos só para o teste. A voz definitiva é escolha da operadora.

| Medida | Resultado |
|---|---|
| Instalação completa (ambiente + Kokoro) | 1 min 10 s; o Kokoro (337 MB) baixou em 11 s |
| Carga do Kokoro (CPU) | 3,4–4,9 s |
| "Pronto!" | pronta em 0,85–1,02 s para 0,7 s de fala |
| "Criei o relatório com três tópicos." | pronta em 0,72–0,78 s para 2,1 s de fala |
| "Quer que eu envie por e-mail?" | pronta em 0,56–0,58 s para 1,6 s de fala |
| Ida e volta (Kokoro → Whisper na GPU) | "Pronto! Criei o relatório com três tópicos. Quer que eu envie por e-**mails**?": só um plural a mais |

O Kokoro roda na CPU (onnxruntime) e, a partir da segunda frase, fica pronto antes de a frase anterior terminar de tocar. A
primeira frase curta é a mais lenta em relação à própria duração.

**Licenças** (inventário refeito a partir da instalação limpa, 123 pacotes):
- **`espeak-ng.dll`** (pacote `espeakng-loader`, que não declara licença): origem GPL-3.0-or-later.
- **`phonemizer` 3.4.0:** GPL-3.0-or-later.
- **`kokoro-onnx` 0.6.1:** MIT.
- **Pesos do Kokoro:** o `hexgrad/Kokoro-82M` declara Apache-2.0 no Hugging Face. O ONNX vem de uma conversão do mesmo autor
  do `kokoro-onnx`.

**Decisão pendente (antes de qualquer publicação):**
- **O ponto:** o phonemizer e o espeak-ng (GPL-3.0) rodam dentro do mesmo processo do motor.
- **Pesa só na distribuição:** o repositório distribui só o código-fonte MIT, e quem instala recebe os pacotes do PyPI.
  Isso é análise técnica, não parecer jurídico.
- **Alternativas:**
  - manter assim;
  - mover a síntese para um subprocesso (a H1 permite);
  - oferecer outro motor local sem espeak-ng.

**Testes:**
- 53 de unidade (3 pulados sem o Pipecat).
- O instalador ganhou o teste da pergunta de síntese.

**Limitações:**
- O Kokoro usa só a CPU. A GPU para ele (`onnxruntime-gpu`) não foi medida.
- A frase de teste existe nos três idiomas aceitos, mas só o pt-BR foi testado.
- A latência no fluxo completo (VAD → STT → NewClaw → TTS) é a Sprint 5.

## Ajuste de 29/10/2026 — voz escolhida na interface (decisão da operadora)

**Por quê:**
- As 54 vozes do Kokoro vêm num arquivo só (`voices-v1.0.bin`), baixado junto com o modelo: já estão todas instaladas.
- Escolher a voz cabe à interface, não ao instalador.

**O que mudou:**
- **`VOZ_TTS_VOZ`:** na síntese local, deixa de ser obrigatória e passa a ser só a voz inicial.
  - Sem ela, o diagnóstico informa que a voz é escolhida na interface.
  - O motor não fala até a escolha, e a resposta fica em texto.
- **Protocolo (versão 2)** — duas mensagens novas da janela:
  - `{"t":"vozes"}` lista as vozes e a atual;
  - `{"t":"voz","d":{"voz":…}}` troca a voz, sem reiniciar.
  - Voz fora do arquivo é recusada.
  - "falar" sem voz escolhida é ignorado, com o motivo.
- **`tts_local.trocar_voz`:** troca pela mesma configuração em execução do Pipecat (`_update_settings`).
  - Medido: 2 ms.
  - O áudio seguinte sai com a voz nova, e o modelo não é recarregado.
- **Instalador:** não pergunta mais a voz. Mostra quantas vozes estão instaladas e não apaga a voz que já estiver no `.env`.
- **`testar-tts --voz NOME`:** ouvir qualquer voz.

**Voz escolhida pela operadora:** `bm_george`, no `.env` local.
- Ela pediu para testar a **mistura** `bm_george` + `pm_alex`.
- O Kokoro permite misturar os vetores de estilo de duas vozes do mesmo arquivo (Apache-2.0); o resultado é uma voz nova,
  que não imita ninguém.
- Amostras 70/30, 50/50 e 30/70 em `amostras-de-voz/`, fora do git.
- Usar uma mistura na interface é passo seguinte, se ela gostar.

**Testes:** 61 de unidade (3 pulados sem o Pipecat).

## Vozes misturadas com nome (29/10/2026, pedido da operadora)

**O arquivo de dados `vozes-misturadas.json`** declara vozes novas:
- cada uma tem nome, rótulo para a interface e pesos que somam 1;
- a voz é a média ponderada dos vetores de estilo de vozes do Kokoro;
- as primeiras três são da operadora:

| Nome | Rótulo na interface | Mistura |
|---|---|---|
| `george-alex-1` | George e Alex — versão 1 | 70% `bm_george` + 30% `pm_alex` |
| `george-alex-2` | George e Alex — versão 2 | 50% + 50% |
| `george-alex-3` | George e Alex — versão 3 | 30% `bm_george` + 70% `pm_alex` |

**Validação** (`misturas.py`):
- nome sem espaço, que não repete nenhuma voz existente;
- rótulo presente;
- pelo menos duas vozes, todas no arquivo instalado;
- pesos positivos, somando 1.

Um arquivo com erro aparece com o motivo; nunca é ignorado em silêncio.

**No motor:**
- as misturas entram na lista de vozes (`modelos --vozes`), antes das 54 do Kokoro;
- elas podem ser a voz inicial e podem ser trocadas em execução como qualquer outra voz.

**Prova:**
- as três falaram a frase de teste;
- o Whisper transcreveu as três de volta igual ao original;
- o áudio de cada versão difere do das outras e do George puro.

Amostras em `amostras-de-voz/george-alex-{1,2,3}.wav`, fora do git.

**Licença:** as vozes de origem são do mesmo arquivo do Kokoro (Apache-2.0), e a mistura não imita nenhuma pessoa.

**Testes:** 66 (4 pulados sem o Pipecat ou sem o Kokoro baixado).

### Usar as vozes misturadas em outros projetos

`python -m newclaw_ivox exportar-vozes --saida arquivo.bin`:
- grava um arquivo de vozes no mesmo formato do `voices-v1.0.bin`: as 54 vozes mais as misturas, num total de 57;
- qualquer programa que use o kokoro-onnx com esse arquivo chama a mistura pelo nome.

Provado com o kokoro-onnx puro, sem o newclaw-ivox: a `george-alex-2` falou.

**Achado (29/10):**
- O Voice-Studio, o bot do OpenClaw no Marte e o NewClaw (`KOKORO_TTS_URL`) usam o servidor Kokoro do Sol
  (`<IP do servidor de vozes>:8199`).
- Esse servidor recusa misturas no pedido: `bm_george(0.7)+pm_alex(0.3)` e `bm_george+pm_alex` voltam 500, "not found".
- O erro é o do kokoro-onnx. Indica que trocar o arquivo de vozes dele pelo exportado deixaria as misturas disponíveis por
  nome para todos esses projetos.
- Essa troca é na infraestrutura da operadora e só acontece com o OK dela.

## Sprint 5 — resultado (29/10/2026)

**Motor** (`python -m newclaw_ivox motor [--eco]`, `motor.py`): o pipeline do Pipecat montado com o que foi configurado e
medido.

    transporte WebRTC (entrada) → VAD Silero → Interrupção → Whisper → [Eco] → Kokoro → transporte (saída)

- **Interrupção pela voz** (processador `Interrupcao`): o VAD detecta a pessoa falando enquanto o motor fala, e o motor
  manda parar (`broadcast_interruption`). O pedido no NewClaw não é cancelado: interromper só corta o áudio (D3).
- **Mensagens da janela pelo RTVI** (`on_client_message` → `controle.interpretar`):
  - `falar` vira `TTSSpeakFrame` frase a frase;
  - `interromper` corta a fala;
  - `vozes` responde a lista, com as misturas e os rótulos;
  - `voz` vira `TTSUpdateSettingsFrame`;
  - o que é inválido volta como erro, com o motivo.
- **Modo eco** (`--eco`), só para testar sem o NewClaw: o motor repete o que ouviu.
- **Whisper:** é carregado uma vez por processo (`WhisperComModeloReaproveitado`) e aquecido na primeira conexão. A carga
  roda numa thread, e o servidor não trava enquanto carrega.
- **Servidor:** o runner de desenvolvimento do Pipecat, em `127.0.0.1:7860` com origem restrita, mais a página de teste
  pronta em `/client`. O servidor próprio do harness é a Etapa 3.

**Prova automática por WebRTC real**:
- **Como:** um cliente `aiortc` faz o papel do navegador e manda um WAV no lugar do microfone. A fala é uma frase longa;
  depois, outra frase por cima da resposta.
- **Fala usada:** gerada pela voz Maria do Windows.
- **Motor:** voz `bm_george`, Whisper `large-v3-turbo` na GPU.

| Medida | Resultado |
|---|---|
| Transcrições chegando à janela (`user-transcription`) | "Bom dia.", "Quero saber a previsão do tempo para amanhã em São Paulo e depois criar um relatório com três tópicos.", "Espera.", "Pode parar um pouco.": iguais ao falado |
| Interrupção pela voz | 3 de 3; a fala do motor parou **4–7 ms** depois de o VAD confirmar a voz da pessoa (o VAD leva ~0,2 s de fala para confirmar, o padrão dele) |
| Depois da interrupção | o motor seguiu normal: ouviu e respondeu a frase seguinte |
| Primeira conexão do processo | pronto em ~12 s (Whisper 6,4 s de carga + aquecimento + Kokoro) |
| Conexões seguintes | pronto em 1,9 s (Whisper reaproveitado: 0,0 s; Kokoro ~1,9 s) |

**Achados:**
- **Pausas viram trechos:** a voz do Windows faz pausa entre frases, e o VAD separa cada uma como um trecho próprio. No eco,
  o motor começa a responder o primeiro trecho e é interrompido pelo seguinte; é o comportamento certo.
- **Sem NewClaw:** a pausa curta que encerra o trecho é o padrão do Pipecat (VAD). Com o NewClaw, quem decide o fim do
  pedido é a janela (Etapa 4), que pode esperar mais.

**Prova com a operadora no microfone** (29/10, Chrome, página de teste em `http://localhost:7860/client`, modo eco):
- 19 falas dela transcritas, por exemplo "Olá, tudo bem com você?", "Estou interrompendo você…", "Agora fiz o teste e
  parou.".
- Ela falou por cima da resposta duas vezes, e o motor parou nas duas, 5 e 6 ms depois de o VAD confirmar a voz. Ela
  confirmou ao ouvir: "parou quando eu falo".

**Achado do teste real, a conferir na janela (Etapa 4):**
- Logo depois das interrupções, o Whisper transcreveu "Você disse?" e "Eu disse.".
- Pode ser ela repetindo, ou o microfone captando a própria voz do motor ("Você disse: …"), apesar do cancelamento de eco
  do navegador.
- Se for a voz do motor, ela pode disparar uma interrupção falsa ou um pedido falso ao NewClaw.
- **A conferir:** com fone de ouvido e sem fone; cancelamento de eco ligado na janela; e, se preciso, ignorar o que chega
  enquanto o motor fala e o VAD não confirma uma voz diferente.

**Testes:** 68; sem o Pipecat, 6 são pulados.

## Sprint 6 — Linux (29/10/2026, na VPS `<IP da VPS>`, a pedido da operadora)

**Máquina** (medida antes de instalar):
- Ubuntu 24.04, Python 3.12.3, Intel Xeon E5-2670 v3 com 4 núcleos, **sem GPU**;
- 7,9 GB de memória, 6,2 GB livres;
- sem `uv`.

É a produção do NewClaw. Por isso:
- pasta separada (`~/newclaw-ivox-teste`);
- porta 7871, nada na 3090;
- NewClaw e PM2 intactos;
- motor desligado no fim de cada teste.

O Marte foi descartado antes de instalar: 451 MB livres de 3,9 GB, swap em uso e o OpenClaw rodando.

| Prova | Resultado |
|---|---|
| Instalador (`python3 instalar.py`, sem `uv`: `venv` + `pip`) | completo em 5 min 45 s, código 0; ambiente 1,1 GB (sem CUDA, porque não há GPU NVIDIA), modelos 1,9 GB |
| Transcrição `large-v3-turbo` na CPU (`cpu/int8`) | texto **idêntico** ao falado, mas 38 s para 10 s de fala (0,3x) |
| Hipótese "o Pipecat usa um núcleo só" | **descartada**: `cpu_threads` 0 e 4 deram o mesmo tempo (38–39 s). O limite é a própria CPU para esse modelo |
| Síntese (`george-alex-2`) e ida e volta | texto idêntico; 1,4–3,4 s por frase, **mais lento que a fala** |
| Frase de 160 caracteres no Kokoro | 12,6 s na VPS (aqui no Windows: 4,1 s) |
| Motor completo por WebRTC (eco) | o motor ouviu e transcreveu, mas **não falou**: o Kokoro ficou 40 s sem produzir áudio enquanto o Whisper transcrevia o trecho seguinte, até o Pipecat encerrar a frase |

**Corrigido nesta sprint:**
- **Espera por frase:** o Pipecat desiste de uma frase se o áudio não chega em 3 s.
  - Agora o motor mede a frase mais longa ao iniciar e espera 2x esse tempo.
  - Medido: 8,2 s no Windows e 25,3 s na VPS.
  - Isso valia também no Windows: uma frase de 160 caracteres já passava dos 3 s.
- **Inventário no Linux:**
  - as bibliotecas têm versão no nome (`….so.165`) e o prefixo `lib`; o filtro perdia o FFmpeg, o x264/x265 e o espeak-ng;
  - agora `docs/terceiros/linux.md` lista as mesmas bibliotecas de origem GPL/LGPL do Windows;
  - no Linux não há pacotes proprietários, porque não há CUDA.
- **Mensagem das vozes no instalador:** separa as 54 do Kokoro das 3 misturadas.

**Conclusão:**
- **Funciona no Linux:** a instalação, a transcrição, a síntese, as misturas e o protocolo funcionam iguais ao Windows.
- **O que não funciona nessa VPS:** com o `large-v3-turbo` e sem GPU, a CPU não dá conta de transcrever e falar ao mesmo
  tempo em tempo real. O motivo é o tamanho do modelo para aquela CPU, não o Linux.
- **O que fazer:** o modelo é escolha de quem instala. O `testar-stt` já avisa quando fica mais lento que a fala. Fica para
  a operadora decidir se mede lá um modelo menor.

**Achado lateral:** o cliente de teste (`aiortc`) na VPS não recebeu as mensagens nem o áudio do motor, e houve erros de
STUN no `aioice`. O motor recebeu o áudio do cliente normalmente. Isso fica a investigar com uma janela de verdade, na
Etapa 4.

# Etapa 3 — servidor do harness (29/10/2026)

Critério da ADR-030 para considerar a Etapa 3 pronta: testes de segurança mostrando que, sem login, a resposta é 401; que
outra origem é recusada; e que o motor de voz não pode ser alcançado pela rede.

**`python -m newclaw_ivox servidor`** (`servidor.py`): um processo só, que atende uma origem (H1).

| Peça | Como |
|---|---|
| Login | `POST /entrar {senha}` → o harness chama `/api/auth/login` do NewClaw; o **token fica no servidor do harness**; o navegador recebe só o cookie `ivox_sessao` (`HttpOnly`, `SameSite=Strict`, `Secure` com HTTPS). `POST /sair` encerra |
| Versão | no login, `GET /api/status` → `contracts.turn` precisa ser 1 (a versão que o harness usa); outra → `409`, sem sessão |
| Idioma | `VOZ_IDIOMA` vence; vazio, o harness lê `language` de `/api/config` no login (rota fora do contrato do turno: se faltar ou trouxer idioma não aceito, a ausência continua reportada) |
| Repasse | `/newclaw/<rota>` → `/api/<rota>` com `Bearer`, **só as rotas do contrato**: `POST chat`, `GET chat/active`, `GET chat/outbox`, `POST chat/auth-decision`, `GET conversations`, `GET conversations/<id>/messages`. O resto (inclusive `/api/status`, que traz nome da máquina e pid) → `404` sem chegar ao NewClaw. Da resposta passam só `Content-Type` e `Retry-After` |
| Origem | todo pedido que muda estado (`/entrar`, `/sair`, `POST /newclaw/*`, `/api/offer`) precisa de `Origin` desta origem; senão `403` |
| Sinalização WebRTC | `POST/PATCH /api/offer` com sessão e origem; o tratador é o do Pipecat (`SmallWebRTCRequestHandler`); cada conexão monta o pipeline do motor. Uma sessão não mexe na conexão de outra (`pc_id` conferido). O motor não tem porta própria |
| HTTPS (H3) | `HARNESS_TLS_CERT` + `HARNESS_TLS_CHAVE`; `HARNESS_HOST` fora de loopback **sem** HTTPS é erro de configuração: o servidor não sobe |
| Cabeçalhos | `nosniff`, `no-referrer`, `X-Frame-Options: DENY`, `no-store`; sem `/docs` nem `/openapi.json` |
| Token revogado | se o NewClaw responder 401 (senha trocada), a sessão do harness acaba também |

**Testes:** 20 de segurança (`tests/test_servidor.py`) com um NewClaw falso (`httpx.MockTransport`), mais as regras de
configuração do servidor. Suíte: 88 testes; sem o Pipecat, 21 são pulados.

**Prova real:**
- **Montagem:** NewClaw isolado (porta 3197, dados próprios, provedor local que não responde, nenhuma cota) e o harness na
  7872. Tudo pelo HTTP de verdade, desligado no fim.

| Prova | Resultado |
|---|---|
| `GET /newclaw/chat/active` sem login | 401 |
| Login de outra origem / senha errada / certa | 403 / 401 / 200 em 2,1 s, `contrato_do_turno: 1`, `idioma: "pt-BR"` (lido do NewClaw) |
| O cookie carrega o token? | não |
| `GET /newclaw/config` (fora do contrato) / `POST /newclaw/chat` de outra origem | 404 / 403 |
| Enviar "olá, newclaw" | 202 em 14–24 ms; estado `pending: true`, `active: []` (a fase `accepted` da Etapa 1) |
| `/cancelar` | "⏹ Operação cancelada." e o turno: "⏹ Pedido interrompido." |
| Histórico | a conversa aparece como `web:etapa3-voz` |
| `/api/offer` sem sessão / com sessão | 401 / 200, e a conexão sobe |
| Pelo WebRTC com sessão | transcrições na janela; `vozes` devolve as 57 vozes e a atual; `falar` sai em 3 frases; `voz_do_filme` → erro "não está entre as 57 disponíveis" |
| Portas do processo | só `127.0.0.1:7872` (as outras duas são o par interno do asyncio no Windows); pelo IP da rede (`<IP desta máquina>:7872`) não conecta |
| Depois de `/sair` | 401 |

**Limitações que ficam:**
- **Token:** o token do NewClaw continua com acesso total e sem expiração (limitação do núcleo). A defesa é ele nunca sair do
  harness e o repasse abrir só o contrato.
- **Sessão:** a sessão do harness vive enquanto o processo estiver de pé, e reiniciar exige novo login. Não há tempo de
  expiração inventado.
- **Limite de requisições:** atrás do harness, todos os usuários saem do mesmo IP e dividem os 120/min do NewClaw
  (contrato).
- **HTTPS:** testado pela regra de configuração, não com um certificado de verdade.
- **Página `/`:** é só um aviso. A janela de voz é a Etapa 4.

# Etapa 4 — janela de voz (30/10/2026)

Autorizada pela operadora em 30/10/2026 ("Pode começar"), com o `npm install` incluído. O visual parte da maquete aprovada
por ela (`docs/referencia-visual/`). Critério da ADR-030: testes da máquina de estados, build reproduzível e inventário de
licenças gerado.

| Sprint | O que entrega | Estado |
|---|---|---|
| 1 — Base da janela | Projeto em `janela/` (React + Vite + TypeScript, versões fixas, publicadas há mais de 2 semanas); o estado da tela derivado de fatos (pessoa falando, motor falando, fase do turno, erro); o controlador da conversa com o motor e o turno trocáveis por falsos; testes | **feita** (30/10): 23 testes |
| 2 — Ligação com o motor e o NewClaw | Cliente do Pipecat com o transporte SmallWebRTC (sem STUN de terceiros); legenda pelos eventos do motor; volume real da pessoa e do motor; turno pelo cliente público do NewClaw (`turn-client.js`, buscado no próprio NewClaw pelo harness); repasse do harness alinhado a `/newclaw/api/...` | **feita** (30/10): 93 testes do harness (5 novos) |
| 3 — Visual da maquete | Tela de entrada (senha do NewClaw); centro círculo/partículas; estado no meio; legenda; foco; mãos livres/segurar espaço; atalhos; sons; vozes; aprovação por clique; tema claro e escuro; o harness serve o build em `/` | **feita** (30/10): 28 testes da janela; build de ~620 kB com as fontes no próprio build |
| 4 — Prova real e licenças | Harness + motor + NewClaw isolado com um provedor falso que responde (sem cota); microfone de verdade com ela; achado do eco ("Você disse?") com e sem fone; inventário de licenças do build | **feita** (30/10): automática, com a operadora no microfone e o eco testado (caixa em volume baixo e fone) |

## Sprint 4 — resultado da prova automática (30/10/2026)

**Montagem:** NewClaw isolado do branch do contrato do turno (porta 3197, dados próprios), com um provedor falso no formato
do Ollama que responde um texto fixo (nenhuma cota usada); harness na 7860 servindo o build da janela; navegador do
ambiente de desenvolvimento (sem microfone liberado).

| Prova | Resultado |
|---|---|
| Entrada com a senha | o cookie da sessão; a janela carrega o `turn-client.js` do próprio NewClaw |
| Motor de voz na 1ª conexão | Whisper `large-v3-turbo` na GPU em 24,5 s (carga 17,4 s); Kokoro pronto com `bm_george` |
| Motor na 2ª conexão | voz ligada em 5,6 s (modelo reaproveitado no processo) |
| Lista de vozes | as 57, com as três misturas George e Alex no topo |
| Mensagem escrita → resposta falada | na fila 0,1 s → pensando 1,7 s → falando 2,8 s → pronto 12,2 s (fala inteira) |
| Parar durante a fala | de "falando" para "pronto" 16 ms depois do clique; `/cancelar` enviado ao NewClaw |
| Sem microfone | a janela não cai: avisa "o navegador não deu permissão ao microfone" e segue só com texto, com a resposta falada |

**Achados corrigidos durante a prova:**
1. **Código de terceiros em tempo de execução.** O gerenciador de mídia padrão do transporte SmallWebRTC
   (`DailyMediaManager`, do daily-js) baixa um script do CDN do Daily ao abrir, e o daily-js ainda manda telemetria ao
   Sentry. A política de conteúdo do harness bloqueou as duas coisas. Correção: `janela/src/microfone.ts`, um gerenciador
   próprio que usa só `getUserMedia` (com cancelamento de eco, supressão de ruído e ganho automático) e mede o volume
   localmente. Numa aba limpa, nenhum pedido a terceiros. O código do daily-js continua no pacote (o transporte o importa),
   mas não é executado.
2. **Passagem de 26–50 ms por "pronto"** entre "na fila" e "pensando" (o NewClaw anuncia `finished` antes de a entrega ser
   retirada da outbox). A fase anterior agora vale até a entrega chegar; teste na suíte.

**Licenças do build:** `docs/terceiros/janela.md`, gerado por `janela/ferramentas/licencas.mjs`: 29 pacotes de produção —
22 MIT, 3 BSD-2-Clause, 2 OFL-1.1 (fontes), 1 Apache-2.0, 1 0BSD. Nenhum GPL.

**Falta (precisa da operadora):** falar no microfone pela janela, no Chrome dela (`http://127.0.0.1:7860`, `localhost` é
página segura), e conferir o achado do eco ("Você disse?") com e sem fone de ouvido.

## Sprint 4 — prova com a operadora no microfone (30/10/2026)

Chrome dela, `http://127.0.0.1:7860`, NewClaw isolado com o provedor de teste. Cinco achados, todos corrigidos e com teste:

| Achado | Causa | Correção (commit) |
|---|---|---|
| A senha certa era recusada do segundo login em diante | o harness guardava o cookie do NewClaw; com cookie e sem Origin, a proteção contra CSRF do NewClaw recusava o login | o harness descarta os cookies do NewClaw (0e2c905) |
| Parecia que o microfone não funcionava | o botão começava aberto e cada clique o silenciava; após F5 o Chrome deixa o áudio suspenso até o primeiro clique; o Pipecat encerrava a ligação após 5 min parada | linha de situação do microfone, áudio liberado no 1º gesto, sem limite de ociosidade (0254249) |
| O centro não reagia à voz dela, só à do NewClaw | volume em RMS cru (fala ≈ 0,01–0,1) e "Ouvindo" nunca acendia: o RTVI só manda `user-started-speaking` com agregação de LLM, que o motor não tem | volume em dB (e4b4d8a); o motor emite o aviso de fala junto com o VAD (96b7ff2) |
| A tela saía de "Ouvindo" a cada respiro | o VAD diz "parou" com 0,2 s de silêncio | a tela segue o critério do envio (1455047) |
| Reconhecimento com erros ("Dorme de ferro") | cada pedaço de 0,2 s ia sozinho para o Whisper, sem contexto | trecho fecha com 0,8 s; espera da janela 0,6 s; ~1,4 s até o envio, como antes (9bbd5a8) |

**Depois das correções (palavras dela: "Agora eu acho que ficou bom"):** "Quais os filmes que aparece o Jarvis no Homem de
Ferro?" e "Qual o filme do Homem de Ferro que mais aparece o Jarvis?" transcritas inteiras e certas.

**Eco (30/10, 01:58–02:00):** com a caixa em volume baixo (madrugada) e com fone, o motor não detectou voz nenhuma durante as três falas do NewClaw, e não houve interrupção nem pedido falso. O cancelamento de eco do Chrome (pedido explicitamente pela janela em `getUserMedia`) segurou. **Falta:** repetir com a caixa em volume alto.
