"""Mensagens que a janela manda ao motor de voz (`client-message` do RTVI) → o que o motor faz.

O motor não tem LLM, histórico nem persona (ADR-030): ele só fala o texto que a janela recebeu do NewClaw, para quando
pedem e troca de voz quando a pessoa escolhe outra na interface. Esta parte é pura, sem Pipecat, para ser testada sozinha;
o processador do pipeline só executa a ação devolvida.

Protocolo (versão 2):
    {"t": "falar", "d": {"texto": "<resposta do NewClaw>"}}
    {"t": "interromper"}
    {"t": "vozes"}                              → o motor responde a lista de vozes disponíveis e a voz atual
    {"t": "voz", "d": {"voz": "<nome>"}}         → troca a voz, sem reiniciar
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .frases import LIMITE_PADRAO, preparar_para_fala

PROTOCOLO_VERSAO = 2

# Limite de tamanho de um pedido de fala, para uma mensagem maliciosa ou acidental não ocupar o sintetizador por horas.
TEXTO_MAXIMO = 20_000

FALAR = "falar"
INTERROMPER = "interromper"
LISTAR_VOZES = "vozes"
TROCAR_VOZ = "voz"
IGNORAR = "ignorar"


@dataclass(frozen=True)
class Acao:
    tipo: str
    frases: tuple[str, ...] = field(default=())
    voz: str | None = None
    motivo: str | None = None


def interpretar(
    mensagem: object,
    fala_ligada: bool,
    limite: int = LIMITE_PADRAO,
    voz_atual: str | None = None,
    vozes: tuple[str, ...] | None = None,
) -> Acao:
    """`vozes` é a lista do motor (None quando a síntese não é local e a troca não se aplica)."""
    if not isinstance(mensagem, dict):
        return Acao(IGNORAR, motivo="mensagem não é um objeto")
    tipo = mensagem.get("t")
    dados = mensagem.get("d")

    if tipo == INTERROMPER:
        return Acao(INTERROMPER)

    if tipo == LISTAR_VOZES:
        if vozes is None:
            return Acao(IGNORAR, motivo="a troca de voz só existe na síntese local")
        return Acao(LISTAR_VOZES, voz=voz_atual)

    if tipo == TROCAR_VOZ:
        if vozes is None:
            return Acao(IGNORAR, motivo="a troca de voz só existe na síntese local")
        voz = dados.get("voz") if isinstance(dados, dict) else None
        if not isinstance(voz, str) or voz not in vozes:
            return Acao(IGNORAR, motivo=f"voz {voz!r} não está entre as {len(vozes)} disponíveis")
        return Acao(TROCAR_VOZ, voz=voz)

    if tipo == FALAR:
        if not fala_ligada:
            return Acao(IGNORAR, motivo="síntese desligada na configuração")
        if vozes is not None and voz_atual is None:
            return Acao(IGNORAR, motivo="nenhuma voz escolhida ainda: escolha uma na interface")
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
