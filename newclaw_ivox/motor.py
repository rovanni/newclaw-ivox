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

# Silêncio que fecha um trecho de fala para o Whisper. O padrão do Pipecat (0,2 s) cortava a fala a cada respiro, e cada
# pedaço ia sozinho para a transcrição, sem o resto da frase: "Homem de Ferro" virou "Dorme de ferro", enquanto as frases
# inteiras saíam certas (prova com a operadora, 30/10/2026). O início da fala (`start_secs`, que dispara a interrupção)
# continua o do Pipecat.
PAUSA_QUE_FECHA_O_TRECHO_S = 0.8


def _processadores():
    """Classes que dependem do Pipecat, criadas só quando o motor roda (o resto do pacote não precisa dele)."""
    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        BotStoppedSpeakingFrame,
        TranscriptionFrame,
        TTSSpeakFrame,
        UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame,
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    class Interrupcao(FrameProcessor):
        """Corta a fala do motor quando a pessoa começa a falar por cima, e avisa a janela que a pessoa fala.

        O aviso: o RTVI só manda `user-started-speaking`/`user-stopped-speaking` (os eventos que o cliente da janela conhece)
        a partir de UserStarted/StoppedSpeakingFrame, que no Pipecat vêm da agregação de turno de um LLM — e este motor não
        tem LLM. O VAD gera só VADUser…, que o RTVI repassa como `vad-user-…`, nome que o cliente 1.13 não trata. Sem isto
        a janela nunca acendia "Ouvindo" (achado da prova com a operadora, 30/10/2026). O Whisper local não usa esses
        quadros (só os serviços de transcrição por rede, para reconectar).
        """

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
            elif isinstance(frame, VADUserStartedSpeakingFrame):
                await self.push_frame(frame, direction)
                await self.push_frame(UserStartedSpeakingFrame(), direction)
                if self.motor_falando:
                    self.interrupcoes += 1
                    self._pedida_em = time.perf_counter()
                    print(f"[motor] interrupção pela voz #{self.interrupcoes}", flush=True)
                    await self.broadcast_interruption()
                return
            elif isinstance(frame, VADUserStoppedSpeakingFrame):
                await self.push_frame(frame, direction)
                await self.push_frame(UserStoppedSpeakingFrame(), direction)
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
    from pipecat.audio.vad.vad_analyzer import VADParams
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
    if config.idioma is None and getattr(runner_args, "idioma", None):
        # Sem VOZ_IDIOMA, o servidor do harness leu o idioma configurado no NewClaw no login.
        import dataclasses

        config = dataclasses.replace(config, idioma=runner_args.idioma)
    Interrupcao, Eco = _processadores()

    transporte = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    vad = SileroVADAnalyzer(params=VADParams(stop_secs=PAUSA_QUE_FECHA_O_TRECHO_S))
    etapas = [transporte.input(), VADProcessor(vad_analyzer=vad)]
    interrupcao = Interrupcao()
    etapas.append(interrupcao)

    stt = None
    if config.stt is not None and config.stt.motor == cfg.LOCAL:
        # Conectar não carrega o modelo (ADR-037): o serviço pede o modelo ao dono a cada trecho; carregar é um pedido
        # da pessoa na janela (POST /api/modelo/carregar).
        stt = stt_local.servico_da_linha(config)
        print(f"[motor] transcrição na linha; modelo {stt_local.dono().estado()['estado']}", flush=True)
        etapas.append(stt)
    if _EM_ECO:
        etapas.append(Eco())

    tts = None
    vozes: tuple[str, ...] | None = None
    voz_inicial: str | None = None
    if config.tts is not None and config.tts.motor == cfg.LOCAL:
        vozes = tuple(v["nome"] for v in tts_local.vozes_disponiveis(config.modelos_dir))
        try:
            tts = await asyncio.to_thread(tts_local.criar_servico, config, None)
            voz_inicial = tts_local.voz_atual(tts)
        except tts_local.SemVozEscolhida as e:
            # Sem voz inicial (a instalação pelo painel não escolhe uma), o Kokoro entra na linha mesmo assim: a escolha
            # na janela troca a voz em execução. Antes ele ficava de fora, e a troca era recusada até reiniciar o motor
            # (achado da operadora, 30/10/2026). A voz de partida só existe porque o serviço exige uma ao nascer: o
            # controle recusa todo pedido de fala enquanto nenhuma for escolhida, então ela nunca fala.
            print(f"[motor] {e}", flush=True)
            partida = tts_local.modelos.vozes_kokoro(config.modelos_dir)[0]
            tts = await asyncio.to_thread(tts_local.criar_servico, config, None, partida)
        medido, espera = await tts_local.ajustar_espera_pela_medicao(tts, config.idioma, controle.LIMITE_PADRAO)
        print(
            f"[motor] Kokoro pronto, voz {voz_inicial or '(a escolher na janela)'}; frase mais longa em {medido:.1f} s "
            f"→ espera por frase {espera:.1f} s",
            flush=True,
        )
        etapas.append(tts)
    etapas.append(transporte.output())

    # Sem limite de ociosidade: a janela fica aberta esperando a pessoa falar. O padrão do Pipecat (5 min parado) encerrava
    # a ligação no meio do uso (achado da prova real, 30/10/2026); ela acaba quando a janela desconecta.
    task = PipelineTask(Pipeline(etapas), params=PipelineParams(), idle_timeout_secs=None)
    estado: dict = {"voz": voz_inicial, "velocidade": 1.0}

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
            await task.queue_frame(TTSUpdateSettingsFrame(delta=KokoroTTSService.Settings(voice=acao.voz)))
            estado["voz"] = acao.voz
        elif acao.tipo == controle.VELOCIDADE:
            await task.queue_frame(TTSUpdateSettingsFrame(delta=KokoroTTSService.Settings(speed=acao.velocidade)))
            estado["velocidade"] = acao.velocidade
        elif acao.tipo == controle.IGNORAR:
            await rtvi.send_error_response(msg, acao.motivo)
            return
        await rtvi.send_server_response(
            msg, {"ok": True, "acao": acao.tipo, "voz": estado["voz"], "velocidade": estado["velocidade"]},
        )

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

    if config.stt is not None and config.stt.motor == cfg.LOCAL:
        # Este runner de teste não tem a janela nem a rota de carregar: rodar o comando já é o pedido de carga (ADR-037).
        stt_local.dono().pedir_carga(config)
    sys.modules["__main__"].bot = bot  # o runner procura a função `bot` no módulo principal
    endereco = f"http://localhost:{config.porta}"
    print(f"[motor] abrindo em {endereco}/client {'(modo eco: repete o que ouvir)' if _EM_ECO else ''}", flush=True)
    sys.argv = [
        "newclaw-ivox-motor", "-t", "webrtc", "--host", "127.0.0.1", "--port", str(config.porta),
        "--allowed-origins", endereco, f"http://127.0.0.1:{config.porta}",
    ]
    run.main()
    return 0
