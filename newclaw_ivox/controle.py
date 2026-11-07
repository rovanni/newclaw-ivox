"""Mensagens que a janela manda ao motor de voz (`client-message` do RTVI) → o que o motor faz.

O motor não tem LLM, histórico nem persona (ADR-030): ele só fala o texto que a janela recebeu do NewClaw, para quando
pedem e troca de voz quando a pessoa escolhe outra na interface. Esta parte é pura, sem Pipecat, para ser testada sozinha;
o processador do pipeline só executa a ação devolvida.

Protocolo (versão 4):
    {"t": "falar", "d": {"texto": "<resposta do NewClaw>"}}
    {"t": "interromper"}
    {"t": "vozes"}                              → o motor responde a lista de vozes disponíveis e a voz atual
    {"t": "voz", "d": {"voz": "<nome>"}}         → troca a voz, sem reiniciar
    {"t": "velocidade", "d": {"velocidade": 1.2}} → velocidade da fala (multiplicador aceito pelo Kokoro: 0,5 a 2,0)
    {"t": "vocabulario", "d": {"palavras": ["River", "Cornélio Procópio"]}}
        → as palavras do dicionário da voz (ADR-039 do NewClaw), na ordem em que valem; o motor responde quantas cabem
          no Whisper. A fonte da lista é o NewClaw, pela janela: o motor não fala com o NewClaw.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .frases import LIMITE_PADRAO, preparar_para_fala

PROTOCOLO_VERSAO = 4

# Limite de tamanho de um pedido de fala, para uma mensagem maliciosa ou acidental não ocupar o sintetizador por horas.
TEXTO_MAXIMO = 20_000

FALAR = "falar"
INTERROMPER = "interromper"
LISTAR_VOZES = "vozes"
TROCAR_VOZ = "voz"
VELOCIDADE = "velocidade"
VOCABULARIO = "vocabulario"
# Os mesmos tetos de proteção da rota do NewClaw (`src/dashboard/routes/voz.ts`): protegem o motor de uma mensagem gigante.
# Não são o tamanho bom da lista: quantas cabem no Whisper é medido com o tokenizador do modelo (`stt_local`).
VOCABULARIO_MAXIMO = 200
PALAVRA_MAXIMA = 60
# Faixa do multiplicador de velocidade que o serviço Kokoro do Pipecat documenta (`KokoroTTSSettings.speed`).
VELOCIDADE_MINIMA = 0.5
VELOCIDADE_MAXIMA = 2.0
IGNORAR = "ignorar"


@dataclass(frozen=True)
class Acao:
    tipo: str
    frases: tuple[str, ...] = field(default=())
    voz: str | None = None
    velocidade: float | None = None
    palavras: tuple[str, ...] = field(default=())
    motivo: str | None = None


def interpretar(
    mensagem: object,
    fala_ligada: bool,
    limite: int = LIMITE_PADRAO,
    voz_atual: str | None = None,
    vozes: tuple[str, ...] | None = None,
    ouvir_ligado: bool = False,
) -> Acao:
    """`vozes` é a lista do motor (None quando a síntese não é local e a troca não se aplica); `ouvir_ligado`: há
    reconhecimento local na linha (o vocabulário só vale para ele)."""
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

    if tipo == VELOCIDADE:
        if vozes is None:
            return Acao(IGNORAR, motivo="a velocidade da fala só existe na síntese local")
        v = dados.get("velocidade") if isinstance(dados, dict) else None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not VELOCIDADE_MINIMA <= v <= VELOCIDADE_MAXIMA:
            return Acao(IGNORAR, motivo=f"velocidade {v!r} fora de {VELOCIDADE_MINIMA}–{VELOCIDADE_MAXIMA}")
        return Acao(VELOCIDADE, velocidade=float(v))

    if tipo == VOCABULARIO:
        if not ouvir_ligado:
            return Acao(IGNORAR, motivo="o reconhecimento local não está ligado neste motor")
        lista = dados.get("palavras") if isinstance(dados, dict) else None
        if not isinstance(lista, list) or any(not isinstance(p, str) for p in lista):
            return Acao(IGNORAR, motivo="vocabulario sem a lista de palavras")
        if len(lista) > VOCABULARIO_MAXIMO:
            return Acao(IGNORAR, motivo=f"vocabulario com mais de {VOCABULARIO_MAXIMO} palavras")
        palavras = tuple(" ".join(p.split()) for p in lista if p.strip())
        if any(len(p) > PALAVRA_MAXIMA for p in palavras):
            return Acao(IGNORAR, motivo=f"palavra com mais de {PALAVRA_MAXIMA} caracteres")
        return Acao(VOCABULARIO, palavras=palavras)

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
