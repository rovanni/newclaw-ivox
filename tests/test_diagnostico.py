import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import diagnostico

COMPLETA = {
    "VOZ_TTS_MOTOR": "url",
    "VOZ_TTS_URL": "http://127.0.0.1:9001/v1",
    "VOZ_TTS_MODELO": "m",
    "VOZ_TTS_VOZ": "v",
    "VOZ_TTS_CHAVE": "segredo-nao-mostrar",
    "VOZ_STT_MOTOR": "local",
    "VOZ_STT_MODELO": "modelo-escolhido",
    "VOZ_IDIOMA": "pt-BR",
}


def rodar(argumentos, ambiente):
    saida = io.StringIO()
    with tempfile.TemporaryDirectory() as pasta, contextlib.redirect_stdout(saida):
        codigo = diagnostico.principal(argumentos, ambiente, Path(pasta))
    return codigo, saida.getvalue()


class TestDiagnostico(unittest.TestCase):
    def test_sem_configuracao_sai_com_aviso_claro(self):
        codigo, texto = rodar([], {})
        self.assertEqual(codigo, diagnostico.SAIDA_NADA_CONFIGURADO)
        self.assertIn("Nada a fazer", texto)
        self.assertIn("instalar.py", texto)

    def test_erro(self):
        codigo, texto = rodar([], {"VOZ_TTS_MOTOR": "url"})
        self.assertEqual(codigo, diagnostico.SAIDA_ERRO)
        self.assertIn("[ERRO ] VOZ_TTS_MODELO", texto)
        self.assertIn("[ERRO ] VOZ_TTS_VOZ", texto)

    def test_ok_sem_vazar_chave(self):
        codigo, texto = rodar([], COMPLETA)
        self.assertEqual(codigo, diagnostico.SAIDA_OK)
        self.assertIn("Configuração completa.", texto)
        self.assertIn("Transcrição: nesta máquina (modelo modelo-escolhido)", texto)
        self.assertNotIn("segredo", texto)

    def test_sintese_local_sem_voz_inicial(self):
        codigo, texto = rodar([], {"VOZ_TTS_MOTOR": "local", "VOZ_IDIOMA": "pt-BR"})
        self.assertEqual(codigo, diagnostico.SAIDA_OK)
        self.assertIn("Síntese: nesta máquina (voz escolhida na interface)", texto)

    def test_json(self):
        codigo, texto = rodar(["--json"], COMPLETA)
        dados = json.loads(texto)
        self.assertEqual(dados["codigo"], codigo)
        self.assertEqual(dados["tts"]["chave"], "definida")
        self.assertEqual(dados["stt"]["motor"], "local")
        self.assertNotIn("segredo", texto)


if __name__ == "__main__":
    unittest.main()
