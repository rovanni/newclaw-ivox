# Terceiros no ambiente do motor de voz — Windows-11-10.0.26200-SP0

Gerado por `ferramentas/inventario_terceiros.py` (Python 3.12.10). Levantamento técnico, não parecer jurídico: registra o que cada pacote declara e o que está no disco.

## Bibliotecas nativas de origem GPL/LGPL

| Pacote | Arquivo | Licença de origem |
|---|---|---|
| av | `avcodec-62-0f4d449c1bbaaa5eeb9f8a10b4cc7e85.dll` | LGPL (FFmpeg do PyAV; ver configuração abaixo) |
| av | `libmp3lame-0-7a64829d195e8823e9b581d29ebd8775.dll` | LGPL-2.0-or-later (LAME) |
| av | `libx264-165-71900781b680e0e06a1b966b46fee000.dll` | GPL-2.0-or-later (x264) |
| av | `libx265-7e74dd5103fd9dad5114dffeefd474ce.dll` | GPL-2.0-or-later (x265) |
| opencv-python-headless | `opencv_videoio_ffmpeg4140_64.dll` | LGPL (FFmpeg do OpenCV; ver LICENSE-3RD-PARTY.txt do pacote) |
| soundfile | `libsndfile_x64.dll` | LGPL-2.1-or-later (libsndfile) |

## Pacotes com licença proprietária

Instalados do PyPI na máquina de quem usa; não podem ser redistribuídos com o harness.

- nvidia-cublas-cu12 12.9.2.10: LicenseRef-NVIDIA-Proprietary
- nvidia-cuda-nvrtc-cu12 12.9.86: LicenseRef-NVIDIA-Proprietary
- nvidia-cudnn-cu12 9.27.0.42: LicenseRef-NVIDIA-Proprietary

## FFmpeg dentro do PyAV

- PyAV 17.1.0; licença informada pelo próprio FFmpeg: **LGPL version 3 or later**; `--enable-gpl`: **não**.
- Codecs de licença GPL presentes: libx264, libx264rgb, libx265.
- Opus (áudio do WebRTC): sim.
- Bibliotecas externas habilitadas: libdav1d, libmp3lame, libopencore-amrnb, libopencore-amrwb, libopus, libsvtav1, libvpl, libvpx, libwebp, libx264, libx265.

## Modelos ONNX dentro do Pipecat

| Arquivo | Bytes | SHA-256 | Licença |
|---|---|---|---|
| `audio/turn/smart_turn/data/smart-turn-v3.2-cpu.onnx` | 8679182 | `2bb026316b14a660…` | não declarada (o pacote não traz arquivo de licença do modelo) |
| `audio/vad/data/silero_vad.onnx` | 2327524 | `597d30b3ec076608…` | não declarada (o pacote não traz arquivo de licença do modelo) |

## Pacotes (118)

