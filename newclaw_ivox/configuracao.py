"""Configuração do motor de voz, lida só do ambiente (e de um `.env` opcional).

Regra (ADR-030, tabela 4): nenhum valor de laboratório e nenhum valor adivinhado. Variável vazia significa recurso
desligado, e o desligamento é reportado. Modelo, voz e idioma nunca têm padrão no código: sem escolha do usuário, a
ausência aparece no diagnóstico.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

# Idiomas que o `Language` do Pipecat aceita e que o NewClaw usa (ADR-030, tabela 4).
IDIOMAS_ACEITOS = ("pt-BR", "en-US", "es-ES")

# A porta é o único valor com padrão: é endereço local, não escolha de recurso. O motor escuta só em 127.0.0.1.
PORTA_PADRAO = 7860

PREFIXOS_ICE = ("stun:", "turn:", "turns:")

ERRO = "erro"
AVISO = "aviso"
INFO = "info"


@dataclass(frozen=True)
class Achado:
    nivel: str
    variavel: str
    mensagem: str


@dataclass(frozen=True)
class Servico:
    """Um serviço compatível com a API OpenAI (transcrição ou síntese)."""

    url: str
    modelo: str
    chave: str | None
    voz: str | None = None


@dataclass(frozen=True)
class Configuracao:
    stt: Servico | None
    tts: Servico | None
    idioma: str | None
    ice_servidores: tuple[str, ...]
    porta: int
    achados: tuple[Achado, ...] = field(default=())

    @property
    def tem_erro(self) -> bool:
        return any(a.nivel == ERRO for a in self.achados)

    @property
    def nada_configurado(self) -> bool:
        return self.stt is None and self.tts is None and not self.tem_erro


def ler_arquivo_env(caminho: Path) -> dict[str, str]:
    """Lê `CHAVE=valor` por linha; ignora comentários e linhas vazias; tira aspas simples ou duplas do valor."""
    valores: dict[str, str] = {}
    if not caminho.is_file():
        return valores
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, valor = linha.split("=", 1)
        nome = nome.strip()
        if nome.startswith("export "):
            nome = nome[len("export "):].strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[nome] = valor
    return valores


def carregar(ambiente: Mapping[str, str] | None = None, arquivo_env: Path | None = None) -> Configuracao:
    """Monta a configuração. O ambiente do processo vence o `.env`, como de costume."""
    origem: dict[str, str] = {}
    if arquivo_env is not None:
        origem.update(ler_arquivo_env(arquivo_env))
    origem.update(os.environ if ambiente is None else ambiente)

    def valor(nome: str) -> str | None:
        bruto = origem.get(nome, "").strip()
        return bruto or None

    achados: list[Achado] = []

    stt = _servico(
        "VOZ_STT", valor, achados,
        desligado="Transcrição desligada (VOZ_STT_URL vazia): a janela funciona só em texto.",
        exige_voz=False,
    )
    tts = _servico(
        "VOZ_TTS", valor, achados,
        desligado="Síntese desligada (VOZ_TTS_URL vazia): as respostas aparecem só em texto.",
        exige_voz=True,
    )

    idioma = valor("VOZ_IDIOMA")
    if idioma is not None and idioma not in IDIOMAS_ACEITOS:
        achados.append(Achado(ERRO, "VOZ_IDIOMA", f"Idioma '{idioma}' não aceito; use um de: {', '.join(IDIOMAS_ACEITOS)}."))
        idioma = None
    elif idioma is None and stt is not None:
        achados.append(Achado(
            AVISO, "VOZ_IDIOMA",
            "Idioma da transcrição não informado. Nenhum idioma é escolhido aqui; o servidor de transcrição decide.",
        ))

    ice: list[str] = []
    for item in (valor("VOZ_ICE_SERVIDORES") or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith(PREFIXOS_ICE):
            ice.append(item)
        else:
            achados.append(Achado(ERRO, "VOZ_ICE_SERVIDORES", f"'{item}' não começa com stun:, turn: ou turns:."))

    porta = PORTA_PADRAO
    bruta = valor("HARNESS_PORTA")
    if bruta is not None:
        if bruta.isdigit() and 1 <= int(bruta) <= 65535:
            porta = int(bruta)
        else:
            achados.append(Achado(ERRO, "HARNESS_PORTA", f"Porta '{bruta}' inválida (1 a 65535)."))

    return Configuracao(stt=stt, tts=tts, idioma=idioma, ice_servidores=tuple(ice), porta=porta, achados=tuple(achados))


def _servico(prefixo: str, valor, achados: list[Achado], desligado: str, exige_voz: bool) -> Servico | None:
    url = valor(f"{prefixo}_URL")
    modelo = valor(f"{prefixo}_MODELO")
    chave = valor(f"{prefixo}_CHAVE")
    voz = valor(f"{prefixo}_VOZ") if exige_voz else None

    if url is None:
        achados.append(Achado(INFO, f"{prefixo}_URL", desligado))
        sobras = [n for n, v in ((f"{prefixo}_MODELO", modelo), (f"{prefixo}_VOZ", voz), (f"{prefixo}_CHAVE", chave)) if v]
        if sobras:
            achados.append(Achado(AVISO, f"{prefixo}_URL", f"{', '.join(sobras)} preenchida(s), mas sem URL o serviço fica desligado."))
        return None

    ok = True
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        achados.append(Achado(ERRO, f"{prefixo}_URL", f"'{url}' não é um endereço http(s) válido."))
        ok = False
    if modelo is None:
        achados.append(Achado(ERRO, f"{prefixo}_MODELO", "Modelo não informado. Nenhum modelo é escolhido aqui; informe o do seu servidor."))
        ok = False
    if exige_voz and voz is None:
        achados.append(Achado(ERRO, f"{prefixo}_VOZ", "Voz não informada. Nenhuma voz é escolhida aqui; informe uma que o seu servidor aceite."))
        ok = False
    if not ok:
        return None
    return Servico(url=url, modelo=modelo, chave=chave, voz=voz)


def resumo_publico(config: Configuracao) -> dict:
    """Versão para mostrar ou registrar: a chave nunca aparece, só se existe."""

    def servico(s: Servico | None) -> dict | None:
        if s is None:
            return None
        saida = {"url": s.url, "modelo": s.modelo, "chave": "definida" if s.chave else "ausente"}
        if s.voz is not None:
            saida["voz"] = s.voz
        return saida

    return {
        "stt": servico(config.stt),
        "tts": servico(config.tts),
        "idioma": config.idioma,
        "ice_servidores": list(config.ice_servidores),
        "porta": config.porta,
        "achados": [{"nivel": a.nivel, "variavel": a.variavel, "mensagem": a.mensagem} for a in config.achados],
    }
