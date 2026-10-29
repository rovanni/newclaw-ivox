import sys

from . import diagnostico


def _modelos(argumentos):
    from . import comandos

    return comandos.modelos(argumentos)


def _testar_stt(argumentos):
    from . import comandos

    return comandos.testar_stt(argumentos)


def _testar_tts(argumentos):
    from . import comandos

    return comandos.testar_tts(argumentos)


def _exportar_vozes(argumentos):
    from . import comandos

    return comandos.exportar_vozes(argumentos)


def _instalar(argumentos):
    from . import instalador

    return instalador.principal(argumentos)


COMANDOS = {
    "diagnostico": diagnostico.principal,
    "exportar-vozes": _exportar_vozes,
    "instalar": _instalar,
    "modelos": _modelos,
    "testar-stt": _testar_stt,
    "testar-tts": _testar_tts,
}


def main() -> int:
    # Fora de um terminal (pipe, arquivo, outro programa lendo o JSON), o Windows usaria a página de código local e
    # estragaria os acentos. No terminal, o Python já escreve Unicode.
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        print(f"uso: python -m newclaw_ivox <{'|'.join(COMANDOS)}> [opções]", file=sys.stderr)
        return 64
    return COMANDOS[sys.argv[1]](sys.argv[2:])


sys.exit(main())
