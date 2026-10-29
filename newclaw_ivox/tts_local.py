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
from . import misturas, modelos

RAIZ = Path(__file__).resolve().parent.parent

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
    base = modelos.vozes_kokoro(config.modelos_dir)
    lista = misturas_validas(base)
    nomes = nomes_disponiveis(base, lista)
    if voz not in nomes:
        raise TtsIndisponivel(f"A voz '{voz}' não está entre as {len(nomes)} disponíveis.")

    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.transcriptions.language import Language

    # O serviço confere a voz inicial no arquivo do Kokoro ao nascer; uma mistura ainda não está lá. Ele nasce com a
    # primeira voz da mistura, recebe as misturas e troca para a pedida em seguida.
    mistura = next((m for m in lista if m.nome == voz), None)
    voz_de_partida = mistura.pesos[0][0] if mistura else voz
    modelo, arquivo_vozes = modelos.arquivos_kokoro(config.modelos_dir)
    servico = KokoroTTSService(
        model_path=str(modelo),
        voices_path=str(arquivo_vozes),
        sample_rate=taxa,
        settings=KokoroTTSService.Settings(voice=voz_de_partida, language=Language(config.idioma)),
    )
    _acrescentar_misturas(servico, lista)
    if mistura:
        trocar_voz(servico, voz)
    return servico


def misturas_validas(base: list[str]) -> list[misturas.Mistura]:
    try:
        return misturas.carregar(RAIZ / misturas.ARQUIVO, base)
    except misturas.MisturaInvalida as e:
        raise TtsIndisponivel(f"Vozes misturadas: {e}") from e


def nomes_disponiveis(base: list[str], lista: list[misturas.Mistura]) -> list[str]:
    return [m.nome for m in lista] + list(base)


def vozes_disponiveis(modelos_dir: Path) -> list[dict]:
    """Para a interface: as misturas primeiro (com rótulo), depois as vozes do Kokoro (o rótulo é o próprio nome)."""
    base = modelos.vozes_kokoro(modelos_dir)
    lista = misturas_validas(base)
    return [{"nome": m.nome, "rotulo": m.rotulo, "mistura": dict(m.pesos)} for m in lista] + [
        {"nome": v, "rotulo": v} for v in base
    ]


def _acrescentar_misturas(servico, lista: list[misturas.Mistura]) -> None:
    """O kokoro-onnx guarda as vozes como vetores de estilo por nome; a mistura é a média ponderada deles."""
    kokoro = servico._kokoro
    vozes = {nome: kokoro.voices[nome] for nome in kokoro.voices.keys()}
    for m in lista:
        vozes[m.nome] = sum(vozes[v] * peso for v, peso in m.pesos)
    kokoro.voices = vozes


def voz_atual(servico) -> str:
    return servico._settings.voice


def trocar_voz(servico, voz: str) -> None:
    """Troca a voz sem recarregar o modelo, pelo mesmo caminho de configuração que o pipeline usa."""
    if voz not in servico._kokoro.voices:
        raise TtsIndisponivel(f"A voz '{voz}' não está entre as {len(servico._kokoro.voices)} disponíveis.")
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
