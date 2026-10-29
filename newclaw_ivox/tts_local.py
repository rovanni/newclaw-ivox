"""Síntese local: o `KokoroTTSService` do Pipecat (kokoro-onnx), com voz e idioma sempre explícitos.

O Pipecat assume o inglês e baixa os arquivos sozinho para uma pasta própria quando não recebe nada; aqui ele recebe os
arquivos já baixados em `modelos/tts/kokoro`, a voz escolhida e o idioma configurado. A voz é conferida contra o arquivo
de vozes antes de usar. Aqui nunca se baixa nada.

Licença (achado da Sprint 4): o kokoro-onnx carrega `phonemizer` e `espeak-ng`, ambos GPL-3.0, no mesmo processo. Pesa só
na distribuição; a decisão (manter no processo ou mover para subprocesso, que a H1 permite) fica pendente para antes de
qualquer publicação.
"""

from __future__ import annotations

import asyncio
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

from . import configuracao as cfg
from . import modelos

# Taxa de saída quando o serviço roda fora de um pipeline (no pipeline, quem define é o transporte).
TAXA_PADRAO_FORA_DO_PIPELINE = 24_000


class TtsIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True)
class Fala:
    frase: str
    audio_pcm16: bytes
    taxa: int
    segundos_ate_primeiro_audio: float
    segundos_para_sintetizar: float

    @property
    def segundos_de_audio(self) -> float:
        return len(self.audio_pcm16) / 2 / self.taxa


@dataclass(frozen=True)
class Resultado:
    falas: tuple[Fala, ...] = field(default=())

    @property
    def audio_pcm16(self) -> bytes:
        return b"".join(f.audio_pcm16 for f in self.falas)


class SemVozEscolhida(TtsIndisponivel):
    """A voz é escolhida na interface; até lá, o motor não fala (e a resposta fica só em texto)."""


def criar_servico(config: cfg.Configuracao, taxa: int = TAXA_PADRAO_FORA_DO_PIPELINE, voz: str | None = None):
    """`voz` é a escolhida na interface; sem ela, vale a voz inicial do `.env` (VOZ_TTS_VOZ), se houver."""
    if config.tts is None or config.tts.motor != cfg.LOCAL:
        raise TtsIndisponivel("Síntese local não configurada (VOZ_TTS_MOTOR=local).")
    if not modelos.kokoro_instalado(config.modelos_dir):
        raise TtsIndisponivel(f"Kokoro não está em {modelos.pasta_kokoro(config.modelos_dir)}. Rode o instalador para baixá-lo.")
    if config.idioma is None:
        raise TtsIndisponivel("VOZ_IDIOMA vazio: a síntese precisa saber em que idioma falar, e nenhum é escolhido aqui.")
    voz = voz or config.tts.voz
    if voz is None:
        raise SemVozEscolhida("Nenhuma voz escolhida: escolha uma na interface (todas as vozes do Kokoro já estão instaladas).")
    vozes = modelos.vozes_kokoro(config.modelos_dir)
    if voz not in vozes:
        raise TtsIndisponivel(f"A voz '{voz}' não está no arquivo de vozes do Kokoro ({len(vozes)} vozes).")

    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.transcriptions.language import Language

    modelo, arquivo_vozes = modelos.arquivos_kokoro(config.modelos_dir)
    servico = KokoroTTSService(
        model_path=str(modelo),
        voices_path=str(arquivo_vozes),
        sample_rate=taxa,
        settings=KokoroTTSService.Settings(voice=voz, language=Language(config.idioma)),
    )
    return servico


def voz_atual(servico) -> str:
    return servico._settings.voice


def trocar_voz(servico, voz: str, vozes: list[str]) -> None:
    """Troca a voz sem recarregar o modelo, pelo mesmo caminho de configuração que o pipeline usa."""
    if voz not in vozes:
        raise TtsIndisponivel(f"A voz '{voz}' não está no arquivo de vozes do Kokoro ({len(vozes)} vozes).")
    from pipecat.services.kokoro.tts import KokoroTTSService

    asyncio.run(servico._update_settings(KokoroTTSService.Settings(voice=voz)))
    if voz_atual(servico) != voz:
        raise TtsIndisponivel(f"O serviço não aceitou a troca para '{voz}'.")


def sintetizar(servico, frases: list[str]) -> Resultado:
    """Sintetiza frase a frase (H2), pelo mesmo `run_tts` que o pipeline usa, e mede cada uma."""
    from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame

    if not servico.sample_rate:
        # No pipeline, a taxa é definida quando ele inicia; fora dele, vale a pedida na criação.
        servico._sample_rate = servico._init_sample_rate or TAXA_PADRAO_FORA_DO_PIPELINE

    async def uma(frase: str, indice: int) -> Fala:
        inicio = time.perf_counter()
        primeiro = None
        pedacos, erros = [], []
        async for quadro in servico.run_tts(frase, f"teste-{indice}"):
            if isinstance(quadro, TTSAudioRawFrame):
                if primeiro is None:
                    primeiro = time.perf_counter() - inicio
                pedacos.append(quadro.audio)
            elif isinstance(quadro, ErrorFrame):
                erros.append(quadro.error)
        if erros:
            raise TtsIndisponivel("; ".join(erros))
        total = time.perf_counter() - inicio
        return Fala(frase, b"".join(pedacos), servico.sample_rate, primeiro if primeiro is not None else total, total)

    async def todas():
        return [await uma(f, i) for i, f in enumerate(frases)]

    return Resultado(tuple(asyncio.run(todas())))


def gravar_wav(caminho: Path, audio_pcm16: bytes, taxa: int) -> None:
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(audio_pcm16)
