import json
import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import misturas

BASE = ("bm_george", "pm_alex", "pf_dora", "am_michael", "bm_daniel", "bm_fable")
RAIZ = Path(__file__).resolve().parent.parent


def arquivo(conteudo) -> Path:
    pasta = Path(tempfile.mkdtemp())
    caminho = pasta / misturas.ARQUIVO
    caminho.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo), encoding="utf-8")
    return caminho


def voz(nome="nova", rotulo="Nova", mistura=None):
    return {"nome": nome, "rotulo": rotulo, "mistura": mistura or {"bm_george": 0.5, "pm_alex": 0.5}}


class TestMisturas(unittest.TestCase):
    def test_arquivo_do_repositorio_e_valido(self):
        lista = misturas.carregar(RAIZ / misturas.ARQUIVO, BASE)
        self.assertEqual([m.nome for m in lista], [
            "george-michael-1", "george-michael-2", "george-michael-3", "daniel-george", "daniel-suave", "alex-limpo",
            "george-alex-1", "george-alex-2", "george-alex-3",
        ])
        por_nome = {m.nome: m for m in lista}
        self.assertEqual(por_nome["george-alex-1"].rotulo, "George & Alex 1 (70% George / 30% Alex)")
        self.assertEqual(dict(por_nome["george-alex-1"].pesos), {"bm_george": 0.7, "pm_alex": 0.3})
        self.assertEqual(dict(por_nome["alex-limpo"].pesos), {"bm_daniel": 0.8, "pm_alex": 0.2})
        self.assertEqual(dict(por_nome["daniel-suave"].pesos), {"bm_daniel": 0.7, "bm_fable": 0.3})

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
