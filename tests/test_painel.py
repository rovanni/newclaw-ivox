"""O instalador chamado pelo painel do NewClaw (ADR-030, Etapa 5): opções e licenças em JSON, modo sem perguntas."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import licencas as lic
from newclaw_ivox.instalador import Cancelado, Instalador, licencas_json, opcoes

RAIZ = Path(__file__).resolve().parent.parent


class TestOpcoes(unittest.TestCase):
    def test_escolhas_do_painel_sem_nada_instalado(self):
        dados = {o["id"]: o for o in opcoes(RAIZ)}
        self.assertEqual(set(dados), {"transcricao", "sintese", "modelo", "idioma"})
        self.assertEqual([o["valor"] for o in dados["transcricao"]["opcoes"]], ["local", "desligada"])
        self.assertEqual(dados["modelo"]["visivel_se"], {"transcricao": "local"})
        self.assertIn("large-v3-turbo", [o["valor"] for o in dados["modelo"]["opcoes"]])
        # tamanho e licença medidos, com a data da medição
        turbo = next(o for o in dados["modelo"]["opcoes"] if o["valor"] == "large-v3-turbo")
        self.assertIn("licença mit", turbo["detalhe"])
        self.assertIn("medidos em", dados["modelo"]["nota"])

    def test_foto_da_lista_foi_gerada_por_comando(self):
        foto = json.loads((RAIZ / "modelos-whisper.json").read_text(encoding="utf-8"))
        self.assertTrue(foto["gerado_em"] and foto["faster_whisper"])
        self.assertTrue(all({"nome", "bytes", "tamanho", "licenca"} <= set(m) for m in foto["modelos"]))


class TestLicencasJson(unittest.TestCase):
    def test_pecas_conforme_as_escolhas(self):
        so_ouvir = {i["id"] for i in licencas_json(RAIZ, ["--transcricao", "local", "--sintese", "desligada"])["itens"]}
        so_falar = {i["id"] for i in licencas_json(RAIZ, ["--transcricao", "desligada", "--sintese", "local"])["itens"]}
        self.assertIn("faster-whisper", so_ouvir)
        self.assertNotIn("espeak-ng", so_ouvir)
        self.assertIn("espeak-ng", so_falar)
        self.assertNotIn("cuda", so_falar)  # sem transcrição local, sem CUDA


class TestSemPerguntas(unittest.TestCase):
    def pasta(self):
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        (pasta / lic.ARQUIVO_DA_LISTA).parent.mkdir(parents=True)
        shutil.copy(RAIZ / lic.ARQUIVO_DA_LISTA, pasta / lic.ARQUIVO_DA_LISTA)
        return pasta

    def inst(self, pasta, **respostas):
        saida = []
        base = {"transcricao": "local", "sintese": "local", "modelo": "large-v3-turbo", "idioma": "pt-BR"}
        return Instalador(pasta, saida=saida.append, respostas={**base, **respostas}), saida

    def test_sem_aceite_no_painel_nao_instala(self):
        pasta = self.pasta()
        inst, _ = self.inst(pasta, aceito=False)
        with self.assertRaises(Cancelado):
            inst.aceitar_licencas({lic.STT_LOCAL})
        self.assertFalse((pasta / lic.ARQUIVO_DO_REGISTRO).exists())

    def test_aceite_do_painel_fica_registrado_com_a_origem(self):
        pasta = self.pasta()
        inst, saida = self.inst(pasta, aceito=True)
        inst.aceitar_licencas({lic.STT_LOCAL, lic.TTS_LOCAL})
        registro = lic.ler_registro(pasta)
        self.assertEqual(registro["onde"], "painel do NewClaw")
        self.assertIn("espeak-ng", registro["itens"])
        self.assertTrue(any("GPL" in s for s in saida))  # a lista aparece no andamento

    def test_valor_fora_da_lista_e_erro_claro(self):
        inst, _ = self.inst(self.pasta(), transcricao="nuvem")
        with self.assertRaises(RuntimeError) as e:
            inst.perguntar_transcricao()
        self.assertIn("--transcricao", str(e.exception))

    def test_confirmacoes_valem_pelo_clique_no_painel(self):
        inst, saida = self.inst(self.pasta())
        self.assertTrue(inst.confirmar("Instalar agora?"))
        self.assertIn("confirmado no painel", saida[-1])

    def test_desligada_vira_motor_vazio(self):
        inst, _ = self.inst(self.pasta(), transcricao="desligada", sintese="desligada")
        self.assertEqual(inst.perguntar_transcricao(), {"VOZ_STT_MOTOR": ""})
        self.assertEqual(inst.perguntar_sintese(), {"VOZ_TTS_MOTOR": ""})


class TestManifesto(unittest.TestCase):
    def test_manifesto_aponta_para_comandos_que_existem(self):
        m = json.loads((RAIZ / "newclaw-integracao.json").read_text(encoding="utf-8"))
        self.assertEqual(m["formato"], 1)
        for chave in ("opcoes", "licencas", "instalar"):
            self.assertEqual(m[chave][:2], ["{python}", "instalar.py"])
        self.assertIn("--aceito-licencas", m["instalar"])  # só vem depois do clique "Li e aceito"
        self.assertIn("{newclaw_url}", m["instalar"])
        self.assertTrue(m["pacote"].startswith("https://codeload.github.com/"))


if __name__ == "__main__":
    unittest.main()
