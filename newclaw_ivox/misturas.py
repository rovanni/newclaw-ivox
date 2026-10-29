"""Vozes misturadas: vozes novas feitas da média ponderada de vozes do Kokoro, declaradas em `vozes-misturadas.json`.

Só biblioteca padrão aqui (ler e validar o arquivo); o cálculo do vetor é feito por quem tem o numpy (`tts_local`).
Uma mistura só vale se todas as vozes que ela usa estiverem no arquivo de vozes instalado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ARQUIVO = "vozes-misturadas.json"
TOLERANCIA_DA_SOMA = 1e-6


@dataclass(frozen=True)
class Mistura:
    nome: str
    rotulo: str
    pesos: tuple[tuple[str, float], ...]


class MisturaInvalida(ValueError):
    pass


def carregar(caminho: Path, vozes_base: list[str] | tuple[str, ...]) -> list[Mistura]:
    """Lê e valida. Arquivo ausente = nenhuma mistura; arquivo com erro = exceção com o motivo (não se ignora em silêncio)."""
    if not caminho.is_file():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MisturaInvalida(f"{caminho.name}: JSON inválido ({e}).") from e
    base = set(vozes_base)
    saida: list[Mistura] = []
    vistos: set[str] = set()
    for i, item in enumerate(dados.get("vozes", []) if isinstance(dados, dict) else []):
        nome = item.get("nome") if isinstance(item, dict) else None
        rotulo = item.get("rotulo") if isinstance(item, dict) else None
        mistura = item.get("mistura") if isinstance(item, dict) else None
        onde = f"{caminho.name}, voz {i + 1}"
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
        saida.append(Mistura(nome, rotulo.strip(), tuple((v, float(p)) for v, p in mistura.items())))
    return saida
