import json
import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import misturas

BASE = ("bm_george", "pm_alex", "pf_dora")
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
        self.assertEqual([m.nome for m in lista], ["george-alex-1", "george-alex-2", "george-alex-3"])
        self.assertEqual(lista[0].rotulo, "George e Alex — versão 1")
        self.assertEqual(dict(lista[0].pesos), {"bm_george": 0.7, "pm_alex": 0.3})

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
