import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import configuracao as cfg


def niveis(config, variavel):
    return [a.nivel for a in config.achados if a.variavel == variavel]


LOCAL = {
    "VOZ_STT_MOTOR": "local",
    "VOZ_STT_MODELO": "modelo-escolhido",
    "VOZ_TTS_MOTOR": "local",
    "VOZ_TTS_VOZ": "voz-escolhida",
    "VOZ_IDIOMA": "pt-BR",
}

POR_URL = {
    "VOZ_STT_MOTOR": "url",
    "VOZ_STT_URL": "http://127.0.0.1:9000/v1",
    "VOZ_STT_MODELO": "modelo-stt-do-usuario",
    "VOZ_TTS_MOTOR": "url",
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
        self.assertEqual(niveis(c, "VOZ_STT_MOTOR"), [cfg.INFO])
        self.assertEqual(niveis(c, "VOZ_TTS_MOTOR"), [cfg.INFO])
        self.assertEqual(c.porta, cfg.PORTA_PADRAO)
        self.assertEqual(c.dispositivo, "auto")

    def test_local_completo(self):
        c = cfg.carregar(LOCAL)
        self.assertFalse(c.tem_erro)
        self.assertEqual((c.stt.motor, c.stt.modelo), ("local", "modelo-escolhido"))
        self.assertEqual((c.tts.motor, c.tts.voz), ("local", "voz-escolhida"))
        self.assertIsNone(c.stt.url)

    def test_url_completo(self):
        c = cfg.carregar(POR_URL)
        self.assertFalse(c.tem_erro)
        self.assertEqual(c.stt.url, "http://127.0.0.1:9000/v1")
        self.assertEqual(c.tts.voz, "voz-do-usuario")

    def test_local_sem_modelo_ou_voz_nunca_adivinha(self):
        c = cfg.carregar({"VOZ_STT_MOTOR": "local", "VOZ_TTS_MOTOR": "local"})
        self.assertIsNone(c.stt)
        self.assertIsNone(c.tts)
        self.assertEqual(niveis(c, "VOZ_STT_MODELO"), [cfg.ERRO])
        self.assertEqual(niveis(c, "VOZ_TTS_VOZ"), [cfg.ERRO])

    def test_url_exige_endereco_modelo_e_voz(self):
        c = cfg.carregar({"VOZ_TTS_MOTOR": "url"})
        for variavel in ("VOZ_TTS_URL", "VOZ_TTS_MODELO", "VOZ_TTS_VOZ"):
            self.assertEqual(niveis(c, variavel), [cfg.ERRO], variavel)

    def test_url_invalida(self):
        c = cfg.carregar({**POR_URL, "VOZ_TTS_URL": "ftp://x"})
        self.assertIsNone(c.tts)
        self.assertEqual(niveis(c, "VOZ_TTS_URL"), [cfg.ERRO])

    def test_motor_desconhecido(self):
        c = cfg.carregar({"VOZ_STT_MOTOR": "nuvem"})
        self.assertEqual(niveis(c, "VOZ_STT_MOTOR"), [cfg.ERRO])

    def test_local_ignora_url_com_aviso(self):
        c = cfg.carregar({**LOCAL, "VOZ_STT_URL": "http://x:1/v1"})
        self.assertIsNotNone(c.stt)
        self.assertIn(cfg.AVISO, niveis(c, "VOZ_STT_MOTOR"))

    def test_sobras_sem_motor_avisam(self):
        c = cfg.carregar({"VOZ_TTS_VOZ": "v"})
        self.assertIn(cfg.AVISO, niveis(c, "VOZ_TTS_MOTOR"))

    def test_idioma(self):
        self.assertEqual(niveis(cfg.carregar({**LOCAL, "VOZ_IDIOMA": "fr-FR"}), "VOZ_IDIOMA"), [cfg.ERRO])
        sem = {k: v for k, v in LOCAL.items() if k != "VOZ_IDIOMA"}
        self.assertEqual(niveis(cfg.carregar(sem), "VOZ_IDIOMA"), [cfg.AVISO])
        self.assertEqual(niveis(cfg.carregar({}), "VOZ_IDIOMA"), [])

    def test_dispositivo(self):
        self.assertEqual(cfg.carregar({"VOZ_DISPOSITIVO": "cuda"}).dispositivo, "cuda")
        c = cfg.carregar({"VOZ_DISPOSITIVO": "gpu"})
        self.assertEqual(niveis(c, "VOZ_DISPOSITIVO"), [cfg.ERRO])

    def test_pasta_de_modelos(self):
        raiz = Path(tempfile.gettempdir()) / "ivox-raiz"
        self.assertEqual(cfg.carregar({}, raiz=raiz).modelos_dir, raiz / cfg.PASTA_MODELOS_PADRAO)
        self.assertEqual(cfg.carregar({"VOZ_MODELOS_DIR": "outra"}, raiz=raiz).modelos_dir, raiz / "outra")
        absoluta = raiz / "absoluta"
        self.assertEqual(cfg.carregar({"VOZ_MODELOS_DIR": str(absoluta)}, raiz=raiz).modelos_dir, absoluta)

    def test_ice_e_porta(self):
        c = cfg.carregar({"VOZ_ICE_SERVIDORES": "stun:a:3478, turns:b:5349", "HARNESS_PORTA": "8123"})
        self.assertEqual(c.ice_servidores, ("stun:a:3478", "turns:b:5349"))
        self.assertEqual(c.porta, 8123)
        c = cfg.carregar({"VOZ_ICE_SERVIDORES": "http://x", "HARNESS_PORTA": "99999"})
        self.assertEqual(c.ice_servidores, ())
        self.assertEqual(niveis(c, "VOZ_ICE_SERVIDORES"), [cfg.ERRO])
        self.assertEqual(niveis(c, "HARNESS_PORTA"), [cfg.ERRO])

    def test_chave_nunca_aparece_no_resumo(self):
        c = cfg.carregar({**POR_URL, "VOZ_STT_CHAVE": "segredo-123", "VOZ_TTS_CHAVE": "outro-segredo"})
        resumo = repr(cfg.resumo_publico(c))
        self.assertNotIn("segredo", resumo)
        self.assertEqual(cfg.resumo_publico(c)["stt"]["chave"], "definida")

    def test_arquivo_env_e_precedencia(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text(
                "# comentário\nexport VOZ_TTS_MOTOR='local'\nVOZ_TTS_VOZ=\"do-arquivo\"\n\nlinha-sem-igual\n",
                encoding="utf-8",
            )
            c = cfg.carregar({"VOZ_TTS_VOZ": "do-ambiente"}, env)
            self.assertEqual(c.tts.motor, "local")
            self.assertEqual(c.tts.voz, "do-ambiente")
            self.assertEqual(cfg.ler_arquivo_env(Path(pasta) / "nao-existe"), {})


if __name__ == "__main__":
    unittest.main()
