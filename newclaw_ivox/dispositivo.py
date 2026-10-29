"""Onde a voz vai rodar: medido nesta máquina, nunca suposto (AGENTS.md do NewClaw, regra 11).

Duas medições:
- `medir_sistema()` usa só a biblioteca padrão, para o instalador decidir o que instalar antes de existir o `.venv`;
- `medir_motor()` pergunta ao CTranslate2 (o motor do faster-whisper) quantas GPUs CUDA ele usa e com quais tipos de
  cálculo. É ela que vale para rodar.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ordem de preferência entre os tipos que a medição disser que existem. Na GPU, meia precisão é o uso normal do
# Whisper; na CPU, int8 é o que o CTranslate2 acelera. Só se escolhe dentro do que foi medido.
PREFERENCIA = {
    "cuda": ("float16", "int8_float16", "bfloat16", "float32"),
    "cpu": ("int8", "int8_float32", "float32"),
}


@dataclass(frozen=True)
class Sistema:
    sistema: str
    python: str
    gpus_nvidia: tuple[str, ...]
    espaco_livre_bytes: int | None


@dataclass(frozen=True)
class Motor:
    gpus_cuda: int
    tipos: dict[str, tuple[str, ...]] = field(default_factory=dict)
    pastas_dll: tuple[str, ...] = ()
    erro: str | None = None


@dataclass(frozen=True)
class Escolha:
    dispositivo: str | None
    tipo: str | None
    motivo: str


def medir_sistema(pasta: Path | None = None) -> Sistema:
    gpus: tuple[str, ...] = ()
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            saida = subprocess.run(
                [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=15,
            )
            if saida.returncode == 0:
                gpus = tuple(l.strip() for l in saida.stdout.splitlines() if l.strip())
        except (OSError, subprocess.SubprocessError):
            gpus = ()
    livre = None
    try:
        livre = shutil.disk_usage(pasta or Path.cwd()).free
    except OSError:
        pass
    return Sistema(
        sistema=f"{platform.system()} {platform.release()} ({platform.machine()})",
        python=platform.python_version(),
        gpus_nvidia=gpus,
        espaco_livre_bytes=livre,
    )


def registrar_dlls_cuda() -> tuple[str, ...]:
    """No Windows, as bibliotecas CUDA instaladas pelo pip (pacotes `nvidia-*`) ficam fora do caminho de busca de DLLs.

    Registra as pastas `bin` desses pacotes, se existirem. Em outros sistemas não há o que fazer.
    """
    if sys.platform != "win32":
        return ()
    try:
        import nvidia  # type: ignore[import-not-found]
    except ImportError:
        return ()
    pastas = []
    for raiz in getattr(nvidia, "__path__", []):
        for bin_ in sorted(Path(raiz).glob("*/bin")):
            os.add_dll_directory(str(bin_))
            os.environ["PATH"] = str(bin_) + os.pathsep + os.environ.get("PATH", "")
            pastas.append(bin_.parent.name)
    return tuple(pastas)


def medir_motor() -> Motor:
    pastas = registrar_dlls_cuda()
    try:
        import ctranslate2
    except ImportError as e:
        return Motor(gpus_cuda=0, pastas_dll=pastas, erro=f"CTranslate2 ausente: {e}")
    tipos: dict[str, tuple[str, ...]] = {}
    for dispositivo in ("cpu", "cuda"):
        try:
            tipos[dispositivo] = tuple(sorted(ctranslate2.get_supported_compute_types(dispositivo)))
        except Exception:  # noqa: BLE001 — sem CUDA, o CTranslate2 levanta; isso é a medição dizendo "não há"
            tipos[dispositivo] = ()
    try:
        gpus = ctranslate2.get_cuda_device_count()
    except Exception:  # noqa: BLE001
        gpus = 0
    return Motor(gpus_cuda=gpus, tipos=tipos, pastas_dll=pastas)


def escolher(pedido: str, motor: Motor) -> Escolha:
    """`pedido` é o VOZ_DISPOSITIVO do usuário: auto, cpu ou cuda."""
    tem_cuda = motor.gpus_cuda > 0 and bool(motor.tipos.get("cuda"))
    if pedido == "cuda" and not tem_cuda:
        return Escolha(None, None, "VOZ_DISPOSITIVO=cuda, mas o CTranslate2 não encontrou GPU CUDA nesta máquina.")
    dispositivo = "cuda" if pedido == "cuda" or (pedido == "auto" and tem_cuda) else "cpu"
    disponiveis = motor.tipos.get(dispositivo, ())
    tipo = next((t for t in PREFERENCIA[dispositivo] if t in disponiveis), None)
    if tipo is None:
        return Escolha(None, None, f"Nenhum tipo de cálculo conhecido para {dispositivo}; medidos: {list(disponiveis)}.")
    if pedido == "auto":
        motivo = (f"GPU CUDA encontrada ({motor.gpus_cuda})" if tem_cuda else "nenhuma GPU CUDA encontrada") + f": {dispositivo}/{tipo}."
    else:
        motivo = f"pedido {pedido}: {dispositivo}/{tipo}."
    return Escolha(dispositivo, tipo, motivo)
