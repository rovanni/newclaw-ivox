"""O ambiente do motor de voz funciona nesta máquina? (Sprint 2.)

Só roda com o Pipecat instalado (`.venv` do projeto); sem ele, os testes são pulados e o motivo aparece. Nada de rede:
o VAD roda o modelo ONNX local sobre áudio gerado aqui.
"""

import asyncio
import importlib
import importlib.util
import math
import struct
import unittest

TEM_PIPECAT = importlib.util.find_spec("pipecat") is not None
TAXA = 16_000


def pcm16(amostras) -> bytes:
    return struct.pack(f"<{len(amostras)}h", *(max(-32768, min(32767, int(a))) for a in amostras))


@unittest.skipUnless(TEM_PIPECAT, "Pipecat não instalado neste Python (ver docs/SPRINTS.md, Sprint 2)")
class TestMotorDisponivel(unittest.TestCase):
    def test_componentes_do_pipeline_importam(self):
        for modulo in (
            "pipecat.transports.smallwebrtc.transport",
            "pipecat.audio.vad.silero",
            "pipecat.services.openai.stt",
            "pipecat.services.openai.tts",
            "pipecat.processors.frameworks.rtvi",
        ):
            with self.subTest(modulo=modulo):
                importlib.import_module(modulo)

    def test_versao_fixada(self):
        import importlib.metadata as md

        self.assertEqual(md.version("pipecat-ai"), "1.12.0")

    def test_vad_silero_roda_o_onnx(self):
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADState

        vad = SileroVADAnalyzer(sample_rate=TAXA)
        vad.set_sample_rate(TAXA)  # o pipeline faz isto ao iniciar; sem ele o analisador não sabe o tamanho do quadro
        quadro = vad.num_frames_required()
        self.assertGreater(quadro, 0)

        silencio = pcm16([0] * quadro)
        self.assertLess(vad.voice_confidence(silencio), 0.5)
        async def analisar_varias_vezes():
            estado = None
            for _ in range(20):
                estado = await vad.analyze_audio(silencio)
            return estado

        self.assertEqual(asyncio.run(analisar_varias_vezes()), VADState.QUIET)

        tom = pcm16([8000 * math.sin(2 * math.pi * 440 * i / TAXA) for i in range(quadro)])
        confianca = vad.voice_confidence(tom)
        self.assertTrue(0.0 <= confianca <= 1.0)


RAIZ = __import__("pathlib").Path(__file__).resolve().parent.parent


def _kokoro_baixado() -> bool:
    if not TEM_PIPECAT:
        return False
    from newclaw_ivox import modelos

    return modelos.kokoro_instalado(RAIZ / "modelos")


@unittest.skipUnless(_kokoro_baixado(), "Kokoro não baixado em modelos/ (o instalador baixa)")
class TestVozesMisturadas(unittest.TestCase):
    def test_mistura_e_troca_em_execucao(self):
        from newclaw_ivox import configuracao as cfg, tts_local

        config = cfg.carregar({"VOZ_TTS_MOTOR": "local", "VOZ_IDIOMA": "pt-BR"}, raiz=RAIZ)
        nomes = [v["nome"] for v in tts_local.vozes_disponiveis(config.modelos_dir)]
        self.assertEqual(nomes[:3], ["george-alex-1", "george-alex-2", "george-alex-3"])

        servico = tts_local.criar_servico(config, voz="george-alex-1")
        self.assertEqual(tts_local.voz_atual(servico), "george-alex-1")
        um = tts_local.sintetizar(servico, ["Teste."]).audio_pcm16
        tts_local.trocar_voz(servico, "george-alex-3")
        tres = tts_local.sintetizar(servico, ["Teste."]).audio_pcm16
        self.assertTrue(um and tres)
        self.assertNotEqual(um, tres)
        with self.assertRaises(tts_local.TtsIndisponivel):
            tts_local.trocar_voz(servico, "voz_do_filme")


if __name__ == "__main__":
    unittest.main()
