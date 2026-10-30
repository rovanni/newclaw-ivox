"""Aceite das licenças de terceiros no instalador (pedido da operadora, 30/10/2026): nada é instalado sem o aceite dela."""

import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from newclaw_ivox import licencas as lic
from newclaw_ivox.dispositivo import Sistema
from newclaw_ivox.instalador import Cancelado, Instalador

RAIZ = Path(__file__).resolve().parent.parent


def pasta_com_lista(pasta: str) -> Path:
    """Pasta temporária com a lista de verdade do repositório."""
    destino = Path(pasta) / lic.ARQUIVO_DA_LISTA
    destino.parent.mkdir(parents=True)
    shutil.copy(RAIZ / lic.ARQUIVO_DA_LISTA, destino)
    return Path(pasta)


def instalador(pasta, respostas, simular=False):
    fila = list(respostas)
    saida = []

    def entrada(_):
        if not fila:
            raise EOFError
        return fila.pop(0)

    return Instalador(Path(pasta), simular=simular, entrada=entrada, saida=saida.append), saida


class TestListaDoRepositorio(unittest.TestCase):
    def test_lista_valida_com_licenca_e_link_em_toda_peca(self):
        lista = lic.carregar_lista(RAIZ)
        self.assertGreaterEqual(lista.versao, 1)
        ids = [i.id for i in lista.itens]
        self.assertEqual(len(ids), len(set(ids)), "ids repetidos")
        for i in lista.itens:
            with self.subTest(item=i.id):
                self.assertTrue(i.licenca.strip())
                self.assertTrue(i.link.strip())
                self.assertIn(i.quando, {lic.SEMPRE, lic.STT_LOCAL, lic.TTS_LOCAL, lic.CUDA})

    def test_gpl_e_proprietaria_vem_com_atencao(self):
        # Quem aceita precisa ver o aviso das peças que têm restrição de redistribuição.
        for i in lic.carregar_lista(RAIZ).itens:
            if "GPL" in i.licenca.replace("LGPL", "") or "propriet" in i.licenca:
                with self.subTest(item=i.id):
                    self.assertTrue(i.atencao, f"{i.id} tem licença com restrição e não tem 'atencao'")

    def test_so_as_pecas_da_instalacao_pedida(self):
        lista = lic.carregar_lista(RAIZ)
        so_texto = {i.id for i in lic.itens_para(lista, set())}
        completo = {i.id for i in lic.itens_para(lista, {lic.STT_LOCAL, lic.TTS_LOCAL, lic.CUDA})}
        self.assertNotIn("espeak-ng", so_texto)
        self.assertNotIn("cuda", so_texto)
        self.assertIn("pipecat", so_texto)
        self.assertTrue({"espeak-ng", "cuda", "modelo-whisper", "modelo-kokoro"} <= completo)


