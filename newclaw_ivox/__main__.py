import sys

from . import diagnostico

COMANDOS = {"diagnostico": diagnostico.principal}


def main() -> int:
    # Fora de um terminal (pipe, arquivo, outro programa lendo o JSON), o Windows usaria a página de código local e
    # estragaria os acentos. No terminal, o Python já escreve Unicode.
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        print(f"uso: python -m newclaw_ivox <{'|'.join(COMANDOS)}> [--json]", file=sys.stderr)
        return 64
    return COMANDOS[sys.argv[1]](sys.argv[2:])


sys.exit(main())
