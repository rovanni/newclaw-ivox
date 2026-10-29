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
            continue
        partes = [f"modelo {s['modelo']}"] if s["modelo"] else []
        if "voz" in s:
            partes.append(f"voz {s['voz']}")
        elif nome == "tts" and s["motor"] == cfg.LOCAL:
            partes.append("voz escolhida na interface")
        if s["motor"] == cfg.URL:
            partes.append(f"chave {s['chave']}")
            onde = s["url"]
        else:
            onde = "nesta máquina"
        linhas.append(f"{rotulo}: {onde} ({', '.join(partes)})")
    linhas.append(f"Idioma: {resumo['idioma'] or 'não informado'}")
    linhas.append(f"Dispositivo: {resumo['dispositivo']}")
    linhas.append(f"Pasta dos modelos: {resumo['modelos_dir']}")
    linhas.append(f"STUN/TURN: {', '.join(resumo['ice_servidores']) or 'nenhum'}")
    linhas.append(f"Harness: {'https' if resumo['https'] else 'http'}://{resumo['host']}:{resumo['porta']}")
    linhas.append(f"NewClaw: {resumo['newclaw_url'] or 'não informado'}")
    if config.achados:
        linhas.append("")
        linhas.extend(f"[{_ROTULO[a.nivel]}] {a.variavel}: {a.mensagem}" for a in config.achados)
    codigo = codigo_de_saida(config)
    linhas.append("")
    if codigo == SAIDA_NADA_CONFIGURADO:
        linhas.append(
            "Nada a fazer: nem transcrição nem síntese configuradas. Rode o instalador "
            "(python instalar.py) ou preencha VOZ_STT_* e/ou VOZ_TTS_* (veja .env.example)."
        )
    elif codigo == SAIDA_ERRO:
        linhas.append("Corrija os erros acima antes de iniciar o motor de voz.")
    else:
        linhas.append("Configuração completa.")
    return "\n".join(linhas)


def principal(argumentos: list[str], ambiente=None, raiz: Path | None = None) -> int:
    raiz = raiz or Path.cwd()
    config = cfg.carregar(ambiente, raiz / ".env", raiz)
    if "--json" in argumentos:
        saida = cfg.resumo_publico(config)
        saida["codigo"] = codigo_de_saida(config)
        print(json.dumps(saida, ensure_ascii=False, indent=2))
    else:
        print(texto(config))
    return codigo_de_saida(config)


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
