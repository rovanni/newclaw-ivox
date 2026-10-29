"""Transcrição local: o `WhisperSTTService` do Pipecat (faster-whisper), montado só com o que foi configurado e medido.

Nada de padrão da biblioteca escapa para o uso: o Pipecat assume um modelo e o inglês quando não recebe nada, então
modelo, idioma, dispositivo e tipo de cálculo são sempre passados explicitamente. O modelo é carregado da pasta local, já
baixada; aqui nunca se baixa nada.
"""

from __future__ import annotations

import asyncio
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from . import configuracao as cfg
from . import dispositivo as disp
from . import modelos


class SttIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True)
class Transcricao:
    texto: str
    segundos_de_audio: float
    segundos_para_transcrever: float
    dispositivo: str
    tipo: str


def criar_servico(config: cfg.Configuracao):
    if config.stt is None or config.stt.motor != cfg.LOCAL:
        raise SttIndisponivel("Transcrição local não configurada (VOZ_STT_MOTOR=local e VOZ_STT_MODELO).")
    nome = config.stt.modelo
    if not modelos.instalado(config.modelos_dir, nome):
        raise SttIndisponivel(
            f"Modelo '{nome}' não está em {modelos.pasta_do_modelo(config.modelos_dir, nome)}. Rode o instalador para baixá-lo."
        )
    escolha = disp.escolher(config.dispositivo, disp.medir_motor())
    if escolha.dispositivo is None:
        raise SttIndisponivel(escolha.motivo)

    from pipecat.transcriptions.language import Language

    servico = _classe_com_cache()(
        device=escolha.dispositivo,
        compute_type=escolha.tipo,
        settings=_classe_com_cache().Settings(
            model=str(modelos.pasta_do_modelo(config.modelos_dir, nome)),
            language=Language(config.idioma) if config.idioma else None,
        ),
    )
    return servico, escolha


# Um modelo do Whisper carregado por processo: cada conexão da janela monta um serviço novo (o pipeline é por conexão),
# mas carregar o modelo leva ~9 s e ocupa a memória da GPU; o modelo em si não guarda nada da conversa.
_MODELOS_CARREGADOS: dict[tuple, object] = {}
_CLASSE = None


def _classe_com_cache():
    global _CLASSE
    if _CLASSE is None:
        from pipecat.services.whisper.stt import WhisperSTTService

        class WhisperComModeloReaproveitado(WhisperSTTService):
            def _load(self):
                chave = (self._settings.model, self._device, self._compute_type)
                if chave in _MODELOS_CARREGADOS:
                    self._model = _MODELOS_CARREGADOS[chave]
                    problema = self._unsupported_language()
                    if problema:
                        raise ValueError(problema)
                    return
                super()._load()
                _MODELOS_CARREGADOS[chave] = self._model

        _CLASSE = WhisperComModeloReaproveitado
    return _CLASSE


def ler_wav_pcm16(caminho: Path) -> tuple[bytes, int]:
    """Lê um WAV mono de 16 bits; devolve (amostras, taxa)."""
    with wave.open(str(caminho), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise ValueError(f"{caminho}: esperado WAV mono de 16 bits (veio {w.getnchannels()} canal(is), {8 * w.getsampwidth()} bits).")
        return w.readframes(w.getnframes()), w.getframerate()


def transcrever(servico, escolha: disp.Escolha, audio_pcm16: bytes, taxa: int) -> Transcricao:
    """Versão para fora de um laço asyncio (comandos de teste)."""
    return asyncio.run(transcrever_async(servico, escolha, audio_pcm16, taxa))


async def transcrever_async(servico, escolha: disp.Escolha, audio_pcm16: bytes, taxa: int) -> Transcricao:
    """Transcreve um trecho inteiro pelo mesmo `run_stt` que o pipeline usa. O Whisper espera 16 kHz."""
    if taxa != 16_000:
        raise ValueError(f"O Whisper espera áudio a 16 kHz; veio {taxa} Hz.")
    from pipecat.frames.frames import ErrorFrame, TranscriptionFrame

    inicio = time.perf_counter()
    textos, erros = [], []
    async for quadro in servico.run_stt(audio_pcm16):
        if isinstance(quadro, TranscriptionFrame):
            textos.append(quadro.text)
        elif isinstance(quadro, ErrorFrame):
            erros.append(quadro.error)
    duracao = time.perf_counter() - inicio
    if erros:
        raise SttIndisponivel("; ".join(erros))
    return Transcricao(
        texto=" ".join(t.strip() for t in textos).strip(),
        segundos_de_audio=len(audio_pcm16) / 2 / taxa,
        segundos_para_transcrever=duracao,
        dispositivo=escolha.dispositivo,
        tipo=escolha.tipo,
    )
