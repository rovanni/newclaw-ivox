"""Motor de voz (Sprint 5): microfone → VAD → Whisper → texto na janela; texto da janela → Kokoro → alto-falante.

Sem LLM, sem histórico, sem persona (ADR-030): quem responde é o NewClaw, e a janela manda ao motor o que falar. Peças,
todas do Pipecat, montadas com o que foi configurado e medido:

    transporte (entrada) → VAD Silero → Interrupção → Whisper → [Eco] → Kokoro → transporte (saída)

- **Interrupção pela voz:** quando o VAD detecta a pessoa falando enquanto o motor fala, o motor para na hora (o pedido no
  NewClaw continua; cancelar é outra ação, D3).
- **Mensagens da janela:** chegam pelo RTVI (`client-message`) e vão para `controle.interpretar`: falar, interromper, vozes,
  voz.
- **Eco** (`--eco`, só para testar sem o NewClaw): o motor repete o que ouviu, para provar o ciclo e a interrupção com
  microfone de verdade.

O servidor desta sprint é o runner de desenvolvimento do Pipecat, preso a 127.0.0.1 e com origem restrita; o servidor
próprio do harness (login, repasse ao NewClaw, checagem de origem) é a Etapa 3.
"""

from __future__ import annotations

import asyncio
import sys
import time

from . import configuracao as cfg
from . import controle, stt_local, tts_local
from .comandos import RAIZ

_EM_ECO = False
_AQUECIDO: list[bool] = []  # o aquecimento da GPU vale para o processo inteiro


def _processadores():
    """Classes que dependem do Pipecat, criadas só quando o motor roda (o resto do pacote não precisa dele)."""
    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        BotStoppedSpeakingFrame,
        TranscriptionFrame,
        TTSSpeakFrame,
        VADUserStartedSpeakingFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    class Interrupcao(FrameProcessor):
        """Corta a fala do motor quando a pessoa começa a falar por cima."""

        def __init__(self):
            super().__init__()
            self.motor_falando = False
            self.interrupcoes = 0
            self.latencias_ms: list[float] = []
            self._pedida_em: float | None = None

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, BotStartedSpeakingFrame):
                self.motor_falando = True
            elif isinstance(frame, BotStoppedSpeakingFrame):
                self.motor_falando = False
                if self._pedida_em is not None:
                    # Do VAD confirmar a fala da pessoa até a saída avisar que o áudio do motor parou.
                    self.latencias_ms.append((time.perf_counter() - self._pedida_em) * 1000)
                    print(f"[motor] fala do motor parou {self.latencias_ms[-1]:.0f} ms depois da interrupção", flush=True)
                    self._pedida_em = None
            elif isinstance(frame, VADUserStartedSpeakingFrame) and self.motor_falando:
                self.interrupcoes += 1
                self._pedida_em = time.perf_counter()
                print(f"[motor] interrupção pela voz #{self.interrupcoes}", flush=True)
                await self.push_frame(frame, direction)
                await self.broadcast_interruption()
                return
            await self.push_frame(frame, direction)

    class Eco(FrameProcessor):
        """Só no modo de teste: transforma o que foi ouvido em fala."""

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            await self.push_frame(frame, direction)
            if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM and frame.text.strip():
                print(f"[motor] ouvi: {frame.text.strip()!r}", flush=True)
                for frase in controle.preparar_para_fala(f"Você disse: {frame.text.strip()}"):
                    await self.push_frame(TTSSpeakFrame(frase, append_to_context=False))

    return Interrupcao, Eco


