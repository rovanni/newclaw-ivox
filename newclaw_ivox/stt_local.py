"""Transcrição local: o `WhisperSTTService` do Pipecat (faster-whisper), montado só com o que foi configurado e medido.

Nada de padrão da biblioteca escapa para o uso: o Pipecat assume um modelo e o inglês quando não recebe nada, então
modelo, idioma, dispositivo e tipo de cálculo são sempre passados explicitamente. O modelo é carregado da pasta local, já
baixada; aqui nunca se baixa nada. Carregar e descarregar são pedidos da pessoa (`DonoDoModelo`, ADR-037 do NewClaw).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from . import configuracao as cfg
from . import dispositivo as disp
from . import modelos


class SttIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True)
class Transcricao:
    texto: str
    segundos_de_audio: float
    segundos_para_transcrever: float
    dispositivo: str
    tipo: str


# ─── O modelo e o seu dono (ADR-037 do NewClaw) ──────────────────────────────────────────────────────────────────────
# Carregar o modelo é um pedido da pessoa, não efeito de abrir a janela: o Whisper ocupa ~2,2 GB de VRAM e a mesma GPU
# pode estar com outro modelo local. Iniciar a integração, carregar o modelo e abrir a janela são três coisas separadas.
# O dono é um por processo (todas as janelas veem o mesmo estado); cada conexão monta um serviço que só pede o modelo
# emprestado a cada trecho de fala.

DESCARREGADO = "descarregado"
CARREGANDO = "carregando"
CARREGADO = "carregado"
DESCARREGANDO = "descarregando"
FALHA = "falha"

ARQUIVO_CONSUMO = "consumo-medido.json"  # dentro da pasta dos modelos: medida desta máquina, não do repositório


class PedidoRecusado(RuntimeError):
    """O pedido não cabe no estado atual (ex.: descarregar enquanto carrega). A mensagem diz por quê."""


def _chave(modelo: str, dispositivo: str, tipo: str) -> str:
    return f"{modelo}|{dispositivo}|{tipo}"


def _carregar_whisper(pasta: Path, dispositivo: str, tipo: str, idioma: str | None):
    """Carga real: o WhisperModel do faster-whisper, conferido contra o idioma e aquecido (a 1ª transcrição é lenta)."""
    import numpy as np
    from faster_whisper import WhisperModel

    modelo = WhisperModel(str(pasta), device=dispositivo, compute_type=tipo)
    suportados = getattr(modelo, "supported_languages", None)
    if idioma and suportados and idioma not in suportados:
        _descarregar_whisper(modelo)
        raise SttIndisponivel(f"O modelo em {pasta.name} não transcreve '{idioma}'; ele aceita só {sorted(suportados)}.")
    segmentos, _ = modelo.transcribe(np.zeros(16_000, dtype=np.float32), language=idioma)
    list(segmentos)
    return modelo


def _descarregar_whisper(modelo) -> None:
    """Tira os pesos da GPU/RAM pelo próprio CTranslate2; quem guarda a referência a solta depois."""
    interno = getattr(modelo, "model", None)
    if interno is not None and hasattr(interno, "unload_model"):
        interno.unload_model()


class DonoDoModelo:
    """Estados: descarregado → carregando → carregado → descarregando → descarregado; falha guarda o motivo.

    Peças trocáveis para teste: `carregar(pasta, dispositivo, tipo, idioma)`, `descarregar(modelo)`, `medir_motor()`,
    `medir_memoria()` e o relógio.
    """

    def __init__(self, carregar=_carregar_whisper, descarregar=_descarregar_whisper, medir_motor=disp.medir_motor,
                 medir_memoria=disp.medir_memoria_gpu, relogio=time.monotonic):
        self._carregar, self._descarregar = carregar, descarregar
        self._medir_motor, self._medir_memoria, self._relogio = medir_motor, medir_memoria, relogio
        self._cond = threading.Condition()
        self._estado = DESCARREGADO
        self._modelo = None
        self._em_uso = 0
        self._ultimo_uso: float | None = None
        self._info: dict = {}
        self._fio: threading.Thread | None = None

    # ─── leitura ──────────────────────────────────────────────────────────────

    def estado(self) -> dict:
        with self._cond:
            return {"estado": self._estado, "em_uso": self._em_uso, **self._info}

    # ─── carregar ─────────────────────────────────────────────────────────────

    def pedir_carga(self, config: cfg.Configuracao, na_cpu: bool = False, esperar: bool = False) -> dict:
        """Começa a carregar (num fio próprio) e devolve o estado. `na_cpu`: a pessoa confirmou a CPU (D3).

        Sem `na_cpu`, vale o VOZ_DISPOSITIVO configurado (auto, cuda ou cpu). Na GPU, se a memória livre medida for menor
        que o consumo medido da última carga, não carrega: devolve a pergunta "tentar na CPU ou cancelar".
        """
        with self._cond:
            if self._estado in (CARREGANDO, CARREGADO):
                return self.estado()
            if self._estado == DESCARREGANDO:
                raise PedidoRecusado("o modelo está sendo descarregado; peça de novo quando terminar")
        if config.stt is None or config.stt.motor != cfg.LOCAL:
            raise SttIndisponivel("Transcrição local não configurada (VOZ_STT_MOTOR=local e VOZ_STT_MODELO).")
        nome = config.stt.modelo
        if not modelos.instalado(config.modelos_dir, nome):
            raise SttIndisponivel(
                f"Modelo '{nome}' não está em {modelos.pasta_do_modelo(config.modelos_dir, nome)}. Rode o instalador para baixá-lo."
            )
        escolha = disp.escolher("cpu" if na_cpu else config.dispositivo, self._medir_motor())
        base = {"modelo": nome, "dispositivo": escolha.dispositivo, "tipo": escolha.tipo, "motivo": escolha.motivo}
        if escolha.dispositivo is None:
            with self._cond:
                self._estado, self._info = FALHA, {**base, "erro": escolha.motivo}
            return self.estado()

        memoria = self._medir_memoria() if escolha.dispositivo == "cuda" else None
        necessario = ler_consumo(config.modelos_dir).get(_chave(nome, escolha.dispositivo, escolha.tipo))
        base["memoria_antes"] = _memoria_para_json(memoria)
        base["consumo_medido_bytes"] = necessario
        # Só compara com uma GPU: com várias, a ordem da NVML pode não ser a do CUDA, e não dá para saber qual vai ser usada.
        if memoria and len(memoria) == 1 and necessario and memoria[0].livre_bytes < necessario:
            with self._cond:
                self._estado = DESCARREGADO
                self._info = {**base, "pergunta": "cpu", "aviso": (
                    f"A GPU tem {memoria[0].livre_bytes / 2**30:.1f} GB livres e este modelo ocupou "
                    f"{necessario / 2**30:.1f} GB na última carga.")}
            return self.estado()

        with self._cond:
            if self._estado in (CARREGANDO, CARREGADO):  # outra janela pediu enquanto este media
                return self.estado()
            self._estado, self._info = CARREGANDO, {**base, "inicio": time.time()}
            pasta = modelos.pasta_do_modelo(config.modelos_dir, nome)
            self._fio = threading.Thread(
                target=self._carregar_no_fio, args=(config, pasta, escolha, memoria, base), daemon=True)
            self._fio.start()
            fio = self._fio
        if esperar:
            fio.join()
        return self.estado()

    def _carregar_no_fio(self, config, pasta, escolha, memoria_antes, base) -> None:
        inicio = time.perf_counter()
        try:
            modelo = self._carregar(pasta, escolha.dispositivo, escolha.tipo, config.idioma)
        except Exception as e:  # noqa: BLE001 — qualquer falha da biblioteca vira estado, sem derrubar a integração
            info = {**base, "erro": f"{type(e).__name__}: {e}"}
            if escolha.dispositivo == "cuda":
                info["pergunta"] = "cpu"  # toda falha na GPU oferece a CPU; o motivo não é adivinhado pelo texto
            with self._cond:
                self._estado, self._info = FALHA, info
            print(f"[motor] Whisper não carregou ({escolha.dispositivo}/{escolha.tipo}): {info['erro']}", flush=True)
            return
        info = {**base, "segundos_para_carregar": round(time.perf_counter() - inicio, 1)}
        if escolha.dispositivo == "cuda":
            depois = self._medir_memoria()
            info["memoria_depois"] = _memoria_para_json(depois)
            if memoria_antes and depois and len(memoria_antes) == len(depois) == 1:
                consumo = depois[0].usada_bytes - memoria_antes[0].usada_bytes
                # Diferença do dispositivo inteiro: outro programa alocando ao mesmo tempo entra na conta.
                info["consumo_bytes"] = consumo
                info["consumo_fonte"] = "diferença da memória usada na GPU antes e depois da carga"
                if consumo > 0:
                    gravar_consumo(config.modelos_dir, _chave(base["modelo"], escolha.dispositivo, escolha.tipo), consumo)
        with self._cond:
            self._modelo, self._estado, self._info = modelo, CARREGADO, info
            self._ultimo_uso = self._relogio()
        print(f"[motor] Whisper carregado em {info['segundos_para_carregar']} s ({base['motivo']})", flush=True)

    # ─── usar ─────────────────────────────────────────────────────────────────

    def tomar(self):
        """Empresta o modelo para um trecho; None se não estiver carregado. Quem toma, devolve (`devolver`)."""
        with self._cond:
            if self._estado != CARREGADO:
                return None
            self._em_uso += 1
            return self._modelo

    def devolver(self) -> None:
        with self._cond:
            self._em_uso -= 1
            self._ultimo_uso = self._relogio()
            self._cond.notify_all()

    # ─── descarregar ──────────────────────────────────────────────────────────

    def descarregar(self) -> dict:
        """Espera a transcrição em andamento terminar e tira o modelo da memória. Bloqueia: chamar fora do laço asyncio."""
        with self._cond:
            if self._estado == CARREGANDO:
                raise PedidoRecusado("o modelo ainda está carregando; descarregue quando a carga terminar")
            if self._estado in (DESCARREGADO, FALHA):
                self._estado, self._info = DESCARREGADO, {}
                return self.estado()
            if self._estado == DESCARREGANDO:
                return self.estado()
            self._estado = DESCARREGANDO
            while self._em_uso > 0:
                self._cond.wait()
            modelo, self._modelo = self._modelo, None
            dispositivo = self._info.get("dispositivo")
        antes = self._medir_memoria() if dispositivo == "cuda" else None
        try:
            self._descarregar(modelo)
        finally:
            del modelo
            import gc

            gc.collect()
        info: dict = {}
        if dispositivo == "cuda":
            depois = self._medir_memoria()
            info["memoria_depois"] = _memoria_para_json(depois)
            if antes and depois and len(antes) == len(depois) == 1:
                info["liberado_bytes"] = antes[0].usada_bytes - depois[0].usada_bytes
        with self._cond:
            self._estado, self._info = DESCARREGADO, info
        print(f"[motor] Whisper descarregado; liberado: {info.get('liberado_bytes', 'não medido')}", flush=True)
        return self.estado()

    def descarregar_se_ocioso(self, minutos: float | None) -> bool:
        """D2 (opcional, desligado por padrão): descarrega se ninguém transcreveu nada há `minutos`."""
        if not minutos:
            return False
        with self._cond:
            ocioso = (self._estado == CARREGADO and self._em_uso == 0 and self._ultimo_uso is not None
                      and self._relogio() - self._ultimo_uso >= minutos * 60)
        if ocioso:
            self.descarregar()
        return ocioso


def _memoria_para_json(memoria) -> list[dict] | None:
    if memoria is None:
        return None
    return [{"nome": g.nome, "total_bytes": g.total_bytes, "usada_bytes": g.usada_bytes, "livre_bytes": g.livre_bytes}
            for g in memoria]


def ler_consumo(modelos_dir: Path) -> dict[str, int]:
    try:
        return json.loads((modelos_dir / ARQUIVO_CONSUMO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar_consumo(modelos_dir: Path, chave: str, consumo: int) -> None:
    dados = ler_consumo(modelos_dir)
    dados[chave] = consumo
    try:
        modelos_dir.mkdir(parents=True, exist_ok=True)
        (modelos_dir / ARQUIVO_CONSUMO).write_text(json.dumps(dados, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"[motor] consumo medido não gravado em {modelos_dir / ARQUIVO_CONSUMO}: {e}", flush=True)


_DONO: DonoDoModelo | None = None


def dono() -> DonoDoModelo:
    """O dono do modelo deste processo."""
    global _DONO
    if _DONO is None:
        _DONO = DonoDoModelo()
    return _DONO


# ─── O serviço da linha (um por conexão) ─────────────────────────────────────────────────────────────────────────────

_CLASSE = None


def _classe_da_linha():
    global _CLASSE
    if _CLASSE is None:
        from pipecat.frames.frames import ErrorFrame
        from pipecat.services.whisper.stt import WhisperSTTService

        class WhisperDoDono(WhisperSTTService):
            """O `WhisperSTTService` do Pipecat carrega o modelo no construtor; este não carrega nada: a cada trecho de fala
            pede o modelo emprestado ao dono. Sem modelo carregado, o trecho é ignorado (a janela mostra o motivo)."""

            def __init__(self, *args, dono_do_modelo: DonoDoModelo, **kwargs):
                self._dono = dono_do_modelo
                super().__init__(*args, **kwargs)

            def _load(self):
                return

            async def run_stt(self, audio: bytes):
                modelo = self._dono.tomar()
                if modelo is None:
                    return
                try:
                    self._model = modelo
                    async for quadro in super().run_stt(audio):
                        yield quadro
                except Exception as e:  # noqa: BLE001
                    yield ErrorFrame(f"transcrição falhou: {e}")
                finally:
                    self._model = None
                    self._dono.devolver()

        _CLASSE = WhisperDoDono
    return _CLASSE


def servico_da_linha(config: cfg.Configuracao, dono_do_modelo: DonoDoModelo | None = None):
    """O serviço de transcrição de uma conexão. Não carrega o modelo (ADR-037): só confere a configuração."""
    if config.stt is None or config.stt.motor != cfg.LOCAL:
        raise SttIndisponivel("Transcrição local não configurada (VOZ_STT_MOTOR=local e VOZ_STT_MODELO).")
    from pipecat.transcriptions.language import Language

    cls = _classe_da_linha()
    return cls(
        # Dispositivo e tipo do serviço não são usados (o dono carrega); o Pipecat só exige que existam.
        device=config.dispositivo, compute_type="default", dono_do_modelo=dono_do_modelo or dono(),
        settings=cls.Settings(
            model=str(modelos.pasta_do_modelo(config.modelos_dir, config.stt.modelo)),
            language=Language(config.idioma) if config.idioma else None,
        ),
    )


def criar_servico(config: cfg.Configuracao):
    """Para os comandos de teste (fora da janela): carrega já, espera e devolve o serviço com a escolha medida."""
    estado = dono().pedir_carga(config, esperar=True)
    if estado["estado"] != CARREGADO:
        raise SttIndisponivel(estado.get("erro") or estado.get("aviso") or f"modelo {estado['estado']}")
    escolha = disp.Escolha(estado["dispositivo"], estado["tipo"], estado["motivo"])
    return servico_da_linha(config), escolha


def ler_wav_pcm16(caminho: Path) -> tuple[bytes, int]:
    """Lê um WAV mono de 16 bits; devolve (amostras, taxa)."""
    with wave.open(str(caminho), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise ValueError(f"{caminho}: esperado WAV mono de 16 bits (veio {w.getnchannels()} canal(is), {8 * w.getsampwidth()} bits).")
        return w.readframes(w.getnframes()), w.getframerate()


def transcrever(servico, escolha: disp.Escolha, audio_pcm16: bytes, taxa: int) -> Transcricao:
    """Versão para fora de um laço asyncio (comandos de teste)."""
    return asyncio.run(transcrever_async(servico, escolha, audio_pcm16, taxa))


async def transcrever_async(servico, escolha: disp.Escolha, audio_pcm16: bytes, taxa: int) -> Transcricao:
    """Transcreve um trecho inteiro pelo mesmo `run_stt` que o pipeline usa. O Whisper espera 16 kHz."""
    if taxa != 16_000:
        raise ValueError(f"O Whisper espera áudio a 16 kHz; veio {taxa} Hz.")
    from pipecat.frames.frames import ErrorFrame, TranscriptionFrame

    inicio = time.perf_counter()
    textos, erros = [], []
    async for quadro in servico.run_stt(audio_pcm16):
        if isinstance(quadro, TranscriptionFrame):
            textos.append(quadro.text)
        elif isinstance(quadro, ErrorFrame):
            erros.append(quadro.error)
    duracao = time.perf_counter() - inicio
    if erros:
        raise SttIndisponivel("; ".join(erros))
    return Transcricao(
        texto=" ".join(t.strip() for t in textos).strip(),
        segundos_de_audio=len(audio_pcm16) / 2 / taxa,
        segundos_para_transcrever=duracao,
        dispositivo=escolha.dispositivo,
        tipo=escolha.tipo,
    )
