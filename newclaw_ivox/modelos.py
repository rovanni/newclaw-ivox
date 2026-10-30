"""Modelos da transcrição local: quais existem, quanto pesam e onde ficam.

A lista vem do próprio faster-whisper (`available_models()`), e o tamanho, do Hugging Face no momento da pergunta. Nada
disso fica escrito aqui. Baixar é sempre pedido explícito: o instalador mostra o tamanho e pergunta antes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Arquivo que todo modelo CTranslate2 tem; a presença dele na pasta é o sinal de que o download terminou.
ARQUIVO_DO_MODELO = "model.bin"

# Foto da lista de modelos (nome, tamanho, licença, data), gerada por `modelos --gravar-lista`: é o que o painel mostra
# antes de o faster-whisper estar instalado.
ARQUIVO_DA_LISTA = "modelos-whisper.json"


def ler_lista_gravada(raiz: Path) -> dict | None:
    import json

    try:
        return json.loads((raiz / ARQUIVO_DA_LISTA).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass(frozen=True)
class ModeloStt:
    nome: str
    repositorio: str
    bytes_: int | None
    # A licença declarada no cartão do modelo no Hugging Face (None: não declarada ou sem rede). Mostrada na escolha.
    licenca: str | None = None


def repositorios() -> dict[str, str]:
    """Nome curto → repositório no Hugging Face, como o faster-whisper instalado conhece."""
    from faster_whisper import utils

    nomes = utils.available_models()
    tabela = getattr(utils, "_MODELS", {})
    return {n: tabela.get(n, n) for n in nomes}


def consultar(repositorio: str) -> tuple[int | None, str | None]:
    """Tamanho (soma dos arquivos) e licença declarada do repositório no Hugging Face, numa consulta só; (None, None) se
    ela falhar (sem rede, por exemplo)."""
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repositorio, files_metadata=True)
        licenca = info.card_data.get("license") if info.card_data else None
        return sum((s.size or 0) for s in (info.siblings or [])), licenca
    except Exception:  # noqa: BLE001 — sem os dados, o instalador diz que não conseguiu medir
        return None, None


def listar(com_tamanho: bool = True) -> list[ModeloStt]:
    vistos: dict[str, ModeloStt] = {}
    for nome, repo in repositorios().items():
        bytes_, licenca = consultar(repo) if com_tamanho else (None, None)
        vistos[nome] = ModeloStt(nome, repo, bytes_, licenca)
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


# ─── Síntese local (Kokoro) ──────────────────────────────────────────────────
# Os endereços dos arquivos vêm do serviço Kokoro do Pipecat instalado (as mesmas constantes que ele usaria para baixar
# sozinho); aqui só se escolhe a pasta, e o download só acontece quando pedido.

ARQUIVOS_KOKORO = ("kokoro-v1.0.onnx", "voices-v1.0.bin")


def pasta_kokoro(modelos_dir: Path) -> Path:
    return modelos_dir / "tts" / "kokoro"


def arquivos_kokoro(modelos_dir: Path) -> tuple[Path, Path]:
    pasta = pasta_kokoro(modelos_dir)
    return pasta / ARQUIVOS_KOKORO[0], pasta / ARQUIVOS_KOKORO[1]


def kokoro_instalado(modelos_dir: Path) -> bool:
    return all(p.is_file() and p.stat().st_size > 0 for p in arquivos_kokoro(modelos_dir))


def enderecos_kokoro() -> tuple[str, str]:
    from pipecat.services.kokoro import tts

    return tts.KOKORO_MODEL_URL, tts.KOKORO_VOICES_URL


def tamanho_kokoro() -> int | None:
    """Soma dos dois arquivos, perguntada ao servidor (HEAD); None se não der para medir."""
    try:
        import requests

        total = 0
        for url in enderecos_kokoro():
            resposta = requests.head(url, allow_redirects=True, timeout=30)
            resposta.raise_for_status()
            total += int(resposta.headers["Content-Length"])
        return total
    except Exception:  # noqa: BLE001
        return None


def baixar_kokoro(modelos_dir: Path) -> Path:
    from pipecat.services.kokoro import tts

    modelo, vozes = arquivos_kokoro(modelos_dir)
    # Baixa para um nome provisório e só renomeia no fim: um download interrompido não fica parecendo completo.
    for destino, url in ((modelo, tts.KOKORO_MODEL_URL), (vozes, tts.KOKORO_VOICES_URL)):
        if destino.is_file():
            continue
        parcial = destino.with_suffix(destino.suffix + ".parcial")
        tts._download_file(url, parcial)
        parcial.replace(destino)
    if not kokoro_instalado(modelos_dir):
        raise RuntimeError(f"O download do Kokoro terminou incompleto em {pasta_kokoro(modelos_dir)}.")
    return pasta_kokoro(modelos_dir)


def vozes_kokoro(modelos_dir: Path) -> list[str]:
    """As vozes que estão de fato no arquivo de vozes baixado."""
    import numpy as np

    _, vozes = arquivos_kokoro(modelos_dir)
    with np.load(vozes) as dados:
        return sorted(dados.files)


def formatar_bytes(n: int | None) -> str:
    if n is None:
        return "tamanho não medido"
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade in ("B", "KB") else f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"
