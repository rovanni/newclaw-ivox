"""Modelos da transcrição local: quais existem, quanto pesam e onde ficam.

A lista vem do próprio faster-whisper (`available_models()`), e o tamanho, do Hugging Face no momento da pergunta. Nada
disso fica escrito aqui. Baixar é sempre pedido explícito: o instalador mostra o tamanho e pergunta antes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Arquivo que todo modelo CTranslate2 tem; a presença dele na pasta é o sinal de que o download terminou.
ARQUIVO_DO_MODELO = "model.bin"


@dataclass(frozen=True)
class ModeloStt:
    nome: str
    repositorio: str
    bytes_: int | None


def repositorios() -> dict[str, str]:
    """Nome curto → repositório no Hugging Face, como o faster-whisper instalado conhece."""
    from faster_whisper import utils

    nomes = utils.available_models()
    tabela = getattr(utils, "_MODELS", {})
    return {n: tabela.get(n, n) for n in nomes}


def tamanho(repositorio: str) -> int | None:
    """Soma dos arquivos do repositório no Hugging Face; None se a consulta falhar (sem rede, por exemplo)."""
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repositorio, files_metadata=True)
        return sum((s.size or 0) for s in (info.siblings or []))
    except Exception:  # noqa: BLE001 — sem tamanho, o instalador diz que não conseguiu medir
        return None


def listar(com_tamanho: bool = True) -> list[ModeloStt]:
    vistos: dict[str, ModeloStt] = {}
    for nome, repo in repositorios().items():
        vistos[nome] = ModeloStt(nome, repo, tamanho(repo) if com_tamanho else None)
    return list(vistos.values())


def pasta_do_modelo(modelos_dir: Path, nome: str) -> Path:
    return modelos_dir / "stt" / nome


def instalado(modelos_dir: Path, nome: str) -> bool:
    return (pasta_do_modelo(modelos_dir, nome) / ARQUIVO_DO_MODELO).is_file()


def baixar(modelos_dir: Path, nome: str) -> Path:
    from faster_whisper import download_model

    destino = pasta_do_modelo(modelos_dir, nome)
    destino.mkdir(parents=True, exist_ok=True)
    download_model(nome, output_dir=str(destino))
    if not instalado(modelos_dir, nome):
        raise RuntimeError(f"O download de '{nome}' terminou sem {ARQUIVO_DO_MODELO} em {destino}.")
    return destino


def formatar_bytes(n: int | None) -> str:
    if n is None:
        return "tamanho não medido"
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade in ("B", "KB") else f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"