async def bot(runner_args):
    """Chamado pelo runner do Pipecat a cada conexão da janela."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import TTSSpeakFrame, TTSUpdateSettingsFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.services.kokoro.tts import KokoroTTSService
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    from . import modelos

    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    Interrupcao, Eco = _processadores()

    transporte = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    etapas = [transporte.input(), VADProcessor(vad_analyzer=SileroVADAnalyzer())]
    interrupcao = Interrupcao()
    etapas.append(interrupcao)

    stt = None
    if config.stt is not None and config.stt.motor == cfg.LOCAL:
        inicio = time.perf_counter()
        # Carregar o modelo bloqueia; numa thread, o servidor continua respondendo enquanto isso.
        stt, escolha = await asyncio.to_thread(stt_local.criar_servico, config)
        carga = time.perf_counter() - inicio
        if not _AQUECIDO:
            await stt_local.transcrever_async(stt, escolha, bytes(16_000 * 2), 16_000)  # a 1ª de cada processo é lenta
            _AQUECIDO.append(True)
        print(f"[motor] Whisper pronto em {time.perf_counter() - inicio:.1f} s (carga {carga:.1f} s; {escolha.motivo})", flush=True)
        etapas.append(stt)
    if _EM_ECO:
        etapas.append(Eco())

    tts = None
    vozes: tuple[str, ...] | None = None
    if config.tts is not None and config.tts.motor == cfg.LOCAL:
        vozes = tuple(v["nome"] for v in tts_local.vozes_disponiveis(config.modelos_dir))
        try:
            tts = await asyncio.to_thread(tts_local.criar_servico, config, None)
            print(f"[motor] Kokoro pronto, voz {tts_local.voz_atual(tts)}", flush=True)
        except tts_local.SemVozEscolhida as e:
            print(f"[motor] {e}", flush=True)
        if tts is not None:
            etapas.append(tts)
    etapas.append(transporte.output())

    task = PipelineTask(Pipeline(etapas), params=PipelineParams())
    estado = {"voz": tts_local.voz_atual(tts) if tts else None}

    @task.rtvi.event_handler("on_client_message")
    async def mensagem(rtvi, msg):
        acao = controle.interpretar(
            {"t": msg.type, "d": msg.data}, fala_ligada=tts is not None or vozes is not None,
            voz_atual=estado["voz"], vozes=vozes,
        )
        if acao.tipo == controle.FALAR and tts is not None:
            await task.queue_frames([TTSSpeakFrame(f, append_to_context=False) for f in acao.frases])
        elif acao.tipo == controle.INTERROMPER:
            await rtvi.interrupt_bot()
        elif acao.tipo == controle.LISTAR_VOZES:
            lista = tts_local.vozes_disponiveis(config.modelos_dir)
            await rtvi.send_server_response(msg, {"vozes": lista, "atual": estado["voz"]})
            return
        elif acao.tipo == controle.TROCAR_VOZ:
            if tts is None:
                await rtvi.send_error_response(msg, "a síntese ainda não começou: reinicie o motor com uma voz inicial")
                return
            await task.queue_frame(TTSUpdateSettingsFrame(delta=KokoroTTSService.Settings(voice=acao.voz)))
            estado["voz"] = acao.voz
        elif acao.tipo == controle.IGNORAR:
            await rtvi.send_error_response(msg, acao.motivo)
            return
        await rtvi.send_server_response(msg, {"ok": True, "acao": acao.tipo, "voz": estado["voz"]})

    @transporte.event_handler("on_client_disconnected")
    async def desconectou(transport, client):
        print(f"[motor] janela desconectou; interrupções pela voz nesta sessão: {interrupcao.interrupcoes}", flush=True)
        await task.cancel()

    await PipelineRunner(handle_sigint=False).run(task)


def principal(argumentos: list[str]) -> int:
    """`motor [--eco]` — sobe o motor em 127.0.0.1:HARNESS_PORTA, com a página de teste do Pipecat em /client."""
    global _EM_ECO
    _EM_ECO = "--eco" in argumentos
    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    if config.tem_erro or config.nada_configurado:
        print("Configuração incompleta; rode: python -m newclaw_ivox diagnostico")
        return 1
    from pipecat.runner import run

    sys.modules["__main__"].bot = bot  # o runner procura a função `bot` no módulo principal
    endereco = f"http://localhost:{config.porta}"
    print(f"[motor] abrindo em {endereco}/client {'(modo eco: repete o que ouvir)' if _EM_ECO else ''}", flush=True)
    sys.argv = [
        "newclaw-ivox-motor", "-t", "webrtc", "--host", "127.0.0.1", "--port", str(config.porta),
        "--allowed-origins", endereco, f"http://127.0.0.1:{config.porta}",
    ]
    run.main()
    return 0
