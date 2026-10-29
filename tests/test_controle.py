import unittest

from newclaw_ivox.controle import FALAR, IGNORAR, INTERROMPER, TEXTO_MAXIMO, interpretar


class TestControle(unittest.TestCase):
    def test_falar(self):
        acao = interpretar({"t": "falar", "d": {"texto": "**Pronto.** Mais algo?"}}, fala_ligada=True)
        self.assertEqual(acao.tipo, FALAR)
        self.assertEqual(acao.frases, ("Pronto.", "Mais algo?"))

    def test_interromper_vale_mesmo_sem_fala(self):
        self.assertEqual(interpretar({"t": "interromper"}, fala_ligada=False).tipo, INTERROMPER)

    def test_falar_com_sintese_desligada(self):
        acao = interpretar({"t": "falar", "d": {"texto": "oi"}}, fala_ligada=False)
        self.assertEqual(acao.tipo, IGNORAR)
        self.assertIn("desligada", acao.motivo)

    def test_entradas_invalidas(self):
        casos = [
            None, "falar", [], {}, {"t": "outra"},
            {"t": "falar"}, {"t": "falar", "d": "texto"}, {"t": "falar", "d": {"texto": "   "}},
            {"t": "falar", "d": {"texto": 42}},
            {"t": "falar", "d": {"texto": "```\nsó código\n```"}},
            {"t": "falar", "d": {"texto": "a" * (TEXTO_MAXIMO + 1)}},
        ]
        for caso in casos:
            with self.subTest(caso=str(caso)[:40]):
                acao = interpretar(caso, fala_ligada=True)
                self.assertEqual(acao.tipo, IGNORAR)
                self.assertTrue(acao.motivo)


if __name__ == "__main__":
    unittest.main()
