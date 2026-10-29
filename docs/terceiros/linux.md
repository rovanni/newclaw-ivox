# Terceiros no ambiente do motor de voz — Linux-6.8.0-147-generic-x86_64-with-glibc2.39

Gerado por `ferramentas/inventario_terceiros.py` (Python 3.12.3). Levantamento técnico, não parecer jurídico: registra o que cada pacote declara e o que está no disco.

## Bibliotecas nativas de origem GPL/LGPL

| Pacote | Arquivo | Licença de origem |
|---|---|---|
| av | `libavcodec-c3f15378.so.62.28.101` | LGPL (FFmpeg; ver a configuração do PyAV abaixo e o LICENSE-3RD-PARTY.txt do OpenCV) |
| av | `libmp3lame-8f9e436f.so.0.0.0` | LGPL-2.0-or-later (LAME) |
| av | `libx264-d6533a8d.so.165` | GPL-2.0-or-later (x264) |
| av | `libx265-f5385bb8.so.216` | GPL-2.0-or-later (x265) |
| espeakng-loader | `libespeak-ng.so` | GPL-3.0-or-later (eSpeak NG; carregado no processo pelo phonemizer) |
| espeakng-loader | `libespeak-ng.so.1` | GPL-3.0-or-later (eSpeak NG; carregado no processo pelo phonemizer) |
| espeakng-loader | `libespeak-ng.so.1.52.0` | GPL-3.0-or-later (eSpeak NG; carregado no processo pelo phonemizer) |
| opencv-python-headless | `libavcodec-57aca189.so.62.28.102` | LGPL (FFmpeg; ver a configuração do PyAV abaixo e o LICENSE-3RD-PARTY.txt do OpenCV) |
| soundfile | `libsndfile_x86_64.so` | LGPL-2.1-or-later (libsndfile) |

## Pacotes com licença proprietária

Nenhum.

## FFmpeg dentro do PyAV

- PyAV 17.1.0; licença informada pelo próprio FFmpeg: **LGPL version 3 or later**; `--enable-gpl`: **não**.
- Codecs de licença GPL presentes: libx264, libx264rgb, libx265.
- Opus (áudio do WebRTC): sim.
- Bibliotecas externas habilitadas: libdav1d, libmp3lame, libopencore-amrnb, libopencore-amrwb, libopus, libsvtav1, libvpl, libvpx, libwebp, libx264, libx265, libxcb.

## Modelos ONNX dentro do Pipecat

| Arquivo | Bytes | SHA-256 | Licença |
|---|---|---|---|
| `audio/turn/smart_turn/data/smart-turn-v3.2-cpu.onnx` | 8679182 | `2bb026316b14a660…` | não declarada (o pacote não traz arquivo de licença do modelo) |
| `audio/vad/data/silero_vad.onnx` | 2327524 | `597d30b3ec076608…` | não declarada (o pacote não traz arquivo de licença do modelo) |

## Pacotes (121)