| Pacote | Versão | Licença declarada | Nativas |
|---|---|---|---|
| agent-detector | 2.0.0 | MIT |  |
| aiofiles | 25.1.0 | Apache-2.0 |  |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |  |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT |  |
| aioice | 0.10.2 | BSD-3-Clause |  |
| aiortc | 1.15.0 | BSD-3-Clause |  |
| aiosignal | 1.4.0 | Apache 2.0 |  |
| annotated-doc | 0.0.5 | MIT |  |
| annotated-types | 0.8.0 | MIT |  |
| anyio | 4.15.1 | MIT |  |
| attrs | 26.1.0 | MIT |  |
| av | 17.1.0 | BSD-3-Clause | 25 |
| certifi | 2026.10.23 | MPL-2.0 |  |
| cffi | 2.1.1 | MIT-0 |  |
| charset-normalizer | 3.5.2 | MIT |  |
| click | 8.5.0 | BSD-3-Clause |  |
| colorama | 0.4.6 | BSD License |  |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |  |
| ctranslate2 | 4.8.4 | MIT | 3 |
| detect-installer | 0.2.1 | 0BSD |  |
| dnspython | 2.9.0 | ISC |  |
| docopt | 0.6.2 | MIT |  |
| docstring_parser | 0.18.0 | MIT |  |
| email-validator | 2.3.0 | Unlicense |  |
| fastapi | 0.162.0 | MIT |  |
| fastapi-cli | 0.0.32 | MIT |  |
| fastapi-cloud-cli | 0.26.0 | MIT |  |
| fastar | 0.12.0 | MIT |  |
| faster-whisper | 1.2.1 | MIT |  |
| filelock | 4.2.4 | MIT |  |
| flatbuffers | 25.12.19 | Apache 2.0 |  |
| frozenlist | 1.8.0 | Apache-2.0 |  |
| fsspec | 2026.9.0 | BSD-3-Clause |  |
| google-crc32c | 1.9.0 | Apache-2.0 | 1 |
| googleapis-common-protos | 1.76.0 | Apache-2.0 |  |
| h11 | 0.16.0 | MIT |  |
| hf-xet | 1.7.1 | Apache-2.0 |  |
| httpcore | 1.0.9 | BSD-3-Clause |  |
| httpcore2 | 2.16.0 | BSD-3-Clause |  |
| httptools | 0.9.0 | MIT |  |
| httpx | 0.28.1 | BSD-3-Clause |  |
| httpx2 | 2.16.0 | BSD-3-Clause |  |
| huggingface_hub | 2.4.0 | Apache-2.0 |  |
| idna | 3.20 | BSD-3-Clause |  |
| ifaddr | 0.2.0 | MIT |  |
| itsdangerous | 2.2.0 | BSD License |  |
| Jinja2 | 3.1.6 | BSD License |  |
| jiter | 0.18.0 | MIT |  |
| llvmlite | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception | 2 |
| loguru | 0.7.3 | MIT License |  |
| loudness | 0.2.0 | MIT |  |
| Markdown | 3.11.2 | BSD-3-Clause |  |
| markdown-it-py | 4.2.0 | MIT License |  |
| MarkupSafe | 3.0.4 | BSD-3-Clause |  |
| mdurl | 0.1.2 | MIT License |  |
| mpmath | 1.3.0 | BSD |  |
| multidict | 7.2.1 | Apache-2.0 |  |
| newclaw-ivox | 0.1.0 | MIT License (texto longo no metadado) |  |
| num2words | 0.5.14 | LGPL |  |
| numba | 0.68.1 | BSD |  |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 2 |
| nvidia-cublas-cu12 | 12.9.2.10 | LicenseRef-NVIDIA-Proprietary | 3 |
| nvidia-cuda-nvrtc-cu12 | 12.9.86 | LicenseRef-NVIDIA-Proprietary | 3 |
| nvidia-cudnn-cu12 | 9.27.0.42 | LicenseRef-NVIDIA-Proprietary | 10 |
| onnxruntime | 1.24.4 | MIT License | 2 |
| openai | 3.41.0 | Apache-2.0 |  |
| opencv-python-headless | 4.14.0.94 | Apache 2.0 | 1 |
| opentelemetry-api | 1.45.2 | Apache-2.0 |  |
| opentelemetry-exporter-http-transport | 0.66b2 | Apache-2.0 |  |
| opentelemetry-exporter-otlp-common | 0.66b2 | Apache-2.0 |  |
| opentelemetry-exporter-otlp-proto-common | 1.45.2 | Apache-2.0 |  |
| opentelemetry-exporter-otlp-proto-http | 1.45.2 | Apache-2.0 |  |
| opentelemetry-proto | 1.45.2 | Apache-2.0 |  |
| opentelemetry-sdk | 1.45.2 | Apache-2.0 |  |
| opentelemetry-semantic-conventions | 0.66b2 | Apache-2.0 |  |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |  |
| pillow | 12.3.0 | MIT-CMU |  |
| pipecat-ai | 1.12.0 | BSD-2-Clause |  |
| pipecat-ai-prebuilt | 1.3.0 | BSD 2-Clause License |  |
| propcache | 0.5.4 | Apache-2.0 |  |
| protobuf | 6.33.6 | 3-Clause BSD License |  |
| pycparser | 3.12 | BSD-3-Clause |  |
| pydantic | 2.14.2 | MIT |  |
| pydantic-extra-types | 2.11.1 | MIT |  |
| pydantic-settings | 2.16.2 | MIT |  |
| pydantic_core | 2.50.2 | MIT |  |
| pyee | 16.0.0 | MIT |  |
| Pygments | 2.21.0 | BSD-2-Clause |  |
| pylibsrtp | 1.0.0 | BSD-3-Clause |  |
| pyOpenSSL | 26.4.0 | Apache License, Version 2.0 |  |
| python-dotenv | 1.2.4 | BSD-3-Clause |  |
| python-multipart | 0.0.32 | Apache-2.0 |  |
| PyYAML | 6.0.3 | MIT |  |
| requests | 2.34.2 | Apache-2.0 |  |
| resampy | 0.4.3 | ISC |  |
| rich | 15.0.0 | MIT |  |
| rich-toolkit | 0.20.6 | MIT |  |
| rignore | 0.8.1 | MIT |  |
| sentencex | 1.0.31 | MIT |  |
| sentry-sdk | 2.73.0 | MIT |  |
| shellingham | 1.5.4 | ISC License |  |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |  |
| soundfile | 0.13.1 | BSD 3-Clause License | 1 |
| soxr | 1.0.0 | LGPL-2.1-or-later |  |
| starlette | 1.10.0 | BSD-3-Clause |  |
| sympy | 1.14.0 | BSD |  |
| tokenizers | 0.23.3 | Apache Software License |  |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |  |
| truststore | 0.10.5 | MIT |  |
| typer | 0.27.3 | MIT |  |
| typing-inspection | 0.4.4 | MIT |  |
| typing_extensions | 4.16.0 | PSF-2.0 |  |
| urllib3 | 2.8.0 | MIT |  |
| uvicorn | 0.54.0 | BSD-3-Clause |  |
| watchfiles | 1.3.0 | MIT |  |
| websockets | 17.3 | BSD-3-Clause |  |
| win32_setctime | 1.2.1 | MIT license |  |
| yarl | 1.25.1 | Apache-2.0 |  |

