"""Inventário do que terceiros trazem para dentro do ambiente do motor de voz (ADR-030, decisão L1).

Lê só o ambiente Python em que roda — nada de rede. Lista:
- cada pacote instalado, com versão e a licença que ele mesmo declara;
- as bibliotecas nativas embutidas (.dll / .so / .dylib), por pacote, com os arquivos de licença que vieram junto;
- a configuração de compilação do FFmpeg dentro do PyAV e os codecs com licença GPL;
- os modelos ONNX dentro do Pipecat, com SHA-256.

Uso (com o Python do ambiente que vai rodar o motor):
    .venv/Scripts/python -I ferramentas/inventario_terceiros.py > docs/terceiros/<sistema>.json
    .venv/Scripts/python -I ferramentas/inventario_terceiros.py --markdown > docs/terceiros/<sistema>.md

É levantamento técnico, não parecer jurídico: registra o que cada pacote declara e o que está no disco.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import platform
import re
import sys
from pathlib import Path

EXTENSOES_NATIVAS = (".dll", ".so", ".dylib", ".pyd")
# Bibliotecas cuja licença de origem é GPL ou LGPL e que costumam vir embutidas em pacotes de áudio e vídeo.
NATIVAS_COPYLEFT = {
    "libx264": "GPL-2.0-or-later (x264)",
    "libx265": "GPL-2.0-or-later (x265)",
    "libsndfile": "LGPL-2.1-or-later (libsndfile)",
    "opencv_videoio_ffmpeg": "LGPL (FFmpeg do OpenCV; ver LICENSE-3RD-PARTY.txt do pacote)",
    "avcodec": "LGPL (FFmpeg do PyAV; ver configuração abaixo)",
    "libmp3lame": "LGPL-2.0-or-later (LAME)",
}
CODECS_GPL = ("libx264", "libx264rgb", "libx265", "libxvid", "libfdk_aac")


def _licenca_declarada(meta) -> str:
    texto = (meta.get("License-Expression") or meta.get("License") or "").strip()
    if "\n" in texto or len(texto) > 80:  # alguns pacotes põem o texto inteiro da licença no campo
        texto = texto.splitlines()[0][:80] + " (texto longo no metadado)"
    if not texto:
        classes = [c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
        texto = "; ".join(classes)
    return texto or "não declarada"


def pacotes() -> list[dict]:
    saida = []
    for d in md.distributions():
        arquivos = [str(f) for f in (d.files or [])]
        nativas = sorted({Path(f).name for f in arquivos if f.lower().endswith(EXTENSOES_NATIVAS) and not f.lower().endswith(".pyd")})
        licencas = sorted({f for f in arquivos if re.search(r"licen[cs]e|copying|notice", f, re.I)})
        saida.append({
            "nome": d.metadata["Name"],
            "versao": d.version,
            "licenca_declarada": _licenca_declarada(d.metadata),
            "bibliotecas_nativas": nativas,
            "arquivos_de_licenca": licencas,
        })
    return sorted(saida, key=lambda p: p["nome"].lower())


def copyleft_nativo(lista: list[dict]) -> list[dict]:
    achados = []
    for p in lista:
        for lib in p["bibliotecas_nativas"]:
            for prefixo, licenca in NATIVAS_COPYLEFT.items():
                if lib.lower().startswith(prefixo):
                    achados.append({"pacote": p["nome"], "arquivo": lib, "licenca_de_origem": licenca})
    return achados


def ffmpeg_do_pyav() -> dict:
    try:
        import av
        import av._core as core  # type: ignore[import-not-found]
    except Exception as e:  # noqa: BLE001 — o inventário registra a ausência, não quebra
        return {"ausente": f"{type(e).__name__}: {e}"}
    meta = getattr(core, "library_meta", {}).get("libavcodec", {})
    configuracao = meta.get("configuration", "")
    codecs = set(av.codecs_available)
    return {
        "pyav": av.__version__,
        "licenca_informada_pelo_ffmpeg": meta.get("license"),
        "enable_gpl": "--enable-gpl" in configuracao,
        "bibliotecas_externas_habilitadas": sorted(re.findall(r"--enable-(lib[\w-]+)", configuracao)),
        "codecs_gpl_presentes": sorted(c for c in CODECS_GPL if c in codecs),
        "opus": "libopus" in codecs or "opus" in codecs,
        "configuracao": configuracao,
    }


def modelos_onnx() -> list[dict]:
    try:
        import pipecat
    except Exception:  # noqa: BLE001
        return []
    raiz = Path(pipecat.__file__).parent
    return [
        {
            "arquivo": p.relative_to(raiz).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "licenca_no_pacote": "não declarada (o pacote não traz arquivo de licença do modelo)",
        }
        for p in sorted(raiz.rglob("*.onnx"))
    ]


def inventario() -> dict:
    lista = pacotes()
    return {
        "sistema": platform.platform(),
        "python": platform.python_version(),
        "pacotes": lista,
        "nativas_copyleft": copyleft_nativo(lista),
        "ffmpeg_pyav": ffmpeg_do_pyav(),
        "modelos_onnx": modelos_onnx(),
    }


def markdown(dados: dict) -> str:
    f = dados["ffmpeg_pyav"]
    linhas = [
        f"# Terceiros no ambiente do motor de voz — {dados['sistema']}",
        "",
        f"Gerado por `ferramentas/inventario_terceiros.py` (Python {dados['python']}). Levantamento técnico, não parecer"
        " jurídico: registra o que cada pacote declara e o que está no disco.",
        "",
        "## Bibliotecas nativas de origem GPL/LGPL",
        "",
        "| Pacote | Arquivo | Licença de origem |",
        "|---|---|---|",
    ]
    linhas += [f"| {a['pacote']} | `{a['arquivo']}` | {a['licenca_de_origem']} |" for a in dados["nativas_copyleft"]]
    proprietarias = [p for p in dados["pacotes"] if "proprietary" in p["licenca_declarada"].lower()]
    linhas += ["", "## Pacotes com licença proprietária", ""]
    if proprietarias:
        linhas += ["Instalados do PyPI na máquina de quem usa; não podem ser redistribuídos com o harness.", ""]
        linhas += [f"- {p['nome']} {p['versao']}: {p['licenca_declarada']}" for p in proprietarias]
    else:
        linhas.append("Nenhum.")
    linhas += ["", "## FFmpeg dentro do PyAV", ""]
    if "ausente" in f:
        linhas.append(f"PyAV não instalado: {f['ausente']}")
    else:
        linhas += [
            f"- PyAV {f['pyav']}; licença informada pelo próprio FFmpeg: **{f['licenca_informada_pelo_ffmpeg']}**;"
            f" `--enable-gpl`: **{'sim' if f['enable_gpl'] else 'não'}**.",
            f"- Codecs de licença GPL presentes: {', '.join(f['codecs_gpl_presentes']) or 'nenhum'}.",
            f"- Opus (áudio do WebRTC): {'sim' if f['opus'] else 'não'}.",
            f"- Bibliotecas externas habilitadas: {', '.join(f['bibliotecas_externas_habilitadas'])}.",
        ]
    linhas += ["", "## Modelos ONNX dentro do Pipecat", "", "| Arquivo | Bytes | SHA-256 | Licença |", "|---|---|---|---|"]
    linhas += [f"| `{m['arquivo']}` | {m['bytes']} | `{m['sha256'][:16]}…` | {m['licenca_no_pacote']} |" for m in dados["modelos_onnx"]]
    linhas += ["", f"## Pacotes ({len(dados['pacotes'])})", "", "| Pacote | Versão | Licença declarada | Nativas |", "|---|---|---|---|"]
    linhas += [
        f"| {p['nome']} | {p['versao']} | {p['licenca_declarada']} | {len(p['bibliotecas_nativas']) or ''} |"
        for p in dados["pacotes"]
    ]
    return "\n".join(linhas) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    dados = inventario()
    print(markdown(dados) if "--markdown" in sys.argv else json.dumps(dados, ensure_ascii=False, indent=1))
