import unittest

from newclaw_ivox import dispositivo as d

COM_GPU = d.Motor(gpus_cuda=1, tipos={"cpu": ("float32", "int8"), "cuda": ("float16", "float32", "int8")})
SEM_GPU = d.Motor(gpus_cuda=0, tipos={"cpu": ("float32", "int8"), "cuda": ()})


class TestEscolha(unittest.TestCase):
    def test_auto_com_gpu(self):
        e = d.escolher("auto", COM_GPU)
        self.assertEqual((e.dispositivo, e.tipo), ("cuda", "float16"))
        self.assertIn("GPU CUDA encontrada", e.motivo)

    def test_auto_sem_gpu(self):
        e = d.escolher("auto", SEM_GPU)
        self.assertEqual((e.dispositivo, e.tipo), ("cpu", "int8"))
        self.assertIn("nenhuma GPU", e.motivo)

    def test_cuda_pedido_sem_gpu_e_erro_claro(self):
        e = d.escolher("cuda", SEM_GPU)
        self.assertIsNone(e.dispositivo)
        self.assertIn("não encontrou GPU", e.motivo)

    def test_cpu_pedido_com_gpu(self):
        self.assertEqual(d.escolher("cpu", COM_GPU).dispositivo, "cpu")

    def test_so_escolhe_tipo_medido(self):
        motor = d.Motor(gpus_cuda=1, tipos={"cuda": ("int8_float16",), "cpu": ()})
        self.assertEqual(d.escolher("auto", motor).tipo, "int8_float16")
        self.assertIsNone(d.escolher("cpu", motor).dispositivo)


class TestMedicaoDoSistema(unittest.TestCase):
    def test_medicao_basica(self):
        s = d.medir_sistema()
        self.assertTrue(s.sistema)
        self.assertTrue(s.python)
        self.assertIsInstance(s.gpus_nvidia, tuple)



class TestMemoriaDaGpu(unittest.TestCase):
    def test_sem_driver_nvidia_e_nao_medido(self):
        original = d._abrir_nvml
        d._abrir_nvml = lambda: None
        try:
            self.assertIsNone(d.medir_memoria_gpu(), "sem NVML: ausência, nunca um número inventado")
        finally:
            d._abrir_nvml = original

    def test_medida_quando_ha_driver(self):
        medida = d.medir_memoria_gpu()
        if medida is None:
            self.skipTest("esta máquina não tem driver NVIDIA")
        for g in medida:
            self.assertEqual(g.usada_bytes + g.livre_bytes, g.total_bytes, g)


if __name__ == "__main__":
    unittest.main()
