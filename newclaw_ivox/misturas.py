"""Vozes misturadas: vozes novas feitas da média ponderada de vozes do Kokoro, declaradas na pasta `vozes/` (um arquivo por voz).

Só biblioteca padrão aqui (ler e validar o arquivo); o cálculo do vetor é feito por quem tem o numpy (`tts_local`).
Uma mistura só vale se todas as vozes que ela usa estiverem no arquivo de vozes instalado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PASTA = "vozes"
TOLERANCIA_DA_SOMA = 1e-6


@dataclass(frozen=True)
class Mistura:
    nome: str
    rotulo: str
    pesos: tuple[tuple[str, float], ...]


class MisturaInvalida(ValueError):
    pass


def carregar(caminho: Path, vozes_base: list[str] | tuple[str, ...]) -> list[Mistura]:
    """Lê e valida. `caminho` é a pasta `vozes/` (um arquivo .json por voz, em ordem de nome) ou um arquivo só.

    Ausente = nenhuma mistura; arquivo com erro = exceção com o motivo (não se ignora em silêncio).
    Cada arquivo traz uma voz (`{"nome", "rotulo", "mistura"}`) ou várias (`{"vozes": [...]}`).
    """
    if caminho.is_dir():
        arquivos = sorted(f for f in caminho.glob("*.json") if f.is_file())
    elif caminho.is_file():
        arquivos = [caminho]
    else:
        return []
    base = set(vozes_base)
    saida: list[Mistura] = []
    vistos: set[str] = set()
    for arquivo in arquivos:
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise MisturaInvalida(f"{arquivo.name}: JSON inválido ({e}).") from e
        if isinstance(dados, dict) and "vozes" in dados:
            itens = dados["vozes"] if isinstance(dados["vozes"], list) else []
        else:
            itens = [dados]
        for i, item in enumerate(itens):
            onde = f"{arquivo.name}, voz {i + 1}" if len(itens) > 1 else arquivo.name
            saida.append(_validar(item, onde, base, vistos))
    return saida


def _validar(item: object, onde: str, base: set[str], vistos: set[str]) -> Mistura:
    nome = item.get("nome") if isinstance(item, dict) else None
    rotulo = item.get("rotulo") if isinstance(item, dict) else None
    mistura = item.get("mistura") if isinstance(item, dict) else None
    if not isinstance(nome, str) or not nome or any(c.isspace() for c in nome):
        raise MisturaInvalida(f"{onde}: 'nome' precisa ser um texto sem espaços.")
    if nome in base or nome in vistos:
        raise MisturaInvalida(f"{onde}: o nome '{nome}' já existe.")
    if not isinstance(rotulo, str) or not rotulo.strip():
        raise MisturaInvalida(f"{onde}: falta o 'rotulo' que aparece na interface.")
    if not isinstance(mistura, dict) or len(mistura) < 2:
        raise MisturaInvalida(f"{onde}: 'mistura' precisa de pelo menos duas vozes com peso.")
    for voz, peso in mistura.items():
        if voz not in base:
            raise MisturaInvalida(f"{onde}: a voz '{voz}' não está no arquivo de vozes instalado.")
        if not isinstance(peso, (int, float)) or peso <= 0:
            raise MisturaInvalida(f"{onde}: o peso de '{voz}' precisa ser um número maior que zero.")
    soma = sum(mistura.values())
    if abs(soma - 1) > TOLERANCIA_DA_SOMA:
        raise MisturaInvalida(f"{onde}: os pesos somam {soma}, e precisam somar 1.")
    vistos.add(nome)
    return Mistura(nome, rotulo.strip(), tuple((v, float(p)) for v, p in mistura.items()))
