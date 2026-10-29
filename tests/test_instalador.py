import tempfile
import unittest
from pathlib import Path

from newclaw_ivox.instalador import Cancelado, Instalador


def instalador(pasta, respostas, simular=False):
    fila = list(respostas)
    saida = []

    def entrada(_):
        if not fila:
            raise EOFError
        return fila.pop(0)

    return Instalador(Path(pasta), simular=simular, entrada=entrada, saida=saida.append), saida


class TestConversa(unittest.TestCase):
    def test_escolha_sem_padrao_insiste(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, saida = instalador(pasta, ["", "9", "2"])
            self.assertEqual(inst.escolher("?", [("a", "A"), ("b", "B")]), "b")
            self.assertEqual(sum("não reconhecida" in s for s in saida), 2)

    def test_confirmar(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, _ = instalador(pasta, ["talvez", "S"])
            self.assertTrue(inst.confirmar("?"))

    def test_entrada_encerrada_cancela(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, _ = instalador(pasta, [])
            with self.assertRaises(Cancelado):
                inst.escolher("?", [("a", "A")])

    def test_transcricao_por_servidor(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, _ = instalador(pasta, ["2", "http://srv:1/v1", "modelo-do-srv", ""])
            self.assertEqual(
                inst.perguntar_transcricao(),
                {"VOZ_STT_MOTOR": "url", "VOZ_STT_URL": "http://srv:1/v1", "VOZ_STT_MODELO": "modelo-do-srv", "VOZ_STT_CHAVE": ""},
            )

    def test_sintese_local_e_por_servidor(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, _ = instalador(pasta, ["1"])
            self.assertEqual(inst.perguntar_sintese(), {"VOZ_TTS_MOTOR": "local"})
            inst, _ = instalador(pasta, ["2", "http://srv:2/v1", "m", "v", "k"])
            self.assertEqual(
                inst.perguntar_sintese(),
                {"VOZ_TTS_MOTOR": "url", "VOZ_TTS_URL": "http://srv:2/v1", "VOZ_TTS_MODELO": "m", "VOZ_TTS_VOZ": "v", "VOZ_TTS_CHAVE": "k"},
            )
            inst, _ = instalador(pasta, ["3"])
            self.assertEqual(inst.perguntar_sintese(), {"VOZ_TTS_MOTOR": ""})

    def test_recusar_instalacao_cancela_sem_executar(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, saida = instalador(pasta, ["n"])
            from newclaw_ivox.dispositivo import Sistema

            with self.assertRaises(Cancelado):
                inst.preparar_ambiente(Sistema("x", "3.12", (), None), com_stt_local=True)
            self.assertFalse(any(s.lstrip().startswith("$") for s in saida))


class TestEnv(unittest.TestCase):
    def test_atualiza_so_as_chaves_de_voz(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text("# meu comentário\nNEWCLAW_URL=http://x\nVOZ_IDIOMA=en-US\n", encoding="utf-8")
            inst, saida = instalador(pasta, [])
            inst.gravar_env({"VOZ_IDIOMA": "pt-BR", "VOZ_STT_MOTOR": "local", "VOZ_STT_CHAVE": "segredo"})
            texto = env.read_text(encoding="utf-8")
            self.assertIn("# meu comentário\nNEWCLAW_URL=http://x\nVOZ_IDIOMA=pt-BR\n", texto)
            self.assertIn("VOZ_STT_MOTOR=local", texto)
            self.assertEqual(texto.count("VOZ_IDIOMA="), 1)
            self.assertFalse(any("segredo" in s for s in saida))

    def test_voz_ja_escolhida_nao_e_apagada(self):
        # O instalador não manda VOZ_TTS_VOZ na síntese local: a voz que a pessoa já escolheu fica.
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text("VOZ_TTS_VOZ=bm_george\n", encoding="utf-8")
            inst, _ = instalador(pasta, [])
            inst.gravar_env({"VOZ_TTS_MOTOR": "local", "VOZ_IDIOMA": "pt-BR"})
            self.assertIn("VOZ_TTS_VOZ=bm_george", env.read_text(encoding="utf-8"))

    def test_simulacao_nao_escreve(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, _ = instalador(pasta, [], simular=True)
            inst.gravar_env({"VOZ_IDIOMA": "pt-BR"})
            self.assertFalse((Path(pasta) / ".env").exists())


if __name__ == "__main__":
    unittest.main()
