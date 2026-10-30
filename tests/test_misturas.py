import json
import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import misturas

BASE = ("bm_george", "pm_alex", "pf_dora", "am_michael", "bm_daniel", "bm_fable")
RAIZ = Path(__file__).resolve().parent.parent


def arquivo(conteudo) -> Path:
    pasta = Path(tempfile.mkdtemp())
    caminho = pasta / "vozes-teste.json"
    caminho.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo), encoding="utf-8")
    return caminho


def voz(nome="nova", rotulo="Nova", mistura=None):
    return {"nome": nome, "rotulo": rotulo, "mistura": mistura or {"bm_george": 0.5, "pm_alex": 0.5}}


class TestMisturas(unittest.TestCase):
    def test_arquivo_do_repositorio_e_valido(self):
        lista = misturas.carregar(RAIZ / misturas.PASTA, BASE)
        self.assertEqual([m.nome for m in lista], [
            "alex-limpo", "daniel-george", "daniel-suave", "george-alex-1", "george-alex-2", "george-alex-3",
            "george-michael-1", "george-michael-2", "george-michael-3",
        ])
        por_nome = {m.nome: m for m in lista}
        self.assertEqual(por_nome["george-alex-1"].rotulo, "George & Alex 1 (70% George / 30% Alex)")
        self.assertEqual(dict(por_nome["george-alex-1"].pesos), {"bm_george": 0.7, "pm_alex": 0.3})
        self.assertEqual(dict(por_nome["alex-limpo"].pesos), {"bm_daniel": 0.8, "pm_alex": 0.2})
        self.assertEqual(dict(por_nome["daniel-suave"].pesos), {"bm_daniel": 0.7, "bm_fable": 0.3})

    def test_pasta_um_arquivo_por_voz_em_ordem_de_nome(self):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "b-voz.json").write_text(json.dumps(voz(nome="b-voz")), encoding="utf-8")
        (pasta / "a-voz.json").write_text(json.dumps(voz(nome="a-voz")), encoding="utf-8")
        (pasta / "README.md").write_text("não é voz", encoding="utf-8")
        self.assertEqual([m.nome for m in misturas.carregar(pasta, BASE)], ["a-voz", "b-voz"])

    def test_pasta_erro_diz_o_arquivo_e_nome_repetido_entre_arquivos_recusa(self):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "boa.json").write_text(json.dumps(voz(nome="igual")), encoding="utf-8")
        (pasta / "copia.json").write_text(json.dumps(voz(nome="igual")), encoding="utf-8")
        with self.assertRaisesRegex(misturas.MisturaInvalida, r"copia\.json.*já existe"):
            misturas.carregar(pasta, BASE)
        (pasta / "copia.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(misturas.MisturaInvalida, r"copia\.json.*JSON inválido"):
            misturas.carregar(pasta, BASE)

    def test_ausente_e_nenhuma(self):
        self.assertEqual(misturas.carregar(Path(tempfile.gettempdir()) / "nao-existe.json", BASE), [])

    def test_erros_tem_motivo(self):
        casos = {
            "JSON inválido": "{",
            "sem espaços": {"vozes": [voz(nome="tem espaço")]},
            "já existe": {"vozes": [voz(nome="pf_dora")]},
            "rotulo": {"vozes": [voz(rotulo=" ")]},
            "pelo menos duas": {"vozes": [voz(mistura={"bm_george": 1})]},
            "não está no arquivo": {"vozes": [voz(mistura={"bm_george": 0.5, "voz_do_filme": 0.5})]},
            "maior que zero": {"vozes": [voz(mistura={"bm_george": 1.5, "pm_alex": -0.5})]},
            "somam": {"vozes": [voz(mistura={"bm_george": 0.6, "pm_alex": 0.6})]},
        }
        for motivo, conteudo in casos.items():
            with self.subTest(motivo=motivo):
                with self.assertRaises(misturas.MisturaInvalida) as ctx:
                    misturas.carregar(arquivo(conteudo), BASE)
                self.assertIn(motivo, str(ctx.exception))

    def test_nome_repetido(self):
        with self.assertRaises(misturas.MisturaInvalida):
            misturas.carregar(arquivo({"vozes": [voz(), voz()]}), BASE)


if __name__ == "__main__":
    unittest.main()
