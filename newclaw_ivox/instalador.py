"""Instalador do newclaw-ivox: mede a máquina, pergunta o que a pessoa quer, instala, baixa e testa.

Roda com o Python do sistema e usa só a biblioteca padrão; o que precisa do Pipecat roda depois, pelo Python do `.venv`
recém-criado. Segue os passos do instalador do NewClaw (medir o sistema → instalar → baixar modelo → configurar → testar →
resumo), num arquivo só para Windows, Linux e macOS.

Regras:
- nada é escolhido pela pessoa sem ela ver: modelo e idioma não têm resposta padrão;
- antes de instalar ou baixar, mostra o que vai fazer e pergunta;
- o `.env` é atualizado só nas chaves de voz, e o resto dele fica como estava;
- `--simular` mostra os comandos e não executa nada.

Chamado pelo painel do NewClaw (ADR-030, Etapa 5 — instalador genérico de integrações):
- `--opcoes --json`: as escolhas que o painel mostra (sem precisar de nada instalado);
- `--licencas --json --transcricao X --sintese Y`: as peças de terceiros dessas escolhas;
- `--sem-perguntas --aceito-licencas --transcricao X --sintese Y --modelo M --idioma I [--newclaw-url U]`: instala sem
  perguntar, com o andamento em linhas JSON (`{"texto": ...}`, e no fim `{"fim": true, "codigo": N}`). O aceite das
  licenças é o clique da pessoa no painel, que só então passa `--aceito-licencas`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import configuracao as cfg
from . import dispositivo as disp
from . import licencas as lic

PYTHON_MINIMO = (3, 10)
ARQUIVO_MISTURAS = "vozes-misturadas.json"
IDIOMAS = (("pt-BR", "Português (Brasil)"), ("en-US", "English (US)"), ("es-ES", "Español"))
DESLIGADA = "desligada"  # valor das escolhas sem perguntas para "transcrição/síntese desligada"
CHAVES_DE_VOZ = (
    "VOZ_STT_MOTOR", "VOZ_STT_MODELO", "VOZ_STT_URL", "VOZ_STT_CHAVE",
    "VOZ_TTS_MOTOR", "VOZ_TTS_MODELO", "VOZ_TTS_VOZ", "VOZ_TTS_URL", "VOZ_TTS_CHAVE",
    "VOZ_IDIOMA", "VOZ_DISPOSITIVO",
)


class Cancelado(Exception):
    pass


class Instalador:
    def __init__(self, raiz: Path, simular: bool = False, entrada=input, saida=None, respostas: dict | None = None):
        self.raiz = raiz
        self.simular = simular
        self.entrada = entrada
        # flush: os comandos filhos escrevem direto no terminal; sem ele, as mensagens daqui saem fora de ordem.
        self.saida = saida or (lambda texto: print(texto, flush=True))
        # Sem perguntas (painel do NewClaw): as escolhas chegam prontas; os "Instalar?/Baixar?" valem pelo clique da pessoa
        # no painel, e o aceite das licenças tem de vir explícito em `aceito`.
        self.respostas = respostas

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
        if self.respostas is not None:
            self.info(f"{texto} sim (confirmado no painel)")
            return True
        while True:
            resposta = self.perguntar(f"{texto} [s/n]").lower()
            if resposta in ("s", "sim"):
                return True
            if resposta in ("n", "nao", "não"):
                return False
            self.info("Responda s ou n.")

    def executar(self, comando: list[str], pasta: Path | None = None) -> None:
        self.info("$ " + " ".join(comando))
        if self.simular:
            return
        resultado = subprocess.run(comando, cwd=pasta or self.raiz)
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

    def resposta(self, chave: str, aceitas: tuple[str, ...]) -> str:
        valor = (self.respostas or {}).get(chave)
        if valor not in aceitas:
            raise RuntimeError(f"--{chave} precisa ser um de: {', '.join(aceitas)} (veio {valor!r}).")
        return valor

    def perguntar_transcricao(self) -> dict[str, str]:
        self.titulo("Transcrição (fala → texto)")
        if self.respostas is not None:
            motor = self.resposta("transcricao", (cfg.LOCAL, DESLIGADA))
            self.info(f"Escolhida no painel: {motor}")
            return {"VOZ_STT_MOTOR": cfg.LOCAL if motor == cfg.LOCAL else ""}
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

    def perguntar_sintese(self) -> dict[str, str]:
        self.titulo("Síntese (texto → fala)")
        if self.respostas is not None:
            motor = self.resposta("sintese", (cfg.LOCAL, DESLIGADA))
            self.info(f"Escolhida no painel: {motor}")
            return {"VOZ_TTS_MOTOR": cfg.LOCAL if motor == cfg.LOCAL else ""}
        motor = self.escolher("Onde sintetizar a fala?", [
            (cfg.LOCAL, "Nesta máquina (Kokoro local; não depende de outro computador)"),
            (cfg.URL, "Num servidor que eu já tenho (compatível com a API OpenAI)"),
            ("", "Desligada (respostas só em texto)"),
        ])
        if motor == cfg.URL:
            return {
                "VOZ_TTS_MOTOR": cfg.URL,
                "VOZ_TTS_URL": self.perguntar("Endereço do servidor (ex.: http://servidor:porta/v1):"),
                "VOZ_TTS_MODELO": self.perguntar("Modelo, como o servidor o chama:"),
                "VOZ_TTS_VOZ": self.perguntar("Voz, como o servidor a chama:"),
                "VOZ_TTS_CHAVE": self.perguntar("Chave (Enter se o servidor não pede):"),
            }
        if motor == "":
            return {"VOZ_TTS_MOTOR": ""}
        return {"VOZ_TTS_MOTOR": cfg.LOCAL}

    def grupos(self, sistema: disp.Sistema, com_stt_local: bool, com_tts_local: bool) -> set[str]:
        """Os grupos de peças desta instalação — a mesma conta que decide os extras do pip em preparar_ambiente."""
        grupos = set()
        if com_stt_local:
            grupos.add(lic.STT_LOCAL)
            if sistema.gpus_nvidia and sys.platform != "darwin":
                grupos.add(lic.CUDA)
        if com_tts_local:
            grupos.add(lic.TTS_LOCAL)
        return grupos

    def aceitar_licencas(self, grupos: set[str]) -> None:
        """Mostra cada peça de terceiros desta instalação com a licença e o link; só segue se a pessoa digitar 'aceito'."""
        self.titulo("Licenças de terceiros")
        lista = lic.carregar_lista(self.raiz)
        itens = lic.itens_para(lista, grupos)
        registro = lic.ler_registro(self.raiz)
        if lic.ja_aceitas(registro, lista, itens):
            self.info(f"Já aceitas em {registro['aceito_em']} (lista versão {lista.versao}, as mesmas peças). Seguindo.")
            return
        if self.respostas is not None:
            # O painel mostrou a mesma lista (`--licencas --json`) e a pessoa marcou "Li e aceito"; sem isso, não instala.
            if not self.respostas.get("aceito"):
                raise Cancelado("as licenças de terceiros não foram aceitas no painel, então nada foi instalado")
            for item in itens:
                self.info(f"{item.nome} — {item.licenca}")
            if not self.simular:
                caminho = lic.gravar_registro(self.raiz, lista, itens, origem="painel do NewClaw")
                self.info(f"Aceite feito no painel, guardado em {caminho}.")
            return
        self.info("O newclaw-ivox usa estas peças de terceiros. Cada uma tem a licença do seu autor:")
        for i, item in enumerate(itens, 1):
            self.saida("")
            self.info(f"{i}. {item.nome} — {item.papel}")
            self.info(f"   Licença: {item.licenca}")
            self.info(f"   {item.link}")
            if item.atencao:
                self.info(f"   ATENÇÃO: {item.atencao}")
        self.saida("")
        self.info("Elas são baixadas das fontes oficiais (PyPI, Hugging Face, GitHub) para esta máquina; este repositório")
        self.info("não as redistribui. Ao aceitar, você declara que leu e concorda em usar cada uma conforme a sua licença.")
        resposta = self.perguntar(f"Para aceitar, digite '{lic.PALAVRA_DE_ACEITE}' (qualquer outra resposta cancela):")
        if not lic.resposta_aceita(resposta):
            raise Cancelado("as licenças de terceiros não foram aceitas, então nada foi instalado")
        if self.simular:
            self.info(f"(simulação: o aceite seria guardado em {self.raiz / lic.ARQUIVO_DO_REGISTRO})")
            return
        caminho = lic.gravar_registro(self.raiz, lista, itens)
        self.info(f"Aceite guardado em {caminho}.")

    def preparar_ambiente(self, sistema: disp.Sistema, com_stt_local: bool, com_tts_local: bool = False) -> None:
        self.titulo("Ambiente Python do motor de voz")
        extras = ["motor"]
        if com_stt_local:
            extras.append("stt-local")
            if sistema.gpus_nvidia and sys.platform != "darwin":
                extras.append("cuda")
        if com_tts_local:
            extras.append("tts-local")
        self.info(f"Pasta: {self.venv}")
        self.info(f"Pacotes: newclaw-ivox[{','.join(extras)}], baixados do PyPI para dentro dessa pasta.")
        if "cuda" in extras:
            self.info("Inclui as bibliotecas CUDA da NVIDIA (~2 GB no Windows), porque uma GPU NVIDIA foi encontrada.")
        self.info("Lista completa dos pacotes e licenças instalados: docs/terceiros/.")
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
            return (self.respostas or {}).get("modelo") or self.perguntar("Nome do modelo:")
        resultado = self.rodar_no_venv("modelos", "--json", "--pasta", str(modelos_dir))
        if resultado.returncode != 0:
            raise RuntimeError("Não consegui listar os modelos: " + (resultado.stderr.strip().splitlines() or ["sem detalhe"])[-1])
        lista = json.loads(resultado.stdout)
        if self.respostas is not None:
            # O painel escolheu pela foto da lista; aqui confere contra a lista ao vivo do faster-whisper instalado.
            nome = (self.respostas or {}).get("modelo")
            dados = next((m for m in lista if m["nome"] == nome), None)
            if dados is None:
                raise RuntimeError(f"O modelo {nome!r} não existe no faster-whisper instalado; modelos: "
                                   + ", ".join(m["nome"] for m in lista))
            self.info(f"Escolhido no painel: {nome} ({dados['tamanho']}, licença: {dados.get('licenca') or 'não declarada'})")
            return nome
        self.info("Tamanho e licença lidos agora no Hugging Face. Os maiores erram menos e pesam mais; '.en' só entende inglês.")
        opcoes = [
            (m["nome"], f"{m['nome']:<20} {m['tamanho']:>12}   licença: {m.get('licenca') or 'não declarada no cartão'}"
                        f"{'   (já baixado)' if m['instalado'] else ''}")
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

    def baixar_kokoro(self, modelos_dir: Path) -> None:
        self.titulo("Modelo do Kokoro")
        if self.simular:
            self.info(f"(simulação: baixaria o modelo e as vozes do Kokoro para {modelos_dir})")
            return
        resultado = self.rodar_no_venv("modelos", "--kokoro", "--json", "--pasta", str(modelos_dir))
        if resultado.returncode != 0:
            raise RuntimeError("Não consegui consultar o Kokoro: " + (resultado.stderr.strip().splitlines() or ["sem detalhe"])[-1])
        dados = json.loads(resultado.stdout)
        if dados["instalado"]:
            self.info(f"O Kokoro já está em {dados['pasta']}.")
            return
        if not self.confirmar(f"Baixar o modelo e as vozes do Kokoro ({dados['tamanho']}) do GitHub para {dados['pasta']}?"):
            raise Cancelado("download recusado")
        self.executar([str(self.python_venv), "-m", "newclaw_ivox", "modelos", "--kokoro", "--baixar", "--pasta", str(modelos_dir)])

    def mostrar_vozes(self, modelos_dir: Path) -> None:
        self.titulo("Vozes")
        if self.simular:
            self.info("(simulação: contaria as vozes do arquivo baixado)")
            return
        resultado = self.rodar_no_venv("modelos", "--vozes", "--json", "--pasta", str(modelos_dir))
        if resultado.returncode != 0:
            raise RuntimeError("Não consegui ler as vozes: " + (resultado.stderr.strip().splitlines() or ["sem detalhe"])[-1])
        vozes = json.loads(resultado.stdout)
        misturadas = sum(1 for v in vozes if "mistura" in v)
        self.info(f"{len(vozes) - misturadas} vozes do Kokoro instaladas (num arquivo só) e {misturadas} vozes misturadas"
                  f" ({ARQUIVO_MISTURAS}).")
        self.info("A voz é escolhida na interface e pode ser trocada a qualquer momento; para ouvir uma:"
                  " python -m newclaw_ivox testar-tts --voz <nome>")

    def perguntar_idioma(self) -> str:
        self.titulo("Idioma")
        if self.respostas is not None:
            idioma = self.resposta("idioma", tuple(c for c, _ in IDIOMAS))
            self.info(f"Escolhido no painel: {idioma}")
            return idioma
        return self.escolher("Em que idioma você vai falar?", list(IDIOMAS))

    def construir_janela(self) -> None:
        """Gera a janela de voz (janela/dist), que o harness serve em /. Precisa do Node.js (o do NewClaw serve)."""
        self.titulo("Janela de voz")
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("Node.js (npm) não encontrado: ele é preciso para gerar a janela de voz.")
        pasta = self.raiz / "janela"
        self.info(f"Instala as dependências fixadas (package-lock.json) e gera a janela em {pasta / 'dist'}.")
        if not self.confirmar("Gerar a janela agora?"):
            raise Cancelado("geração da janela recusada")
        self.executar([npm, "ci", "--no-fund", "--no-audit"], pasta)
        self.executar([npm, "run", "build"], pasta)

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

    def testar(self, com_stt_local: bool, com_tts_local: bool = False) -> int:
        self.titulo("Teste")
        if self.simular:
            self.info("(simulação: rodaria o diagnóstico e os testes da transcrição e da síntese)")
            return 0
        python = str(self.python_venv) if self.python_venv.exists() else sys.executable
        codigo = subprocess.run([python, "-m", "newclaw_ivox", "diagnostico"], cwd=self.raiz).returncode
        if codigo == 0 and com_stt_local:
            codigo = subprocess.run([python, "-m", "newclaw_ivox", "testar-stt"], cwd=self.raiz).returncode
        if codigo == 0 and com_tts_local:
            codigo = subprocess.run([python, "-m", "newclaw_ivox", "testar-tts"], cwd=self.raiz).returncode
        return codigo

    def rodar(self) -> int:
        self.saida("newclaw-ivox — instalação" + ("  [simulação: nada será executado]" if self.simular else ""))
        sistema = self.medir()
        valores = {chave: "" for chave in CHAVES_DE_VOZ}
        valores["VOZ_DISPOSITIVO"] = "auto"
        valores.update(self.perguntar_transcricao())
        valores.update(self.perguntar_sintese())
        com_stt_local = valores["VOZ_STT_MOTOR"] == cfg.LOCAL
        com_tts_local = valores["VOZ_TTS_MOTOR"] == cfg.LOCAL

        # Antes de instalar ou baixar qualquer coisa: a pessoa vê cada peça de terceiros e aceita (ou nada acontece).
        self.aceitar_licencas(self.grupos(sistema, com_stt_local, com_tts_local))
        self.preparar_ambiente(sistema, com_stt_local, com_tts_local)
        config_atual = cfg.carregar({}, self.raiz / ".env", self.raiz)
        if com_stt_local:
            valores["VOZ_STT_MODELO"] = self.escolher_modelo_stt(config_atual.modelos_dir)
            self.baixar_modelo_stt(config_atual.modelos_dir, valores["VOZ_STT_MODELO"])
        if com_tts_local:
            self.baixar_kokoro(config_atual.modelos_dir)
            self.mostrar_vozes(config_atual.modelos_dir)
            # A voz é escolhida na interface; a que já estiver no .env (VOZ_TTS_VOZ) fica como está.
            valores.pop("VOZ_TTS_VOZ")

        valores["VOZ_IDIOMA"] = self.perguntar_idioma()
        url = (self.respostas or {}).get("newclaw_url")
        if url:
            valores["NEWCLAW_URL"] = url  # o painel sabe o próprio endereço: a pessoa não digita nada
        self.gravar_env(valores)
        self.construir_janela()
        codigo = self.testar(com_stt_local, com_tts_local)
        self.titulo("Pronto" if codigo == 0 else "Terminou com problema")
        self.info("Conferir a qualquer momento: python -m newclaw_ivox diagnostico")
        return codigo


def _valor(argumentos: list[str], nome: str) -> str | None:
    if nome in argumentos:
        i = argumentos.index(nome)
        if i + 1 < len(argumentos):
            return argumentos[i + 1]
    return None


def opcoes(raiz: Path) -> list[dict]:
    """As escolhas que o painel mostra, sem nada instalado. Os modelos vêm da foto gravada (tamanho e licença medidos)."""
    from . import modelos

    foto = modelos.ler_lista_gravada(raiz) or {"modelos": []}
    local_ou_nao = lambda rotulo: [  # noqa: E731
        {"valor": cfg.LOCAL, "rotulo": rotulo}, {"valor": DESLIGADA, "rotulo": "Desligada"},
    ]
    return [
        {"id": "transcricao", "rotulo": "Ouvir (fala → texto)", "opcoes": local_ou_nao("Nesta máquina (Whisper)")},
        {"id": "sintese", "rotulo": "Falar (texto → fala)", "opcoes": local_ou_nao("Nesta máquina (Kokoro)")},
        {
            "id": "modelo", "rotulo": "Modelo do Whisper", "visivel_se": {"transcricao": cfg.LOCAL},
            "nota": f"Tamanho e licença medidos em {foto.get('gerado_em', '?')} (faster-whisper {foto.get('faster_whisper', '?')}). "
                    "Os maiores erram menos e pesam mais; '.en' só entende inglês.",
            "opcoes": [
                {"valor": m["nome"], "rotulo": m["nome"], "detalhe": f"{m['tamanho']} · licença {m.get('licenca') or 'não declarada'}"}
                for m in foto["modelos"]
            ],
        },
        {"id": "idioma", "rotulo": "Idioma em que você vai falar", "opcoes": [{"valor": c, "rotulo": r} for c, r in IDIOMAS]},
    ]


def licencas_json(raiz: Path, argumentos: list[str]) -> dict:
    """As peças de terceiros das escolhas dadas, com a mesma conta do instalador (inclui CUDA só com GPU NVIDIA)."""
    respostas = {"transcricao": _valor(argumentos, "--transcricao"), "sintese": _valor(argumentos, "--sintese")}
    sistema = disp.medir_sistema(raiz)
    inst = Instalador(raiz, respostas=respostas)
    grupos = inst.grupos(sistema, respostas["transcricao"] == cfg.LOCAL, respostas["sintese"] == cfg.LOCAL)
    lista = lic.carregar_lista(raiz)
    itens = lic.itens_para(lista, grupos)
    campos = ("id", "nome", "papel", "licenca", "link", "atencao")
    return {"versao": lista.versao, "itens": [{c: getattr(i, c) for c in campos} for i in itens]}


def principal(argumentos: list[str]) -> int:
    raiz = Path(__file__).resolve().parent.parent
    if "--opcoes" in argumentos:
        print(json.dumps(opcoes(raiz), ensure_ascii=False))
        return 0
    if "--licencas" in argumentos:
        print(json.dumps(licencas_json(raiz, argumentos), ensure_ascii=False))
        return 0

    sem_perguntas = "--sem-perguntas" in argumentos
    respostas = None
    saida = None
    if sem_perguntas:
        respostas = {
            chave: _valor(argumentos, f"--{chave.replace('_', '-')}")
            for chave in ("transcricao", "sintese", "modelo", "idioma", "newclaw_url")
        }
        respostas["aceito"] = "--aceito-licencas" in argumentos

        def saida(texto: str) -> None:
            if texto.strip():  # o painel mostra linhas; o recuo e as linhas em branco são da conversa no terminal
                print(json.dumps({"texto": texto.strip()}, ensure_ascii=False), flush=True)

    instalador = Instalador(raiz, simular="--simular" in argumentos, saida=saida, respostas=respostas)
    codigo = 0
    try:
        codigo = instalador.rodar()
    except Cancelado as e:
        instalador.saida(f"Instalação interrompida: {e}. Nada além do que já foi mostrado foi feito.")
        codigo = 3
    except RuntimeError as e:
        instalador.saida(f"Erro: {e}")
        codigo = 1
    if sem_perguntas:
        print(json.dumps({"fim": True, "codigo": codigo}), flush=True)
    return codigo
