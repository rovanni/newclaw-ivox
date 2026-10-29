import unittest

from newclaw_ivox.frases import LIMITE_PADRAO, dividir_em_frases, limpar_marcacao, preparar_para_fala


class TestLimpeza(unittest.TestCase):
    def test_enfase_titulo_lista_link(self):
        md = "# Resumo\n\n**Pronto!** O arquivo *novo* está em [relatorio](http://x/y).\n- item um\n2. item dois\n> nota"
        limpo = limpar_marcacao(md)
        for sinal in ("#", "**", "*", "[", "](", "- ", "2. ", "> "):
            self.assertNotIn(sinal, limpo)
        self.assertIn("Pronto! O arquivo novo está em relatorio.", limpo)
        self.assertIn("item um", limpo)
        self.assertIn("nota", limpo)

    def test_codigo(self):
        md = "Rode isto:\n```bash\nnpm run build\n```\nE use `npm test` depois."
        limpo = limpar_marcacao(md)
        self.assertNotIn("npm run build", limpo)
        self.assertNotIn("`", limpo)
        self.assertIn("E use npm test depois.", limpo)
        self.assertNotIn("```", limpar_marcacao("início ```sem fechar"))

    def test_tabela(self):
        md = "| Nome | Valor |\n|---|---:|\n| a | 1 |"
        self.assertEqual(limpar_marcacao(md), "Nome, Valor\n\na, 1")

    def test_preserva_texto_comum(self):
        texto = "O valor é 3.5 e o site é www.exemplo.com; nada_de_sublinhado some, nem 2*3."
        self.assertEqual(limpar_marcacao(texto), texto)


class TestDivisao(unittest.TestCase):
    def test_frases_por_pontuacao(self):
        self.assertEqual(
            dividir_em_frases("Oi. Tudo bem? Sim!  Ótimo… Fim"),
            ["Oi.", "Tudo bem?", "Sim!", "Ótimo…", "Fim"],
        )

    def test_numero_e_endereco_nao_partem(self):
        self.assertEqual(dividir_em_frases("Custa 3.5 reais em www.x.com hoje."), ["Custa 3.5 reais em www.x.com hoje."])

    def test_quebra_de_linha_separa(self):
        self.assertEqual(dividir_em_frases("primeira linha\nsegunda linha"), ["primeira linha", "segunda linha"])

    def test_descarta_pedacos_sem_conteudo(self):
        self.assertEqual(dividir_em_frases("... \n --- \n ok."), ["ok."])
        self.assertEqual(dividir_em_frases(""), [])

    def test_frase_longa_parte_na_pausa(self):
        frase = ("Esta é uma frase bem comprida, com várias partes separadas por vírgulas, que passa do limite; "
                 "depois dela vem mais texto para o motor de voz dizer sem travar o sintetizador do usuário.")
        pedacos = dividir_em_frases(frase, limite=80)
        self.assertGreater(len(pedacos), 1)
        self.assertTrue(all(len(p) <= 80 for p in pedacos), pedacos)
        self.assertEqual(" ".join(pedacos), frase)
        self.assertTrue(pedacos[0].endswith(","), pedacos)

    def test_palavra_gigante_corta_seco(self):
        pedacos = dividir_em_frases("x" * 100, limite=40)
        self.assertEqual([len(p) for p in pedacos], [40, 40, 20])

    def test_limite_padrao_respeitado(self):
        texto = " ".join(["Palavra"] * 200) + "."
        self.assertTrue(all(len(p) <= LIMITE_PADRAO for p in dividir_em_frases(texto)))

    def test_limite_minimo(self):
        with self.assertRaises(ValueError):
            dividir_em_frases("a", limite=5)

    def test_preparar_para_fala(self):
        self.assertEqual(
            preparar_para_fala("## Feito\n**Criei** o arquivo. Quer *mais* algo?"),
            ["Feito", "Criei o arquivo.", "Quer mais algo?"],
        )


if __name__ == "__main__":
    unittest.main()
