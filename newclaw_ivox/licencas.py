"""Aceite das licenças de terceiros, antes de instalar qualquer coisa (pedido da operadora, 30/10/2026).

A lista vive em `docs/terceiros/aceite.json` (dados, conferidos na fonte de cada peça); aqui só se escolhe o que vale para a
instalação pedida e se guarda o aceite. O aceite é da própria pessoa, digitado no instalador: nada aqui aceita por ela.

O registro fica em `.licencas-aceitas.json` na pasta do projeto (fora do git): a versão da lista, a data e as peças aceitas.
Lista nova (versão maior) ou peça nova na instalação → pergunta de novo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ARQUIVO_DA_LISTA = Path("docs") / "terceiros" / "aceite.json"
ARQUIVO_DO_REGISTRO = ".licencas-aceitas.json"
PALAVRA_DE_ACEITE = "aceito"

# Quando cada grupo entra: "sempre" (motor e janela) e os opcionais que a pessoa escolheu no instalador.
SEMPRE = "sempre"
STT_LOCAL = "stt-local"
TTS_LOCAL = "tts-local"
CUDA = "cuda"


@dataclass(frozen=True)
class Item:
    id: str
    nome: str
    papel: str
    licenca: str
    link: str
    quando: str
    atencao: str | None = None


@dataclass(frozen=True)
class Lista:
    versao: int
    itens: tuple[Item, ...]


def carregar_lista(raiz: Path) -> Lista:
    dados = json.loads((raiz / ARQUIVO_DA_LISTA).read_text(encoding="utf-8"))
    campos = Item.__dataclass_fields__
    itens = tuple(Item(**{k: v for k, v in i.items() if k in campos}) for i in dados["itens"])
    return Lista(versao=int(dados["versao"]), itens=itens)


def itens_para(lista: Lista, grupos: set[str]) -> tuple[Item, ...]:
    """As peças desta instalação: as de sempre mais as dos grupos escolhidos."""
    return tuple(i for i in lista.itens if i.quando == SEMPRE or i.quando in grupos)


def ler_registro(raiz: Path) -> dict | None:
    caminho = raiz / ARQUIVO_DO_REGISTRO
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ja_aceitas(registro: dict | None, lista: Lista, itens: tuple[Item, ...]) -> bool:
    """Já aceitas quando o registro é desta versão da lista e cobre todas as peças desta instalação."""
    if not registro or registro.get("versao_da_lista") != lista.versao:
        return False
    return {i.id for i in itens} <= set(registro.get("itens", []))


def gravar_registro(raiz: Path, lista: Lista, itens: tuple[Item, ...], agora: datetime | None = None) -> Path:
    momento = (agora or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    anterior = ler_registro(raiz) or {}
    # Peças já aceitas nesta mesma versão continuam valendo (outra instalação pode ter pedido menos coisas).
    ids = set(anterior.get("itens", [])) if anterior.get("versao_da_lista") == lista.versao else set()
    ids |= {i.id for i in itens}
    caminho = raiz / ARQUIVO_DO_REGISTRO
    caminho.write_text(json.dumps({
        "versao_da_lista": lista.versao,
        "aceito_em": momento,
        "itens": sorted(ids),
        "licencas": {i.id: i.licenca for i in lista.itens if i.id in ids},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return caminho


def resposta_aceita(resposta: str) -> bool:
    return resposta.strip().lower() == PALAVRA_DE_ACEITE
