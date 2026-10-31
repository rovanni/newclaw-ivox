import unittest

from newclaw_ivox.controle import (
    FALAR, IGNORAR, INTERROMPER, LISTAR_VOZES, TEXTO_MAXIMO, TROCAR_VOZ, VELOCIDADE, interpretar,
)

VOZES = ("bm_george", "pf_dora", "pm_alex")


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


class TestVozNaInterface(unittest.TestCase):
    def test_listar_vozes(self):
        acao = interpretar({"t": "vozes"}, fala_ligada=True, voz_atual="bm_george", vozes=VOZES)
        self.assertEqual((acao.tipo, acao.voz), (LISTAR_VOZES, "bm_george"))

    def test_trocar_voz(self):
        acao = interpretar({"t": "voz", "d": {"voz": "pf_dora"}}, fala_ligada=True, voz_atual="bm_george", vozes=VOZES)
        self.assertEqual((acao.tipo, acao.voz), (TROCAR_VOZ, "pf_dora"))

    def test_voz_desconhecida_e_ignorada(self):
        for d in ({"voz": "voz_do_filme"}, {"voz": 3}, {}, "pf_dora"):
            with self.subTest(d=d):
                acao = interpretar({"t": "voz", "d": d}, fala_ligada=True, vozes=VOZES)
                self.assertEqual(acao.tipo, IGNORAR)

    def test_sem_sintese_local_nao_ha_troca(self):
        self.assertEqual(interpretar({"t": "voz", "d": {"voz": "pf_dora"}}, fala_ligada=True).tipo, IGNORAR)
        self.assertEqual(interpretar({"t": "vozes"}, fala_ligada=True).tipo, IGNORAR)

    def test_falar_sem_voz_escolhida(self):
        acao = interpretar({"t": "falar", "d": {"texto": "oi"}}, fala_ligada=True, voz_atual=None, vozes=VOZES)
        self.assertEqual(acao.tipo, IGNORAR)
        self.assertIn("escolha uma na interface", acao.motivo)
        acao = interpretar({"t": "falar", "d": {"texto": "oi"}}, fala_ligada=True, voz_atual="pm_alex", vozes=VOZES)
        self.assertEqual(acao.tipo, FALAR)


if __name__ == "__main__":
    unittest.main()


class TestVelocidade(unittest.TestCase):
    VOZES = ("pf_dora",)

    def test_velocidade_na_faixa_do_kokoro(self):
        for v in (0.5, 1, 1.25, 2.0):
            acao = interpretar({"t": "velocidade", "d": {"velocidade": v}}, True, vozes=self.VOZES)
            self.assertEqual((acao.tipo, acao.velocidade), (VELOCIDADE, float(v)))

    def test_fora_da_faixa_ou_invalida_e_ignorada(self):
        for v in (0.4, 2.1, "1.2", None, True, float("nan")):
            acao = interpretar({"t": "velocidade", "d": {"velocidade": v}}, True, vozes=self.VOZES)
            self.assertEqual(acao.tipo, IGNORAR, v)

    def test_sem_sintese_local_nao_ha_velocidade(self):
        self.assertEqual(interpretar({"t": "velocidade", "d": {"velocidade": 1.2}}, True, vozes=None).tipo, IGNORAR)

