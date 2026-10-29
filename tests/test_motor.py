"""Peças do motor (Sprint 5) que dão para testar sem conexão WebRTC: a interrupção pela voz."""

import asyncio
import importlib.util
import unittest

TEM_PIPECAT = importlib.util.find_spec("pipecat") is not None


@unittest.skipUnless(TEM_PIPECAT, "Pipecat não instalado neste Python")
class TestInterrupcao(unittest.TestCase):
    def rodar(self, quadros):
        from pipecat.frames.frames import InterruptionFrame
        from pipecat.processors.frame_processor import FrameDirection

        from newclaw_ivox.motor import _processadores

        Interrupcao, _ = _processadores()
        processador = Interrupcao()
        transmitidos = []

        async def interromper():
            transmitidos.append(InterruptionFrame)

        async def empurrar(quadro, direcao=FrameDirection.DOWNSTREAM):
            pass

        processador.broadcast_interruption = interromper
        processador.push_frame = empurrar

        async def tudo():
            for q in quadros:
                await processador.process_frame(q, FrameDirection.DOWNSTREAM)

        # process_frame da classe base precisa do processador iniciado; aqui só a lógica própria interessa.
        from pipecat.processors.frame_processor import FrameProcessor

        original = FrameProcessor.process_frame

        async def sem_base(self, frame, direction):
            return None

        FrameProcessor.process_frame = sem_base
        try:
            asyncio.run(tudo())
        finally:
            FrameProcessor.process_frame = original
        return processador, transmitidos

    def test_fala_por_cima_interrompe(self):
        from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, VADUserStartedSpeakingFrame

        p, transmitidos = self.rodar([BotStartedSpeakingFrame(), VADUserStartedSpeakingFrame(), BotStoppedSpeakingFrame()])
        self.assertEqual(p.interrupcoes, 1)
        self.assertEqual(len(transmitidos), 1)
        self.assertEqual(len(p.latencias_ms), 1)

    def test_fala_com_motor_calado_nao_interrompe(self):
        from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, VADUserStartedSpeakingFrame

        p, transmitidos = self.rodar([BotStartedSpeakingFrame(), BotStoppedSpeakingFrame(), VADUserStartedSpeakingFrame()])
        self.assertEqual(p.interrupcoes, 0)
        self.assertEqual(transmitidos, [])


if __name__ == "__main__":
    unittest.main()
