"""O dono do modelo do Whisper (ADR-037 do NewClaw): carregar e descarregar só por pedido, um modelo por processo.

Iniciar a integração, carregar o modelo e abrir a janela são três coisas separadas: conectar não carrega; várias janelas
pedindo juntas carregam uma cópia só (achado de 31/10/2026: três abas reabertas, ~5,7 GB de VRAM); a memória da GPU é
medida antes e depois; falta de memória ou falha na GPU viram pergunta (CPU ou cancelar), nunca troca silenciosa; a
descarga espera a transcrição em andamento. Nada aqui carrega modelo de verdade nem toca a GPU.
"""

import importlib.util
import tempfile
import threading
import time
import unittest
from pathlib import Path

from newclaw_ivox import configuracao as cfg
from newclaw_ivox import dispositivo as disp
from newclaw_ivox import modelos, stt_local

TEM_PIPECAT = importlib.util.find_spec("pipecat") is not None
GB = 2**30
COM_CUDA = disp.Motor(gpus_cuda=1, tipos={"cuda": ("float16",), "cpu": ("int8",)})
SO_CPU = disp.Motor(gpus_cuda=0, tipos={"cuda": (), "cpu": ("int8",)})


def gpu(usada_gb: float, total_gb: float = 16):
    return (disp.MemoriaGpu("GPU de teste", int(total_gb * GB), int(usada_gb * GB), int((total_gb - usada_gb) * GB)),)


class Falsos:
    """Carga, descarga e medições de mentira; a memória "usada" sobe ao carregar na GPU e desce ao descarregar."""

    def __init__(self, motor=COM_CUDA, usada_gb=1.0, consumo_gb=2.2, falhar_na_gpu=False, demora=0.0, nvml=True):
        self.motor, self.usada, self.consumo, self.falhar_na_gpu = motor, usada_gb, consumo_gb, falhar_na_gpu
        self.demora, self.nvml = demora, nvml
        self.cargas: list[tuple[str, str]] = []
        self.descargas = 0
        self.agora = 1000.0

    def carregar(self, pasta, dispositivo, tipo, idioma):
        time.sleep(self.demora)
        if dispositivo == "cuda" and self.falhar_na_gpu:
            raise RuntimeError("CUDA failed with error out of memory")
        self.cargas.append((dispositivo, tipo))
        if dispositivo == "cuda":
            self.usada += self.consumo
        return object()

    def descarregar(self, modelo):
        self.descargas += 1
        self.usada -= self.consumo

    def memoria(self):
        return gpu(self.usada) if self.nvml else None

    def dono(self):
        return stt_local.DonoDoModelo(carregar=self.carregar, descarregar=self.descarregar,
                                      medir_motor=lambda: self.motor, medir_memoria=self.memoria,
                                      relogio=lambda: self.agora)


