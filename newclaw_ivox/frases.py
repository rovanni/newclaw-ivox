"""Texto da resposta → pedaços para a síntese, um de cada vez (ADR-030, H2 e D4).

Tudo aqui é forma do texto, nunca significado: a divisão segue pontuação e quebras de linha, e a limpeza tira só os sinais
de marcação que o sintetizador leria em voz alta. O texto completo continua na tela e no histórico do NewClaw.
"""

from __future__ import annotations

import re

# Pedaço máximo enviado de uma vez à síntese. Medido na Etapa 0 (Kokoro, resposta inteira de uma vez): 71 caracteres
# levaram 0,97 s e 234 levaram 3,39 s; o Pipecat avisa "contexto sem áudio" aos ~3 s. 160 fica abaixo disso com folga.
LIMITE_PADRAO = 160

_BLOCO_DE_CODIGO = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_IMAGEM = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CODIGO_EM_LINHA = re.compile(r"`([^`]*)`")
_NEGRITO = re.compile(r"(\*\*|__)(.+?)\1")
_ITALICO = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_TACHADO = re.compile(r"~~(.+?)~~")
_TITULO = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_CITACAO = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_MARCADOR_DE_LISTA = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+", re.MULTILINE)
_SEPARADOR_DE_TABELA = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$", re.MULTILINE)
_LINHA_HORIZONTAL = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE)

# Fim de frase: pontuação final seguida de espaço. "3.5" e "www.x.com" não se partem porque não têm espaço depois.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")
# Onde partir uma frase longa demais, em ordem de preferência.
_PAUSAS = (re.compile(r"[;:]\s"), re.compile(r",\s"), re.compile(r"\s"))


def limpar_marcacao(texto: str) -> str:
    """Tira a marcação Markdown que viraria ruído falado. Blocos de código não são falados (ficam na tela)."""
    texto = _BLOCO_DE_CODIGO.sub("\n", texto)
    texto = _IMAGEM.sub(r"\1", texto)
    texto = _LINK.sub(r"\1", texto)
    texto = _CODIGO_EM_LINHA.sub(r"\1", texto)
    texto = _NEGRITO.sub(r"\2", texto)
    texto = _TACHADO.sub(r"\1", texto)
    texto = _ITALICO.sub(r"\1", texto)
    texto = _SEPARADOR_DE_TABELA.sub("", texto)
    texto = _LINHA_HORIZONTAL.sub("", texto)
    texto = _TITULO.sub("", texto)
    texto = _CITACAO.sub("", texto)
    texto = _MARCADOR_DE_LISTA.sub("", texto)
    linhas = []
    for linha in texto.splitlines():
        if "|" in linha:
            celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
            linha = ", ".join(c for c in celulas if c)
        linhas.append(linha.strip())
    return "\n".join(linhas)


def dividir_em_frases(texto: str, limite: int = LIMITE_PADRAO) -> list[str]:
    """Divide o texto já limpo em frases; frase maior que o limite é partida na pausa mais próxima antes dele."""
    if limite < 20:
        raise ValueError("limite pequeno demais para frases faladas")
    frases: list[str] = []
    for paragrafo in re.split(r"\n+", texto):
        for frase in _FIM_DE_FRASE.split(paragrafo.strip()):
            frase = re.sub(r"\s+", " ", frase).strip()
            if not _tem_conteudo(frase):
                continue
            frases.extend(_partir(frase, limite))
    return frases


def preparar_para_fala(texto: str, limite: int = LIMITE_PADRAO) -> list[str]:
    return dividir_em_frases(limpar_marcacao(texto), limite)


def _tem_conteudo(frase: str) -> bool:
    return any(c.isalnum() for c in frase)


def _partir(frase: str, limite: int) -> list[str]:
    pedacos: list[str] = []
    while len(frase) > limite:
        corte = _ponto_de_corte(frase, limite)
        pedaco, frase = frase[:corte].strip(), frase[corte:].strip()
        if _tem_conteudo(pedaco):
            pedacos.append(pedaco)
    if _tem_conteudo(frase):
        pedacos.append(frase)
    return pedacos


def _ponto_de_corte(frase: str, limite: int) -> int:
    janela = frase[: limite + 1]
    minimo = limite // 3  # não deixa sobrar um pedaço minúsculo no começo
    for pausa in _PAUSAS:
        cortes = [m.end() for m in pausa.finditer(janela) if m.end() > minimo]
        if cortes:
            return cortes[-1]
    return limite  # palavra sem espaço maior que o limite: corta seco
