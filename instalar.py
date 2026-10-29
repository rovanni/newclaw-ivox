"""Instalador do newclaw-ivox. Uso: python instalar.py   (ou: python instalar.py --simular)

Precisa só do Python 3.10+ do sistema; o resto ele instala na pasta `.venv` deste projeto, perguntando antes.
"""

import sys

if sys.version_info < (3, 10):
    print(f"O newclaw-ivox precisa do Python 3.10 ou mais novo; este é {sys.version.split()[0]}.")
    sys.exit(1)

if not sys.stdout.isatty():
    sys.stdout.reconfigure(encoding="utf-8")

from newclaw_ivox.instalador import principal  # noqa: E402

sys.exit(principal(sys.argv[1:]))