class ComModelo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.modelos_dir = Path(self.tmp.name)
        pasta = modelos.pasta_do_modelo(self.modelos_dir, "large-v3-turbo")
        pasta.mkdir(parents=True)
        (pasta / modelos.ARQUIVO_DO_MODELO).write_bytes(b"")
        self.config = cfg.Configuracao(
            stt=cfg.Servico(cfg.LOCAL, "large-v3-turbo"), tts=None, idioma="pt", dispositivo="auto",
            modelos_dir=self.modelos_dir, ice_servidores=(), porta=7860,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def esperar(self, dono, estados=(stt_local.CARREGADO, stt_local.FALHA)):
        for _ in range(200):
            if dono.estado()["estado"] in estados:
                return dono.estado()
            time.sleep(0.01)
        self.fail(f"estado ficou em {dono.estado()['estado']}")


class TestCarregar(ComModelo):
    def test_comeca_descarregado(self):
        f = Falsos()
        self.assertEqual(f.dono().estado()["estado"], stt_local.DESCARREGADO)
        self.assertEqual(f.cargas, [], "ninguém pediu: nada carregado")

    def test_carga_mede_e_grava_o_consumo(self):
        f = Falsos()
        dono = f.dono()
        e = dono.pedir_carga(self.config, esperar=True)
        self.assertEqual(e["estado"], stt_local.CARREGADO)
        self.assertEqual(f.cargas, [("cuda", "float16")])
        self.assertAlmostEqual(e["consumo_bytes"] / GB, 2.2, places=2)
        self.assertIn("diferença", e["consumo_fonte"], "a fonte da medida aparece para a pessoa")
        self.assertEqual(stt_local.ler_consumo(self.modelos_dir), {"large-v3-turbo|cuda|float16": e["consumo_bytes"]})

    def test_varias_janelas_juntas_carregam_uma_copia(self):
        f = Falsos(demora=0.2)
        dono = f.dono()
        fios = [threading.Thread(target=dono.pedir_carga, args=(self.config,)) for _ in range(3)]
        for t in fios:
            t.start()
        for t in fios:
            t.join()
        self.esperar(dono)
        self.assertEqual(len(f.cargas), 1, "três pedidos juntos: uma carga só")

    def test_memoria_insuficiente_pergunta_sem_carregar(self):
        stt_local.gravar_consumo(self.modelos_dir, "large-v3-turbo|cuda|float16", int(2.2 * GB))
        f = Falsos(usada_gb=15.0)  # 1 GB livre, a última carga ocupou 2,2 GB
        e = f.dono().pedir_carga(self.config)
        self.assertEqual(e["estado"], stt_local.DESCARREGADO)
        self.assertEqual(e["pergunta"], "cpu")
        self.assertIn("1.0 GB livres", e["aviso"])
        self.assertEqual(f.cargas, [], "não tenta carregar sem a pessoa responder")

    def test_primeira_vez_sem_consumo_medido_carrega(self):
        f = Falsos(usada_gb=15.0)
        e = f.dono().pedir_carga(self.config, esperar=True)
        self.assertIsNone(e["consumo_medido_bytes"], "nada medido antes: ausência, não estimativa")
        self.assertEqual(e["estado"], stt_local.CARREGADO)

    def test_falha_na_gpu_vira_pergunta_e_a_cpu_so_com_o_pedido(self):
        f = Falsos(falhar_na_gpu=True)
        dono = f.dono()
        dono.pedir_carga(self.config)
        e = self.esperar(dono)
        self.assertEqual(e["estado"], stt_local.FALHA)
        self.assertEqual(e["pergunta"], "cpu")
        self.assertIn("out of memory", e["erro"], "a mensagem da biblioteca chega como veio")
        self.assertEqual(f.cargas, [], "não trocou para a CPU sozinho")
        e = dono.pedir_carga(self.config, na_cpu=True, esperar=True)
        self.assertEqual((e["estado"], f.cargas), (stt_local.CARREGADO, [("cpu", "int8")]))

    def test_sem_nvml_carrega_sem_medir(self):
        f = Falsos(nvml=False)
        e = f.dono().pedir_carga(self.config, esperar=True)
        self.assertEqual(e["estado"], stt_local.CARREGADO)
        self.assertIsNone(e["memoria_antes"])
        self.assertNotIn("consumo_bytes", e)
        self.assertEqual(stt_local.ler_consumo(self.modelos_dir), {})

    def test_sem_cuda_carrega_na_cpu_e_nao_mede_vram(self):
        f = Falsos(motor=SO_CPU)
        e = f.dono().pedir_carga(self.config, esperar=True)
        self.assertEqual((e["dispositivo"], e["memoria_antes"]), ("cpu", None))

    def test_modelo_nao_instalado(self):
        config = cfg.Configuracao(stt=cfg.Servico(cfg.LOCAL, "outro"), tts=None, idioma="pt", dispositivo="auto",
                                  modelos_dir=self.modelos_dir, ice_servidores=(), porta=7860)
        with self.assertRaises(stt_local.SttIndisponivel):
            Falsos().dono().pedir_carga(config)


class TestDescarregar(ComModelo):
    def test_descarrega_e_mede_o_que_voltou(self):
        f = Falsos()
        dono = f.dono()
        dono.pedir_carga(self.config, esperar=True)
        e = dono.descarregar()
        self.assertEqual((e["estado"], f.descargas), (stt_local.DESCARREGADO, 1))
        self.assertAlmostEqual(e["liberado_bytes"] / GB, 2.2, places=2)

    def test_espera_a_transcricao_em_andamento(self):
        f = Falsos()
        dono = f.dono()
        dono.pedir_carga(self.config, esperar=True)
        self.assertIsNotNone(dono.tomar(), "uma transcrição em andamento")
        fio = threading.Thread(target=dono.descarregar)
        fio.start()
        time.sleep(0.1)
        self.assertEqual(dono.estado()["estado"], stt_local.DESCARREGANDO)
        self.assertEqual(f.descargas, 0, "não tira o modelo no meio da frase")
        self.assertIsNone(dono.tomar(), "descarregando: trecho novo não é transcrito")
        dono.devolver()
        fio.join(2)
        self.assertEqual((dono.estado()["estado"], f.descargas), (stt_local.DESCARREGADO, 1))

    def test_descarregar_enquanto_carrega_e_recusado(self):
        f = Falsos(demora=0.3)
        dono = f.dono()
        dono.pedir_carga(self.config)
        with self.assertRaises(stt_local.PedidoRecusado):
            dono.descarregar()
        self.esperar(dono)

    def test_sem_modelo_tomar_devolve_nada(self):
        self.assertIsNone(Falsos().dono().tomar())

    def test_ociosidade_desligada_por_padrao_e_ligada_descarrega(self):
        f = Falsos()
        dono = f.dono()
        dono.pedir_carga(self.config, esperar=True)
        f.agora += 3600
        self.assertFalse(dono.descarregar_se_ocioso(None), "D2 desligado: nunca descarrega sozinho")
        self.assertFalse(dono.descarregar_se_ocioso(120), "uma hora parado com limite de duas: fica")
        self.assertTrue(dono.descarregar_se_ocioso(30))
        self.assertEqual(dono.estado()["estado"], stt_local.DESCARREGADO)


@unittest.skipUnless(TEM_PIPECAT, "Pipecat não instalado neste Python")
class TestServicoDaLinha(ComModelo):
    def test_idioma_da_configuracao_vira_o_codigo_do_whisper(self):
        # Achado da prova real (31/10/2026): a carga recebia "pt-BR" cru e o faster-whisper recusava.
        from pipecat.services.whisper.stt import language_to_whisper_language
        from pipecat.transcriptions.language import Language

        self.assertEqual(language_to_whisper_language(Language("pt-BR")), "pt")

    def test_conectar_nao_carrega(self):
        f = Falsos()
        dono = f.dono()
        stt_local.servico_da_linha(self.config, dono)
        self.assertEqual((f.cargas, dono.estado()["estado"]), ([], stt_local.DESCARREGADO))

    def test_sem_modelo_o_trecho_e_ignorado(self):
        import asyncio

        servico = stt_local.servico_da_linha(self.config, Falsos().dono())

        async def rodar():
            return [q async for q in servico.run_stt(bytes(3200))]

        self.assertEqual(asyncio.run(rodar()), [])


if __name__ == "__main__":
    unittest.main()
