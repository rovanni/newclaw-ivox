"""Mensagens que a janela manda ao motor de voz (`client-message` do RTVI) → o que o motor faz.

O motor não tem LLM, histórico nem persona (ADR-030): ele só fala o texto que a janela recebeu do NewClaw e para quando
pedem. Esta parte é pura, sem Pipecat, para ser testada sozinha; o processador do pipeline só executa a ação devolvida.

Protocolo (versão 1):
    {"t": "falar", "d": {"texto": "<resposta do NewClaw>"}}
    {"t": "interromper"}
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .frases import LIMITE_PADRAO, preparar_para_fala

PROTOCOLO_VERSAO = 1

# Limite de tamanho de um pedido de fala, para uma mensagem maliciosa ou acidental não ocupar o sintetizador por horas.
TEXTO_MAXIMO = 20_000

FALAR = "falar"
INTERROMPER = "interromper"
IGNORAR = "ignorar"


@dataclass(frozen=True)
class Acao:
    tipo: str
    frases: tuple[str, ...] = field(default=())
    motivo: str | None = None


def interpretar(mensagem: object, fala_ligada: bool, limite: int = LIMITE_PADRAO) -> Acao:
    if not isinstance(mensagem, dict):
        return Acao(IGNORAR, motivo="mensagem não é um objeto")
    tipo = mensagem.get("t")

    if tipo == INTERROMPER:
        return Acao(INTERROMPER)

    if tipo == FALAR:
        if not fala_ligada:
            return Acao(IGNORAR, motivo="síntese desligada na configuração")
        dados = mensagem.get("d")
        texto = dados.get("texto") if isinstance(dados, dict) else None
        if not isinstance(texto, str) or not texto.strip():
            return Acao(IGNORAR, motivo="falar sem texto")
        if len(texto) > TEXTO_MAXIMO:
            return Acao(IGNORAR, motivo=f"texto com mais de {TEXTO_MAXIMO} caracteres")
        frases = tuple(preparar_para_fala(texto, limite))
        if not frases:
            return Acao(IGNORAR, motivo="nada falável depois da limpeza (só código ou marcação)")
        return Acao(FALAR, frases=frases)

    return Acao(IGNORAR, motivo=f"tipo desconhecido: {tipo!r}")
