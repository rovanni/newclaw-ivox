# newclaw-ivox

Interface de voz opcional para o [NewClaw](https://github.com/rovanni/NewClaw): uma janela que ouve, mostra o andamento
das tarefas e fala as respostas. "ivox" vem de "interface de voz", e "vox" porque a interface pode ter várias vozes.

É um **harness**: usa o NewClaw só pelas rotas públicas e pelo contrato do turno (`docs/CONTRATO_DO_TURNO.md` no NewClaw).
O NewClaw não depende dele (ADR-030 e ADR-031 do NewClaw). O harness não tem modelo de linguagem, memória nem persona: quem
pensa, lembra e executa é o NewClaw.

A voz roda **na sua máquina**: a transcrição usa o Whisper local (e a sua GPU, se houver) e a síntese usa o Kokoro local,
sem depender de outro computador. Um servidor externo continua possível, se você preferir.

## Estado

Em desenvolvimento, em sprints — ver [docs/SPRINTS.md](docs/SPRINTS.md).
- **Pronto:** instalador; transcrição local, com GPU medida; síntese local (Kokoro), frase a frase.
- **Ainda não:** janela e fluxo completo com microfone (Sprint 5) e Linux (Sprint 6).

## Instalar

Precisa do Python 3.10 ou mais novo. Na pasta do projeto:

```bash
python instalar.py
```

O instalador:
- mede a máquina (sistema, GPU, espaço);
- pergunta onde transcrever, qual modelo e qual idioma, sem escolher nada por você;
- instala o necessário na pasta `.venv` deste projeto;
- baixa o modelo para `modelos/`;
- grava o `.env` e testa no final.

Antes de cada instalação ou download, ele mostra o que vai fazer e pergunta. Para só ver os passos, sem executar nada:

```bash
python instalar.py --simular
```

Licenças de terceiros: leia [docs/terceiros/windows.md](docs/terceiros/windows.md) antes de instalar.
- O PyAV traz bibliotecas de origem GPL (`libx264`, `libx265`) e outras LGPL.
- As bibliotecas CUDA da NVIDIA têm licença proprietária.
- A síntese local usa o phonemizer e o espeak-ng, de licença GPL-3.0.

Tudo vem do PyPI e do Hugging Face direto para a sua máquina; este repositório não redistribui nada disso.

## Conferir

```bash
python -m newclaw_ivox diagnostico
```

Saída `0` = pronto, `1` = erro de configuração, `2` = nada configurado. `--json` dá a mesma informação para outro programa
ler. A chave nunca aparece, só se ela existe.

Com o Python do `.venv` (`.venv/Scripts/python` no Windows, `.venv/bin/python` no Linux e no macOS):

```bash
.venv/Scripts/python -m newclaw_ivox modelos
```

lista os modelos de transcrição e o tamanho de cada um.

```bash
.venv/Scripts/python -m newclaw_ivox testar-stt --audio fala.wav
```

transcreve um WAV mono de 16 bits e 16 kHz e mede o tempo.

```bash
.venv/Scripts/python -m newclaw_ivox testar-tts
```

fala uma frase de teste com a voz configurada, grava o áudio para você ouvir e, se a transcrição local estiver ligada,
transcreve de volta para comparar.

## Testes

```bash
python -m unittest discover -s tests -t .
```

Sem o `.venv`, os testes do motor são pulados e dizem por quê.

## Licença

MIT (código deste repositório). As dependências de terceiros têm licenças próprias; o inventário e os avisos vêm antes de
qualquer publicação (ADR-030, decisão L1). Este projeto não declara conformidade jurídica.
