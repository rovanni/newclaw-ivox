"""`python -m newclaw_ivox diagnostico` — mostra o que está configurado e o que falta, sem chamar nenhum serviço.

Saída: 0 = pronto; 1 = configuração com erro; 2 = nada configurado (nem transcrição nem síntese).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import configuracao as cfg

SAIDA_OK = 0
SAIDA_ERRO = 1
SAIDA_NADA_CONFIGURADO = 2

_ROTULO = {cfg.ERRO: "ERRO ", cfg.AVISO: "AVISO", cfg.INFO: "info "}


def codigo_de_saida(config: cfg.Configuracao) -> int:
    if config.tem_erro:
        return SAIDA_ERRO
    if config.nada_configurado:
        return SAIDA_NADA_CONFIGURADO
    return SAIDA_OK


def texto(config: cfg.Configuracao) -> str:
    resumo = cfg.resumo_publico(config)
    linhas = ["newclaw-ivox — diagnóstico da configuração do motor de voz", ""]
    for nome, rotulo in (("stt", "Transcrição"), ("tts", "Síntese")):
        s = resumo[nome]
        if s is None:
            linhas.append(f"{rotulo}: desligada")
        else:
            extra = f", voz {s['voz']}" if "voz" in s else ""
            linhas.append(f"{rotulo}: {s['url']} (modelo {s['modelo']}{extra}, chave {s['chave']})")
    linhas.append(f"Idioma: {resumo['idioma'] or 'não informado'}")
    linhas.append(f"STUN/TURN: {', '.join(resumo['ice_servidores']) or 'nenhum'}")
    linhas.append(f"Porta local: 127.0.0.1:{resumo['porta']}")
    if config.achados:
        linhas.append("")
        linhas.extend(f"[{_ROTULO[a.nivel]}] {a.variavel}: {a.mensagem}" for a in config.achados)
    codigo = codigo_de_saida(config)
    linhas.append("")
    if codigo == SAIDA_NADA_CONFIGURADO:
        linhas.append(
            "Nada a fazer: nem transcrição nem síntese configuradas. Preencha VOZ_STT_* e/ou VOZ_TTS_* "
            "(veja .env.example) e rode de novo."
        )
    elif codigo == SAIDA_ERRO:
        linhas.append("Corrija os erros acima antes de iniciar o motor de voz.")
    else:
        linhas.append("Configuração completa.")
    return "\n".join(linhas)


def principal(argumentos: list[str], ambiente=None, raiz: Path | None = None) -> int:
    raiz = raiz or Path.cwd()
    config = cfg.carregar(ambiente, raiz / ".env")
    if "--json" in argumentos:
        saida = cfg.resumo_publico(config)
        saida["codigo"] = codigo_de_saida(config)
        print(json.dumps(saida, ensure_ascii=False, indent=2))
    else:
        print(texto(config))
    return codigo_de_saida(config)


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