class TestRegistro(unittest.TestCase):
    def test_grava_e_reconhece_o_aceite(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            lista = lic.carregar_lista(raiz)
            itens = lic.itens_para(lista, {lic.STT_LOCAL})
            self.assertFalse(lic.ja_aceitas(lic.ler_registro(raiz), lista, itens))
            lic.gravar_registro(raiz, lista, itens, agora=datetime(2026, 10, 30, 12, tzinfo=timezone.utc))
            registro = lic.ler_registro(raiz)
            self.assertEqual(registro["aceito_em"], "2026-10-30T12:00:00+00:00")
            self.assertEqual(registro["licencas"]["faster-whisper"], "MIT")
            self.assertTrue(lic.ja_aceitas(registro, lista, itens))
            # Peça nova (síntese local) → pergunta de novo.
            self.assertFalse(lic.ja_aceitas(registro, lista, lic.itens_para(lista, {lic.STT_LOCAL, lic.TTS_LOCAL})))

    def test_lista_nova_pede_aceite_de_novo(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            lista = lic.carregar_lista(raiz)
            itens = lic.itens_para(lista, set())
            lic.gravar_registro(raiz, lista, itens)
            nova = lic.Lista(versao=lista.versao + 1, itens=lista.itens)
            self.assertFalse(lic.ja_aceitas(lic.ler_registro(raiz), nova, itens))

    def test_registro_corrompido_conta_como_sem_aceite(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            (raiz / lic.ARQUIVO_DO_REGISTRO).write_text("{não é json", encoding="utf-8")
            self.assertIsNone(lic.ler_registro(raiz))

    def test_so_a_palavra_exata_aceita(self):
        self.assertTrue(lic.resposta_aceita("  Aceito "))
        for r in ("", "s", "sim", "ok", "aceito tudo", "não aceito"):
            with self.subTest(resposta=r):
                self.assertFalse(lic.resposta_aceita(r))


class TestNoInstalador(unittest.TestCase):
    GRUPOS = {lic.STT_LOCAL, lic.TTS_LOCAL}

    def test_mostra_licenca_link_e_atencao_e_guarda_o_aceite(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            inst, saida = instalador(raiz, ["aceito"])
            inst.aceitar_licencas(self.GRUPOS)
            texto = "\n".join(saida)
            self.assertIn("GPL-3.0", texto)
            self.assertIn("https://github.com/espeak-ng/espeak-ng", texto)
            self.assertIn("ATENÇÃO", texto)
            self.assertTrue((raiz / lic.ARQUIVO_DO_REGISTRO).is_file())

    def test_recusar_cancela_sem_gravar_nada(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            for resposta in ("s", "não"):
                with self.subTest(resposta=resposta):
                    inst, _ = instalador(raiz, [resposta])
                    with self.assertRaises(Cancelado):
                        inst.aceitar_licencas(self.GRUPOS)
            self.assertFalse((raiz / lic.ARQUIVO_DO_REGISTRO).exists())

    def test_ja_aceitas_nao_pergunta_de_novo(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            instalador(raiz, ["aceito"])[0].aceitar_licencas(self.GRUPOS)
            inst, saida = instalador(raiz, [])  # sem resposta nenhuma: se perguntasse, cancelaria
            inst.aceitar_licencas(self.GRUPOS)
            self.assertTrue(any("Já aceitas" in s for s in saida))

    def test_simulacao_pergunta_mas_nao_grava(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            inst, _ = instalador(raiz, ["aceito"], simular=True)
            inst.aceitar_licencas(self.GRUPOS)
            self.assertFalse((raiz / lic.ARQUIVO_DO_REGISTRO).exists())

    @unittest.skipIf(sys.platform == "darwin", "no macOS o instalador nunca usa CUDA")
    def test_cuda_so_entra_com_gpu_nvidia_e_transcricao_local(self):
        with tempfile.TemporaryDirectory() as pasta:
            inst, _ = instalador(pasta, [])
            com_gpu = Sistema(sistema="Windows", python="3.12", gpus_nvidia=("RTX",), espaco_livre_bytes=None)
            sem_gpu = Sistema(sistema="Windows", python="3.12", gpus_nvidia=(), espaco_livre_bytes=None)
            self.assertIn(lic.CUDA, inst.grupos(com_gpu, True, False))
            self.assertNotIn(lic.CUDA, inst.grupos(sem_gpu, True, True))
            self.assertNotIn(lic.CUDA, inst.grupos(com_gpu, False, True))


class TestOrdemNoInstalador(unittest.TestCase):
    def test_aceite_vem_antes_de_instalar(self):
        """Recusar as licenças interrompe antes de qualquer comando de instalação."""
        with tempfile.TemporaryDirectory() as pasta:
            raiz = pasta_com_lista(pasta)
            # transcrição local, síntese desligada, e "não" às licenças
            inst, saida = instalador(raiz, ["1", "3", "não"])
            executados = []
            inst.executar = lambda comando: executados.append(comando)
            with self.assertRaises(Cancelado):
                inst.rodar()
            self.assertEqual(executados, [])
            self.assertFalse(any("Instalar agora?" in s for s in saida))


if __name__ == "__main__":
    unittest.main()
