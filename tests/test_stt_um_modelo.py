"""Um modelo do Whisper por computador, mesmo com várias janelas conectando juntas (31/10/2026).

Depois de religar o computador, o navegador reabriu três abas da janela ao mesmo tempo; cada conexão achou o cache vazio
e carregou a sua cópia: ~5,7 GB de VRAM. A carga agora é feita sob uma trava: a 2ª conexão espera a 1ª e reaproveita.
"""

import importlib.util
import threading
import time
import types
import unittest

TEM_PIPECAT = importlib.util.find_spec("pipecat") is not None


@unittest.skipUnless(TEM_PIPECAT, "Pipecat não instalado neste Python")
class TestUmModeloSo(unittest.TestCase):
    def test_conexoes_simultaneas_carregam_uma_copia(self):
        from pipecat.services.whisper.stt import WhisperSTTService

        from newclaw_ivox import stt_local

        cargas = []

        def carga_lenta(self):
            time.sleep(0.3)  # a carga real leva ~9 s; o que importa é ela demorar enquanto outras chegam
            self._model = object()
            cargas.append(self._model)

        original = WhisperSTTService._load
        WhisperSTTService._load = carga_lenta
        stt_local._MODELOS_CARREGADOS.clear()
        try:
            cls = stt_local._classe_com_cache()
            servicos = []
            for _ in range(3):
                s = cls.__new__(cls)
                s._settings = types.SimpleNamespace(model="m")
                s._device, s._compute_type = "cuda", "float16"
                s._unsupported_language = lambda: None
                servicos.append(s)
            fios = [threading.Thread(target=s._load) for s in servicos]
            for f in fios:
                f.start()
            for f in fios:
                f.join()
        finally:
            WhisperSTTService._load = original
            stt_local._MODELOS_CARREGADOS.clear()

        self.assertEqual(len(cargas), 1, "três conexões juntas devem carregar uma cópia só")
        self.assertTrue(all(s._model is cargas[0] for s in servicos), "todas usam o mesmo modelo")


if __name__ == "__main__":
    unittest.main()
