"""Comandos que precisam do motor (Pipecat/faster-whisper): rodam com o Python do `.venv`."""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import configuracao as cfg

RAIZ = Path(__file__).resolve().parent.parent


def _valor(argumentos: list[str], nome: str) -> str | None:
    if nome in argumentos:
        i = argumentos.index(nome)
        if i + 1 < len(argumentos):
            return argumentos[i + 1]
    return None


def modelos(argumentos: list[str]) -> int:
    """`modelos [--json] [--pasta P] [--baixar NOME]`"""
    from . import modelos as m

    pasta = Path(_valor(argumentos, "--pasta") or cfg.carregar(None, RAIZ / ".env", RAIZ).modelos_dir)
    nome = _valor(argumentos, "--baixar")
    if nome:
        if nome not in m.repositorios():
            print(f"Modelo '{nome}' não existe nesta versão do faster-whisper.")
            return 1
        print(f"Baixando '{nome}' para {m.pasta_do_modelo(pasta, nome)} …")
        inicio = time.perf_counter()
        destino = m.baixar(pasta, nome)
        print(f"Pronto em {time.perf_counter() - inicio:.0f} s: {destino}")
        return 0
    lista = [
        {
            "nome": x.nome, "repositorio": x.repositorio, "bytes": x.bytes_, "tamanho": m.formatar_bytes(x.bytes_),
            "instalado": m.instalado(pasta, x.nome), "pasta": str(m.pasta_do_modelo(pasta, x.nome)),
        }
        for x in m.listar()
    ]
    if "--json" in argumentos:
        print(json.dumps(lista, ensure_ascii=False))
    else:
        for x in lista:
            print(f"{x['nome']:<20} {x['tamanho']:>12}  {'baixado' if x['instalado'] else ''}")
    return 0


def testar_stt(argumentos: list[str]) -> int:
    """`testar-stt [--audio arquivo.wav]` — carrega o modelo no dispositivo medido e transcreve duas vezes.

    A primeira rodada aquece o dispositivo (na GPU, a primeira de cada processo é bem mais lenta); a segunda é o tempo de
    uso. Sem `--audio`, usa 5 s de silêncio só para provar que o modelo roda e medir o tempo: o Whisper costuma inventar
    texto em silêncio, e no uso real isso não acontece porque o detector de voz só manda trechos com fala.
    """
    from . import stt_local

    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    try:
        inicio = time.perf_counter()
        servico, escolha = stt_local.criar_servico(config)
        carga = time.perf_counter() - inicio
    except stt_local.SttIndisponivel as e:
        print(f"Transcrição local indisponível: {e}")
        return 1
    print(f"Modelo '{config.stt.modelo}' carregado em {carga:.1f} s — {escolha.motivo}")

    arquivo = _valor(argumentos, "--audio")
    if arquivo:
        audio, taxa = stt_local.ler_wav_pcm16(Path(arquivo))
    else:
        audio, taxa = bytes(5 * 16_000 * 2), 16_000
    aquecimento = stt_local.transcrever(servico, escolha, audio, taxa)
    uso = stt_local.transcrever(servico, escolha, audio, taxa)
    fator = uso.segundos_de_audio / uso.segundos_para_transcrever if uso.segundos_para_transcrever else float("inf")
    print(f"Aquecimento: {aquecimento.segundos_para_transcrever:.2f} s.")
    print(
        f"Uso: {uso.segundos_de_audio:.1f} s de áudio em {uso.segundos_para_transcrever:.2f} s "
        f"({uso.dispositivo}/{uso.tipo}) — {fator:.1f}x {'mais rápido' if fator >= 1 else 'da velocidade'} que a fala."
    )
    if fator < 1:
        print("Mais lento que a fala: a resposta vai atrasar. Um modelo menor, ou uma GPU, deixa a transcrição mais rápida.")
    if arquivo:
        print(f"Texto: {uso.texto!r}")
    return 0