| Pacote | Versão | Licença declarada | Nativas |
|---|---|---|---|
| agent-detector | 2.0.0 | MIT |  |
| aiofiles | 25.1.0 | Apache-2.0 |  |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |  |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT | 4 |
| aioice | 0.10.2 | BSD-3-Clause |  |
| aiortc | 1.15.0 | BSD-3-Clause |  |
| aiosignal | 1.4.0 | Apache 2.0 |  |
| annotated-doc | 0.0.5 | MIT |  |
| annotated-types | 0.8.0 | MIT |  |
| anyio | 4.15.1 | MIT |  |
| attrs | 26.1.0 | MIT |  |
| av | 17.1.0 | BSD-3-Clause | 68 |
| certifi | 2026.10.23 | MPL-2.0 |  |
| cffi | 2.1.1 | MIT-0 | 1 |
| charset-normalizer | 3.5.2 | MIT | 2 |
| click | 8.5.0 | BSD-3-Clause |  |
| cloudpickle | 3.1.2 | BSD-3-Clause |  |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | 1 |
| ctranslate2 | 4.8.4 | MIT | 3 |
| detect-installer | 0.2.1 | 0BSD |  |
| dlinfo | 2.0.0 | MIT |  |
| dnspython | 2.9.1 | ISC |  |
| docopt | 0.6.2 | MIT |  |
| docstring_parser | 0.18.0 | MIT |  |
| email-validator | 2.3.0 | Unlicense |  |
| espeakng-loader | 0.2.4 | não declarada | 3 |
| fastapi | 0.162.0 | MIT |  |
| fastapi-cli | 0.0.32 | MIT |  |
| fastapi-cloud-cli | 0.26.0 | MIT |  |
| fastar | 0.12.0 | MIT | 1 |
| faster-whisper | 1.2.1 | MIT |  |
| filelock | 4.2.4 | MIT |  |
| flatbuffers | 25.12.19 | Apache 2.0 |  |
| frozenlist | 1.8.0 | Apache-2.0 | 1 |
| fsspec | 2026.9.0 | BSD-3-Clause |  |
| google-crc32c | 1.9.0 | Apache-2.0 | 2 |
| googleapis-common-protos | 1.76.0 | Apache-2.0 |  |
| h11 | 0.16.0 | MIT |  |
| hf-xet | 1.7.1 | Apache-2.0 | 1 |
| httpcore | 1.0.9 | BSD-3-Clause |  |
| httpcore2 | 2.16.0 | BSD-3-Clause |  |
| httptools | 0.9.0 | MIT | 2 |
| httpx | 0.28.1 | BSD-3-Clause |  |
| httpx2 | 2.16.0 | BSD-3-Clause |  |
| huggingface_hub | 2.4.0 | Apache-2.0 |  |
| idna | 3.20 | BSD-3-Clause |  |
| ifaddr | 0.2.0 | MIT |  |
| itsdangerous | 2.2.0 | BSD License |  |
| Jinja2 | 3.1.6 | BSD License |  |
| jiter | 0.18.0 | MIT | 1 |
| joblib | 1.6.0 | BSD-3-Clause |  |
| kokoro-onnx | 0.6.1 | não declarada |  |
| llvmlite | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception | 1 |
| loguru | 0.7.3 | MIT License |  |
| loudness | 0.2.0 | MIT | 1 |
| Markdown | 3.11.2 | BSD-3-Clause |  |
| markdown-it-py | 4.2.0 | MIT License |  |
| MarkupSafe | 3.0.4 | BSD-3-Clause | 1 |
| mdurl | 0.1.2 | MIT License |  |
| mpmath | 1.3.0 | BSD |  |
| multidict | 7.2.1 | Apache-2.0 | 2 |
| newclaw-ivox | 0.1.0 | MIT License (texto longo no metadado) |  |
| num2words | 0.5.14 | LGPL |  |
| numba | 0.68.1 | BSD | 14 |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 22 |
| onnxruntime | 1.24.4 | MIT License | 3 |
| openai | 3.41.0 | Apache-2.0 |  |
| opencv-python-headless | 4.14.0.94 | Apache 2.0 | 15 |
| opentelemetry-api | 1.45.2 | Apache-2.0 |  |
| opentelemetry-exporter-http-transport | 0.66b2 | Apache-2.0 |  |
| opentelemetry-exporter-otlp-common | 0.66b2 | Apache-2.0 |  |
| opentelemetry-exporter-otlp-proto-common | 1.45.2 | Apache-2.0 |  |
| opentelemetry-exporter-otlp-proto-http | 1.45.2 | Apache-2.0 |  |
| opentelemetry-proto | 1.45.2 | Apache-2.0 |  |
| opentelemetry-sdk | 1.45.2 | Apache-2.0 |  |
| opentelemetry-semantic-conventions | 0.66b2 | Apache-2.0 |  |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |  |
| phonemizer | 3.4.0 | GNU GENERAL PUBLIC LICENSE (texto longo no metadado) |  |
| pillow | 12.3.0 | MIT-CMU | 26 |
| pip | 24.0 | MIT |  |
| pipecat-ai | 1.12.0 | BSD-2-Clause |  |
| pipecat-ai-prebuilt | 1.3.0 | BSD 2-Clause License |  |
| propcache | 0.5.4 | Apache-2.0 | 1 |
| protobuf | 6.33.6 | 3-Clause BSD License | 1 |
| pycparser | 3.12 | BSD-3-Clause |  |
| pydantic | 2.14.2 | MIT |  |
| pydantic-extra-types | 2.11.1 | MIT |  |
| pydantic-settings | 2.16.2 | MIT |  |
| pydantic_core | 2.50.2 | MIT | 1 |
| pyee | 16.0.0 | MIT |  |
| Pygments | 2.21.0 | BSD-2-Clause |  |
| pylibsrtp | 1.0.0 | BSD-3-Clause | 1 |
| pyOpenSSL | 26.4.0 | Apache License, Version 2.0 |  |
| python-dotenv | 1.2.4 | BSD-3-Clause |  |
| python-multipart | 0.0.32 | Apache-2.0 |  |
| PyYAML | 6.0.3 | MIT | 1 |
| requests | 2.34.2 | Apache-2.0 |  |
| resampy | 0.4.3 | ISC |  |
| rich | 15.0.0 | MIT |  |
| rich-toolkit | 0.20.6 | MIT |  |
| rignore | 0.8.1 | MIT | 1 |
| sentencex | 1.0.31 | MIT | 1 |
| sentry-sdk | 2.73.0 | MIT |  |
| shellingham | 1.5.4 | ISC License |  |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |  |
| soundfile | 0.13.1 | BSD 3-Clause License | 1 |
| soxr | 1.0.0 | LGPL-2.1-or-later | 1 |
| starlette | 1.10.0 | BSD-3-Clause |  |
| sympy | 1.14.0 | BSD |  |
| tokenizers | 0.23.3 | Apache Software License | 1 |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |  |
| truststore | 0.10.5 | MIT |  |
| typer | 0.27.3 | MIT |  |
| typing-inspection | 0.4.4 | MIT |  |
| typing_extensions | 4.16.0 | PSF-2.0 |  |
| urllib3 | 2.8.0 | MIT |  |
| uvicorn | 0.54.0 | BSD-3-Clause |  |
| uvloop | 0.23.0 | MIT License | 1 |
| watchfiles | 1.3.0 | MIT | 1 |
| websockets | 17.3 | BSD-3-Clause | 1 |
| yarl | 1.25.1 | Apache-2.0 | 1 |

