import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import configuracao as cfg


def niveis(config, variavel):
    return [a.nivel for a in config.achados if a.variavel == variavel]


COMPLETA = {
    "VOZ_STT_URL": "http://127.0.0.1:9000/v1",
    "VOZ_STT_MODELO": "modelo-stt-do-usuario",
    "VOZ_TTS_URL": "http://127.0.0.1:9001/v1",
    "VOZ_TTS_MODELO": "modelo-tts-do-usuario",
    "VOZ_TTS_VOZ": "voz-do-usuario",
    "VOZ_IDIOMA": "pt-BR",
}


class TestConfiguracao(unittest.TestCase):
    def test_vazia_desliga_tudo_e_reporta(self):
        c = cfg.carregar({})
        self.assertIsNone(c.stt)
        self.assertIsNone(c.tts)
        self.assertIsNone(c.idioma)
        self.assertTrue(c.nada_configurado)
        self.assertFalse(c.tem_erro)
        self.assertEqual(niveis(c, "VOZ_STT_URL"), [cfg.INFO])
        self.assertEqual(niveis(c, "VOZ_TTS_URL"), [cfg.INFO])
        self.assertEqual(c.porta, cfg.PORTA_PADRAO)

    def test_completa(self):
        c = cfg.carregar(COMPLETA)
        self.assertFalse(c.tem_erro)
        self.assertFalse(c.nada_configurado)
        self.assertEqual(c.stt.modelo, "modelo-stt-do-usuario")
        self.assertEqual(c.tts.voz, "voz-do-usuario")
        self.assertEqual(c.idioma, "pt-BR")

    def test_sem_modelo_nunca_adivinha(self):
        c = cfg.carregar({"VOZ_STT_URL": "http://x:1/v1"})
        self.assertIsNone(c.stt)
        self.assertEqual(niveis(c, "VOZ_STT_MODELO"), [cfg.ERRO])

    def test_tts_sem_voz_nunca_adivinha(self):
        amb = {k: v for k, v in COMPLETA.items() if k != "VOZ_TTS_VOZ"}
        c = cfg.carregar(amb)
        self.assertIsNone(c.tts)
        self.assertEqual(niveis(c, "VOZ_TTS_VOZ"), [cfg.ERRO])
        self.assertTrue(c.tem_erro)

    def test_url_invalida(self):
        c = cfg.carregar({**COMPLETA, "VOZ_TTS_URL": "ftp://x"})
        self.assertIsNone(c.tts)
        self.assertEqual(niveis(c, "VOZ_TTS_URL"), [cfg.ERRO])

    def test_idioma(self):
        self.assertEqual(niveis(cfg.carregar({**COMPLETA, "VOZ_IDIOMA": "fr-FR"}), "VOZ_IDIOMA"), [cfg.ERRO])
        sem = {k: v for k, v in COMPLETA.items() if k != "VOZ_IDIOMA"}
        self.assertEqual(niveis(cfg.carregar(sem), "VOZ_IDIOMA"), [cfg.AVISO])
        so_tts = {k: v for k, v in sem.items() if not k.startswith("VOZ_STT")}
        self.assertEqual(niveis(cfg.carregar(so_tts), "VOZ_IDIOMA"), [])

    def test_sobras_sem_url_avisam(self):
        c = cfg.carregar({"VOZ_TTS_MODELO": "m"})
        self.assertIn(cfg.AVISO, niveis(c, "VOZ_TTS_URL"))

    def test_ice_e_porta(self):
        c = cfg.carregar({"VOZ_ICE_SERVIDORES": "stun:a:3478, turns:b:5349", "HARNESS_PORTA": "8123"})
        self.assertEqual(c.ice_servidores, ("stun:a:3478", "turns:b:5349"))
        self.assertEqual(c.porta, 8123)
        c = cfg.carregar({"VOZ_ICE_SERVIDORES": "http://x", "HARNESS_PORTA": "99999"})
        self.assertEqual(c.ice_servidores, ())
        self.assertEqual(niveis(c, "VOZ_ICE_SERVIDORES"), [cfg.ERRO])
        self.assertEqual(niveis(c, "HARNESS_PORTA"), [cfg.ERRO])

    def test_chave_nunca_aparece_no_resumo(self):
        c = cfg.carregar({**COMPLETA, "VOZ_STT_CHAVE": "segredo-123", "VOZ_TTS_CHAVE": "outro-segredo"})
        resumo = repr(cfg.resumo_publico(c))
        self.assertNotIn("segredo", resumo)
        self.assertEqual(cfg.resumo_publico(c)["stt"]["chave"], "definida")

    def test_arquivo_env_e_precedencia(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text(
                "# comentário\nexport VOZ_TTS_URL='http://127.0.0.1:9001/v1'\nVOZ_TTS_MODELO=\"m\"\n"
                "VOZ_TTS_VOZ=do-arquivo\n\nlinha-sem-igual\n",
                encoding="utf-8",
            )
            c = cfg.carregar({"VOZ_TTS_VOZ": "do-ambiente"}, env)
            self.assertEqual(c.tts.url, "http://127.0.0.1:9001/v1")
            self.assertEqual(c.tts.modelo, "m")
            self.assertEqual(c.tts.voz, "do-ambiente")
            self.assertEqual(cfg.ler_arquivo_env(Path(pasta) / "nao-existe"), {})


if __name__ == "__main__":
    unittest.main()
