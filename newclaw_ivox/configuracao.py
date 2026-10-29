"""Configuração do motor de voz, lida só do ambiente (e de um `.env` opcional).

Regra (ADR-030, revisão de 29/10/2026): transcrição e síntese rodam na máquina do usuário (`local`), ou num servidor que
ele declarar (`url`). Nada é adivinhado: modelo, voz e idioma vêm da escolha do usuário, e o que falta é reportado. Se há GPU
é medido (`dispositivo.py`), nunca suposto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

# Idiomas que o `Language` do Pipecat aceita e que o NewClaw usa (ADR-030, tabela 4).
IDIOMAS_ACEITOS = ("pt-BR", "en-US", "es-ES")

LOCAL = "local"
URL = "url"
MOTORES = (LOCAL, URL)

DISPOSITIVOS = ("auto", "cpu", "cuda")

# A porta é o único valor de rede com padrão: é endereço local, não escolha de recurso. O harness escuta só em 127.0.0.1,
# a não ser que HARNESS_HOST diga outra coisa — e aí só com HTTPS (decisão H3).
PORTA_PADRAO = 7860
HOST_PADRAO = "127.0.0.1"
HOSTS_LOCAIS = ("127.0.0.1", "localhost", "::1")


def host_e_local(host: str) -> bool:
    return host in HOSTS_LOCAIS

# Pasta dos modelos baixados, relativa à raiz do harness, quando VOZ_MODELOS_DIR não é informada. É lugar de arquivo,
# não escolha de recurso.
PASTA_MODELOS_PADRAO = "modelos"

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
    """Transcrição ou síntese: local (na máquina) ou por URL (servidor compatível com a API OpenAI)."""

    motor: str
    modelo: str | None
    voz: str | None = None
    url: str | None = None
    chave: str | None = None


@dataclass(frozen=True)
class Configuracao:
    stt: Servico | None
    tts: Servico | None
    idioma: str | None
    dispositivo: str
    modelos_dir: Path
    ice_servidores: tuple[str, ...]
    porta: int
    achados: tuple[Achado, ...] = field(default=())
    # Servidor do harness (Etapa 3).
    newclaw_url: str | None = None
    host: str = HOST_PADRAO
    tls_cert: Path | None = None
    tls_chave: Path | None = None

    @property
    def com_tls(self) -> bool:
        return self.tls_cert is not None and self.tls_chave is not None

    @property
    def origem(self) -> str:
        """A origem que o navegador manda (`Origin`) quando a página vem deste servidor."""
        esquema = "https" if self.com_tls else "http"
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{esquema}://{host}:{self.porta}"

    @property
    def origens_aceitas(self) -> tuple[str, ...]:
        """Em loopback, `localhost` e `127.0.0.1` são a mesma máquina; o navegador manda o nome que estiver na barra."""
        esquema = "https" if self.com_tls else "http"
        if host_e_local(self.host):
            return tuple(f"{esquema}://{h}:{self.porta}" for h in ("localhost", "127.0.0.1", "[::1]"))
        return (self.origem,)

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


def carregar(
    ambiente: Mapping[str, str] | None = None,
    arquivo_env: Path | None = None,
    raiz: Path | None = None,
) -> Configuracao:
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
        desligado="Transcrição desligada (VOZ_STT_MOTOR vazio): a janela funciona só em texto.",
        local_exige=("MODELO",), url_exige=("URL", "MODELO"),
    )
    tts = _servico(
        "VOZ_TTS", valor, achados,
        desligado="Síntese desligada (VOZ_TTS_MOTOR vazio): as respostas aparecem só em texto.",
        # Local: todas as vozes do Kokoro vêm num arquivo só, e a voz é escolhida (e trocada) na interface; VOZ_TTS_VOZ,
        # se houver, é só a voz com que o motor começa. Servidor: a voz é parte do pedido e precisa ser declarada.
        local_exige=(), url_exige=("URL", "MODELO", "VOZ"),
    )
    if tts is not None and tts.motor == LOCAL and tts.voz is None:
        achados.append(Achado(INFO, "VOZ_TTS_VOZ", "Nenhuma voz inicial: a voz é escolhida na interface antes da primeira fala."))

    idioma = valor("VOZ_IDIOMA")
    if idioma is not None and idioma not in IDIOMAS_ACEITOS:
        achados.append(Achado(ERRO, "VOZ_IDIOMA", f"Idioma '{idioma}' não aceito; use um de: {', '.join(IDIOMAS_ACEITOS)}."))
        idioma = None
    elif idioma is None and (stt is not None or tts is not None):
        achados.append(Achado(
            AVISO, "VOZ_IDIOMA",
            "Idioma não informado. Nenhum idioma é escolhido aqui; a transcrição detecta sozinha, se puder.",
        ))

    dispositivo = valor("VOZ_DISPOSITIVO") or "auto"
    if dispositivo not in DISPOSITIVOS:
        achados.append(Achado(ERRO, "VOZ_DISPOSITIVO", f"'{dispositivo}' não aceito; use um de: {', '.join(DISPOSITIVOS)}."))
        dispositivo = "auto"

    pasta = valor("VOZ_MODELOS_DIR")
    base = raiz or Path.cwd()
    modelos_dir = Path(pasta) if pasta else base / PASTA_MODELOS_PADRAO
    if not modelos_dir.is_absolute():
        modelos_dir = base / modelos_dir

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

    newclaw_url = valor("NEWCLAW_URL")
    if newclaw_url is None:
        achados.append(Achado(INFO, "NEWCLAW_URL", "Endereço do NewClaw não informado: o motor roda sozinho, mas o servidor do harness não sobe."))
    else:
        partes = urlparse(newclaw_url)
        if partes.scheme not in ("http", "https") or not partes.netloc or partes.path not in ("", "/"):
            achados.append(Achado(ERRO, "NEWCLAW_URL", f"'{newclaw_url}' não é um endereço http(s) de servidor (ex.: http://localhost:3090)."))
            newclaw_url = None
        else:
            newclaw_url = newclaw_url.rstrip("/")

    host = valor("HARNESS_HOST") or HOST_PADRAO
    tls_cert, tls_chave = valor("HARNESS_TLS_CERT"), valor("HARNESS_TLS_CHAVE")
    cert = chave = None
    if (tls_cert is None) != (tls_chave is None):
        achados.append(Achado(ERRO, "HARNESS_TLS_CERT", "HTTPS precisa dos dois: HARNESS_TLS_CERT e HARNESS_TLS_CHAVE."))
    elif tls_cert is not None:
        for variavel, caminho in (("HARNESS_TLS_CERT", tls_cert), ("HARNESS_TLS_CHAVE", tls_chave)):
            if not Path(caminho).is_file():
                achados.append(Achado(ERRO, variavel, f"Arquivo '{caminho}' não encontrado."))
        if not any(a.variavel in ("HARNESS_TLS_CERT", "HARNESS_TLS_CHAVE") and a.nivel == ERRO for a in achados):
            cert, chave = Path(tls_cert), Path(tls_chave)
    if not host_e_local(host) and cert is None:
        achados.append(Achado(
            ERRO, "HARNESS_HOST",
            f"Escutar em '{host}' expõe o harness à rede: isso só com HTTPS (HARNESS_TLS_CERT e HARNESS_TLS_CHAVE). "
            "Sem certificado, use 127.0.0.1 e o microfone funciona só nesta máquina.",
        ))

    return Configuracao(
        stt=stt, tts=tts, idioma=idioma, dispositivo=dispositivo, modelos_dir=modelos_dir,
        ice_servidores=tuple(ice), porta=porta, achados=tuple(achados),
        newclaw_url=newclaw_url, host=host, tls_cert=cert, tls_chave=chave,
    )


_EXPLICACAO = {
    "MODELO": "Modelo não informado. Nenhum modelo é escolhido aqui.",
    "VOZ": "Voz não informada. Nenhuma voz é escolhida aqui.",
    "URL": "Endereço do servidor não informado.",
}


def _servico(prefixo, valor, achados: list[Achado], desligado: str, local_exige, url_exige) -> Servico | None:
    motor = valor(f"{prefixo}_MOTOR")
    campos = {nome: valor(f"{prefixo}_{nome}") for nome in ("MODELO", "VOZ", "URL", "CHAVE")}

    if motor is None:
        achados.append(Achado(INFO, f"{prefixo}_MOTOR", desligado))
        sobras = [f"{prefixo}_{n}" for n, v in campos.items() if v]
        if sobras:
            achados.append(Achado(AVISO, f"{prefixo}_MOTOR", f"{', '.join(sobras)} preenchida(s), mas sem motor o serviço fica desligado."))
        return None

    if motor not in MOTORES:
        achados.append(Achado(ERRO, f"{prefixo}_MOTOR", f"Motor '{motor}' não aceito; use '{LOCAL}' (nesta máquina) ou '{URL}' (servidor)."))
        return None

    ok = True
    for nome in local_exige if motor == LOCAL else url_exige:
        if campos[nome] is None:
            achados.append(Achado(ERRO, f"{prefixo}_{nome}", _EXPLICACAO[nome]))
            ok = False
    if motor == URL and campos["URL"] is not None:
        partes = urlparse(campos["URL"])
        if partes.scheme not in ("http", "https") or not partes.netloc:
            achados.append(Achado(ERRO, f"{prefixo}_URL", f"'{campos['URL']}' não é um endereço http(s) válido."))
            ok = False
    if motor == LOCAL:
        ignoradas = [f"{prefixo}_{n}" for n in ("URL", "CHAVE") if campos[n]]
        if ignoradas:
            achados.append(Achado(AVISO, f"{prefixo}_MOTOR", f"{', '.join(ignoradas)} só vale(m) no motor '{URL}'; ignorada(s)."))
    if not ok:
        return None
    if motor == LOCAL:
        return Servico(motor=LOCAL, modelo=campos["MODELO"], voz=campos["VOZ"])
    return Servico(motor=URL, modelo=campos["MODELO"], voz=campos["VOZ"], url=campos["URL"], chave=campos["CHAVE"])


def resumo_publico(config: Configuracao) -> dict:
    """Versão para mostrar ou registrar: a chave nunca aparece, só se existe."""

    def servico(s: Servico | None) -> dict | None:
        if s is None:
            return None
        saida = {"motor": s.motor, "modelo": s.modelo}
        if s.voz is not None:
            saida["voz"] = s.voz
        if s.motor == URL:
            saida["url"] = s.url
            saida["chave"] = "definida" if s.chave else "ausente"
        return saida

    return {
        "stt": servico(config.stt),
        "tts": servico(config.tts),
        "idioma": config.idioma,
        "dispositivo": config.dispositivo,
        "modelos_dir": str(config.modelos_dir),
        "ice_servidores": list(config.ice_servidores),
        "porta": config.porta,
        "newclaw_url": config.newclaw_url,
        "host": config.host,
        "https": config.com_tls,
        "achados": [{"nivel": a.nivel, "variavel": a.variavel, "mensagem": a.mensagem} for a in config.achados],
    }
