"""Instalador do newclaw-ivox: mede a máquina, pergunta o que a pessoa quer, instala, baixa e testa.

Roda com o Python do sistema e usa só a biblioteca padrão; o que precisa do Pipecat roda depois, pelo Python do `.venv`
recém-criado. Segue os passos do instalador do NewClaw (medir o sistema → instalar → baixar modelo → configurar → testar →
resumo), num arquivo só para Windows, Linux e macOS.

Regras:
- nada é escolhido pela pessoa sem ela ver: modelo e idioma não têm resposta padrão;
- antes de instalar ou baixar, mostra o que vai fazer e pergunta;
- o `.env` é atualizado só nas chaves de voz, e o resto dele fica como estava;
- `--simular` mostra os comandos e não executa nada.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import configuracao as cfg
from . import dispositivo as disp

PYTHON_MINIMO = (3, 10)
CHAVES_DE_VOZ = (
    "VOZ_STT_MOTOR", "VOZ_STT_MODELO", "VOZ_STT_URL", "VOZ_STT_CHAVE",
    "VOZ_TTS_MOTOR", "VOZ_TTS_MODELO", "VOZ_TTS_VOZ", "VOZ_TTS_URL", "VOZ_TTS_CHAVE",
    "VOZ_IDIOMA", "VOZ_DISPOSITIVO",
)


class Cancelado(Exception):
    pass


class Instalador:
    def __init__(self, raiz: Path, simular: bool = False, entrada=input, saida=None):
        self.raiz = raiz
        self.simular = simular
        self.entrada = entrada
        # flush: os comandos filhos escrevem direto no terminal; sem ele, as mensagens daqui saem fora de ordem.
        self.saida = saida or (lambda texto: print(texto, flush=True))

    # ─── conversa ────────────────────────────────────────────────────────────

    def titulo(self, texto: str) -> None:
        self.saida("")
        self.saida(f"▸ {texto}")

    def info(self, texto: str) -> None:
        self.saida(f"    {texto}")

    def perguntar(self, texto: str) -> str:
        try:
            return self.entrada(f"    {texto} ").strip()
        except EOFError as e:
            raise Cancelado("entrada encerrada antes da resposta") from e

    def escolher(self, texto: str, opcoes: list[tuple[str, str]]) -> str:
        """Lista numerada sem resposta padrão: Enter vazio pergunta de novo."""
        self.info(texto)
        for i, (_, rotulo) in enumerate(opcoes, 1):
            self.info(f"  {i}) {rotulo}")
        while True:
            resposta = self.perguntar(f"Escolha de 1 a {len(opcoes)}:")
            if resposta.isdigit() and 1 <= int(resposta) <= len(opcoes):
                return opcoes[int(resposta) - 1][0]
            self.info("Resposta não reconhecida; digite o número de uma opção.")

    def confirmar(self, texto: str) -> bool:
        while True:
            resposta = self.perguntar(f"{texto} [s/n]").lower()
            if resposta in ("s", "sim"):
                return True
            if resposta in ("n", "nao", "não"):
                return False
            self.info("Responda s ou n.")

    def executar(self, comando: list[str]) -> None:
        self.info("$ " + " ".join(comando))
        if self.simular:
            return
        resultado = subprocess.run(comando, cwd=self.raiz)
        if resultado.returncode != 0:
            raise RuntimeError(f"O comando terminou com código {resultado.returncode}.")

    # ─── caminhos ────────────────────────────────────────────────────────────

    @property
    def venv(self) -> Path:
        return self.raiz / ".venv"

    @property
    def python_venv(self) -> Path:
        return self.venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    def rodar_no_venv(self, *argumentos: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.python_venv), "-m", "newclaw_ivox", *argumentos],
            cwd=self.raiz, capture_output=True, text=True, encoding="utf-8",
        )

    # ─── passos ──────────────────────────────────────────────────────────────

    def medir(self) -> disp.Sistema:
        self.titulo("Esta máquina")
        sistema = disp.medir_sistema(self.raiz)
        self.info(f"Sistema: {sistema.sistema}")
        self.info(f"Python: {sistema.python}")
        self.info(f"GPU NVIDIA: {', '.join(sistema.gpus_nvidia) or 'nenhuma encontrada (nvidia-smi ausente ou sem placa)'}")
        if sistema.espaco_livre_bytes is not None:
            self.info(f"Espaço livre nesta pasta: {sistema.espaco_livre_bytes / 1024**3:.1f} GB")
        if sys.version_info < PYTHON_MINIMO:
            raise RuntimeError(f"Este Python é {sistema.python}; o newclaw-ivox precisa do {'.'.join(map(str, PYTHON_MINIMO))} ou mais novo.")
        return sistema

    def perguntar_transcricao(self) -> dict[str, str]:
        self.titulo("Transcrição (fala → texto)")
        motor = self.escolher("Onde transcrever?", [
            (cfg.LOCAL, "Nesta máquina (Whisper local; não depende de outro computador)"),
            (cfg.URL, "Num servidor que eu já tenho (compatível com a API OpenAI)"),
            ("", "Desligada (só texto)"),
        ])
        if motor == cfg.URL:
            return {
                "VOZ_STT_MOTOR": cfg.URL,
                "VOZ_STT_URL": self.perguntar("Endereço do servidor (ex.: http://servidor:porta/v1):"),
                "VOZ_STT_MODELO": self.perguntar("Modelo, como o servidor o chama:"),
                "VOZ_STT_CHAVE": self.perguntar("Chave (Enter se o servidor não pede):"),
            }
        if motor == "":
            return {"VOZ_STT_MOTOR": ""}
        return {"VOZ_STT_MOTOR": cfg.LOCAL}

    def preparar_ambiente(self, sistema: disp.Sistema, com_stt_local: bool) -> None:
        self.titulo("Ambiente Python do motor de voz")
        extras = ["motor"]
        if com_stt_local:
            extras.append("stt-local")
            if sistema.gpus_nvidia and sys.platform != "darwin":
                extras.append("cuda")
        self.info(f"Pasta: {self.venv}")
        self.info(f"Pacotes: newclaw-ivox[{','.join(extras)}], baixados do PyPI para dentro dessa pasta.")
        if "cuda" in extras:
            self.info("Inclui as bibliotecas CUDA da NVIDIA (~2 GB no Windows), porque uma GPU NVIDIA foi encontrada.")
            self.info("Elas têm licença proprietária da NVIDIA: vêm do PyPI para esta máquina e não podem ser redistribuídas.")
        self.info("Licenças de terceiros: docs/terceiros/ (há bibliotecas GPL/LGPL; vêm do PyPI, não deste repositório).")
        if not self.confirmar("Instalar agora?"):
            raise Cancelado("instalação recusada")
        uv = shutil.which("uv")
        if not self.python_venv.exists():
            self.executar([uv, "venv", str(self.venv), "--python", sys.executable] if uv else [sys.executable, "-m", "venv", str(self.venv)])
        pip = [uv, "pip", "install", "--python", str(self.python_venv)] if uv else [str(self.python_venv), "-m", "pip", "install"]
        self.executar([*pip, "-e", f".[{','.join(extras)}]"])

    def escolher_modelo_stt(self, modelos_dir: Path) -> str:
        self.titulo("Modelo do Whisper")
        if self.simular:
            self.info("(simulação: a lista viria do faster-whisper instalado)")
            return self.perguntar("Nome do modelo:")
        resultado = self.rodar_no_venv("modelos", "--json", "--pasta", str(modelos_dir))
        if resultado.returncode != 0:
            raise RuntimeError("Não consegui listar os modelos: " + (resultado.stderr.strip().splitlines() or ["sem detalhe"])[-1])
        lista = json.loads(resultado.stdout)
        self.info("Tamanhos medidos agora no Hugging Face. Os maiores erram menos e pesam mais; '.en' só entende inglês.")
        opcoes = [
            (m["nome"], f"{m['nome']:<20} {m['tamanho']:>12}{'   (já baixado)' if m['instalado'] else ''}")
            for m in lista
        ]
        return self.escolher("Qual modelo?", opcoes)

    def baixar_modelo_stt(self, modelos_dir: Path, nome: str) -> None:
        if self.simular:
            self.info(f"(simulação: baixaria '{nome}' para {modelos_dir})")
            return
        resultado = self.rodar_no_venv("modelos", "--json", "--pasta", str(modelos_dir))
        dados = next((m for m in json.loads(resultado.stdout) if m["nome"] == nome), None)
        if dados and dados["instalado"]:
            self.info(f"'{nome}' já está em {dados['pasta']}.")
            return
        tamanho = dados["tamanho"] if dados else "tamanho não medido"
        if not self.confirmar(f"Baixar '{nome}' ({tamanho}) do Hugging Face para {modelos_dir}?"):
            raise Cancelado("download recusado")
        self.executar([str(self.python_venv), "-m", "newclaw_ivox", "modelos", "--baixar", nome, "--pasta", str(modelos_dir)])

    def perguntar_idioma(self) -> str:
        self.titulo("Idioma")
        return self.escolher("Em que idioma você vai falar?", [
            ("pt-BR", "Português (Brasil)"), ("en-US", "English (US)"), ("es-ES", "Español"),
        ])

    def gravar_env(self, valores: dict[str, str]) -> Path:
        self.titulo("Configuração")
        caminho = self.raiz / ".env"
        linhas = caminho.read_text(encoding="utf-8").splitlines() if caminho.exists() else []
        restantes = dict(valores)
        novas = []
        for linha in linhas:
            nome = linha.split("=", 1)[0].strip().removeprefix("export ").strip() if "=" in linha else None
            if nome in restantes:
                novas.append(f"{nome}={restantes.pop(nome)}")
            else:
                novas.append(linha)
        if restantes:
            if novas and novas[-1].strip():
                novas.append("")
            novas.append("# Voz — gravado pelo instalador do newclaw-ivox")
            novas.extend(f"{k}={v}" for k, v in restantes.items())
        self.info(f"{'Atualizaria' if self.simular else 'Atualizando'} {caminho} (só as chaves de voz; o resto fica como está).")
        for k, v in valores.items():
            self.info(f"  {k}={'<definida>' if k.endswith('_CHAVE') and v else v}")
        if not self.simular:
            caminho.write_text("\n".join(novas) + "\n", encoding="utf-8")
        return caminho

    def testar(self, com_stt_local: bool) -> int:
        self.titulo("Teste")
        if self.simular:
            self.info("(simulação: rodaria o diagnóstico e o teste da transcrição)")
            return 0
        python = str(self.python_venv) if self.python_venv.exists() else sys.executable
        codigo = subprocess.run([python, "-m", "newclaw_ivox", "diagnostico"], cwd=self.raiz).returncode
        if codigo == 0 and com_stt_local:
            codigo = subprocess.run([python, "-m", "newclaw_ivox", "testar-stt"], cwd=self.raiz).returncode
        return codigo

    def rodar(self) -> int:
        self.saida("newclaw-ivox — instalação" + ("  [simulação: nada será executado]" if self.simular else ""))
        sistema = self.medir()
        valores = {chave: "" for chave in CHAVES_DE_VOZ}
        valores["VOZ_DISPOSITIVO"] = "auto"
        valores.update(self.perguntar_transcricao())
        com_stt_local = valores["VOZ_STT_MOTOR"] == cfg.LOCAL

        self.preparar_ambiente(sistema, com_stt_local)
        config_atual = cfg.carregar({}, self.raiz / ".env", self.raiz)
        if com_stt_local:
            valores["VOZ_STT_MODELO"] = self.escolher_modelo_stt(config_atual.modelos_dir)
            self.baixar_modelo_stt(config_atual.modelos_dir, valores["VOZ_STT_MODELO"])

        self.titulo("Síntese (texto → fala)")
        self.info("A síntese local entra na próxima versão deste instalador; por enquanto fica desligada.")

        valores["VOZ_IDIOMA"] = self.perguntar_idioma()
        self.gravar_env(valores)
        codigo = self.testar(com_stt_local)
        self.titulo("Pronto" if codigo == 0 else "Terminou com problema")
        self.info("Conferir a qualquer momento: python -m newclaw_ivox diagnostico")
        return codigo


def principal(argumentos: list[str]) -> int:
    raiz = Path(__file__).resolve().parent.parent
    instalador = Instalador(raiz, simular="--simular" in argumentos)
    try:
        return instalador.rodar()
    except Cancelado as e:
        print(f"\nInstalação interrompida: {e}. Nada além do que já foi mostrado foi feito.")
        return 3
    except RuntimeError as e:
        print(f"\nErro: {e}")
        return 1
