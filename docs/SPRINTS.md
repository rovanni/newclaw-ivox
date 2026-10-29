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
| 2 — Pipecat no Windows | Instalar o Pipecat num ambiente isolado (`.venv` do projeto); conferir os binários (PyAV/FFmpeg e codecs, ONNX) e as licenças instaladas; fixar as versões | **OK para instalar** (~centenas de MB no `.venv`, nada fora da pasta) | a fazer |
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
