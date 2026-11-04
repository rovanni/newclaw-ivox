"""Medição da transcrição (`medir-stt`): a conta da taxa de erro de palavras e o apoio de vocabulário chegando ao Whisper.

Origem: 04/11/2026, a operadora achou a transcrição da janela pior que o ditado do navegador. Os erros dos testes dela
eram nomes próprios ("Cornelia Procobre" por Cornélio Procópio, "Rigger" por River). Antes de trocar o modelo ou criar
o dicionário, a medição compara modelos e apoios com a voz dela. Nada aqui carrega modelo nem toca a GPU.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from newclaw_ivox import comandos
from newclaw_ivox import configuracao as cfg
from newclaw_ivox import stt_local

TEM_PIPECAT = importlib.util.find_spec("pipecat") is not None


class TaxaDeErroDePalavras(unittest.TestCase):
    def test_igual_nao_tem_erro(self):
        self.assertEqual(stt_local.erros_de_palavras("Qual é a previsão do tempo?", "qual é a previsão do tempo"), (0, 6))

    def test_pontuacao_e_maiusculas_nao_contam(self):
        self.assertEqual(stt_local.erros_de_palavras("E o River?", "e o river."), (0, 3))

    def test_acento_conta(self):
        # "Cornélio" sem acento é outra grafia: o dicionário existe justamente para acertar o nome como se escreve.
        self.assertEqual(stt_local.erros_de_palavras("Cornélio Procópio", "Cornelio Procópio"), (1, 2))

    def test_caso_real_da_operadora(self):
        erros, palavras = stt_local.erros_de_palavras(
            "Qual a previsão do tempo para Cornélio Procópio?", "Qual a previsão do tempo para a Cornelia Procobre?")
        self.assertEqual((erros, palavras), (3, 8))  # uma inserção ("a") e duas trocas

    def test_omissao_e_insercao(self):
        self.assertEqual(stt_local.erros_de_palavras("gera em PowerPoint editável", "gera PowerPoint"), (2, 4))
        self.assertEqual(stt_local.erros_de_palavras("me envia", "e me envia agora"), (2, 2))

    def test_texto_dito_vazio(self):
        self.assertEqual(stt_local.erros_de_palavras("", "obrigado"), (1, 0))


class Argumentos(unittest.TestCase):
    def test_sem_argumentos_mostra_o_uso(self):
        self.assertEqual(comandos.medir_stt([]), 64)

    def test_numero_de_gravacoes_e_frases_diferente_recusa(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            (pasta / "a.wav").write_bytes(b"")
            frases = pasta / "frases.txt"
            frases.write_text("primeira\nsegunda\n", encoding="utf-8")
            self.assertEqual(comandos.medir_stt(["--audios", str(pasta), "--frases", str(frases)]), 1)


@unittest.skipUnless(TEM_PIPECAT, "Pipecat não instalado neste ambiente")
class VocabularioChegaAoWhisper(unittest.TestCase):
    def _config(self, d: str) -> cfg.Configuracao:
        return cfg.carregar({"VOZ_STT_MOTOR": "local", "VOZ_STT_MODELO": "large-v3-turbo", "VOZ_IDIOMA": "pt-BR"},
                            None, Path(d))

    def test_sem_apoio_e_o_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            servico = stt_local.servico_da_linha(self._config(d), stt_local.DonoDoModelo())
            self.assertIsNone(servico._settings.hotwords)
            self.assertIsNone(servico._settings.initial_prompt)

    def test_hotwords_e_initial_prompt_repassados(self):
        with tempfile.TemporaryDirectory() as d:
            servico = stt_local.servico_da_linha(self._config(d), stt_local.DonoDoModelo(),
                                                 hotwords="Cornélio Procópio River", initial_prompt="Vocabulário: River.")
            self.assertEqual(servico._settings.hotwords, "Cornélio Procópio River")
            self.assertEqual(servico._settings.initial_prompt, "Vocabulário: River.")


if __name__ == "__main__":
    unittest.main()
