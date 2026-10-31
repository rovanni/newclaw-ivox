"""Servidor do harness (Etapa 3 da ADR-030, decisões H1 e H3): um processo, uma origem.

- **Login:** `POST /entrar` repassa a senha ao NewClaw (`/api/auth/login`). O token volta para este servidor e fica aqui; o
  navegador recebe só um cookie de sessão próprio (`httpOnly`, `SameSite=Strict`, `Secure` com HTTPS). A senha é a do
  painel do NewClaw: não existe senha da voz. Com o painel sem senha, `GET /sessao` entra direto (não há o que pedir).
- **Sessão:** dura 30 dias, como a do painel, e sobrevive a um reinício do harness: fica num arquivo da pasta dele, com o
  resumo (sha256) do cookie como chave, nunca o cookie em si.
- **Repasse:** `/newclaw/api/<rota>` repassa ao NewClaw (`/api/<rota>`) com `Authorization: Bearer`, e só as rotas públicas
  do contrato do turno (`docs/CONTRATO_DO_TURNO.md`). O caminho espelha o do NewClaw para a janela usar o cliente público
  (`turn-client.js`) com `baseUrl: '/newclaw'`, sem cópia nem adaptação. O NewClaw vê um cliente de API comum: nenhuma regra
  nova de CORS ou CSRF no núcleo (ADR-031, regra 7).
- **Cliente do turno:** `/newclaw/turn-client.js` é o arquivo público do próprio NewClaw, buscado nele a cada pedido (uma
  fonte só; uma atualização do NewClaw chega à janela sem mexer no harness).
- **Janela:** o build da janela (`janela/dist`) é servido em `/`, com uma política de conteúdo que só aceita esta origem.
- **Sinalização WebRTC:** `/api/offer` exige sessão e origem; cada conexão monta o pipeline do motor (`motor.bot`). O motor
  não tem porta própria: só se chega a ele por aqui.
- **Versão:** depois do login, confere `status.contracts.turn` contra a versão que este harness conhece.
- **Origem:** todo pedido que muda estado precisa de `Origin` desta mesma origem (proteção contra CSRF, porque a sessão é por
  cookie).

Limitação que fica (contrato do turno): o token do NewClaw dá acesso à API inteira e não expira. Por isso ele nunca sai
deste servidor, e o repasse só abre as rotas do contrato.
"""

# Sem `from __future__ import annotations`: o FastAPI lê as anotações das rotas (`request: Request`) na hora de montar o
# app, e o Request só é importado dentro de criar_app (o pacote funciona sem FastAPI).
import asyncio
import hashlib
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import configuracao as cfg
from . import stt_local

# Versão do contrato do turno que este harness sabe usar (NewClaw, status.contracts.turn).
CONTRATO_DO_TURNO = 1

COOKIE = "ivox_sessao"
DURACAO_DA_SESSAO_S = 30 * 24 * 3600  # a mesma do painel do NewClaw
ARQUIVO_DAS_SESSOES = ".sessoes-da-janela.json"
# Ajustes do modelo que valem para o processo (D2: descarregar depois de um tempo sem uso). Ficam só nesta máquina.
ARQUIVO_DOS_AJUSTES = ".ajustes-do-modelo.json"

# (método, padrão da rota depois de /api/) — só o contrato do turno, nada de configuração, memória ou ferramentas.
ROTAS_DO_CONTRATO = (
    ("POST", re.compile(r"chat")),
    ("GET", re.compile(r"chat/active")),
    ("GET", re.compile(r"chat/outbox")),
    ("POST", re.compile(r"chat/auth-decision")),
    ("GET", re.compile(r"conversations")),
    ("GET", re.compile(r"conversations/[^/]+/messages")),
)
# /api/status fica fora: além da versão (que o próprio harness confere no login), ele traz nome da máquina, pid e memória
# do servidor do NewClaw, que a janela não precisa ver.

# Cabeçalhos da resposta do NewClaw que valem para o navegador; o resto (cookies dele, por exemplo) fica aqui.
CABECALHOS_REPASSADOS = ("content-type", "retry-after")

# A janela só carrega o que vem desta origem: nada de fonte, script ou estilo de terceiros. O áudio do motor chega por
# WebRTC (fora da CSP) e é tocado por um <audio> com MediaStream.
POLITICA_DE_CONTEUDO = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "media-src 'self' blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


@dataclass
class Sessao:
    token: str
    idioma: str | None = None
    criada_em: float = field(default_factory=time.time)
    conexoes: set[str] = field(default_factory=set)  # pc_id das conexões WebRTC desta sessão


def chave_da_sessao(sessao_id: str) -> str:
    """O arquivo das sessões guarda este resumo, não o cookie: quem lê o arquivo não consegue montar o cookie."""
    return hashlib.sha256(sessao_id.encode()).hexdigest()


def ler_sessoes(arquivo: Path | None, agora: float | None = None) -> dict[str, Sessao]:
    """Sessões gravadas e ainda válidas. Arquivo ausente ou ilegível = nenhuma (a pessoa entra de novo; nada quebra)."""
    if arquivo is None or not arquivo.is_file():
        return {}
    agora = time.time() if agora is None else agora
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    saida: dict[str, Sessao] = {}
    for chave, item in (dados.items() if isinstance(dados, dict) else []):
        if not isinstance(item, dict) or not isinstance(item.get("token"), str):
            continue
        criada = item.get("criada_em")
        if not isinstance(criada, (int, float)) or agora - criada > DURACAO_DA_SESSAO_S:
            continue
        idioma = item.get("idioma") if isinstance(item.get("idioma"), str) else None
        saida[chave] = Sessao(token=item["token"], idioma=idioma, criada_em=float(criada))
    return saida


def gravar_sessoes(arquivo: Path | None, sessoes: dict[str, Sessao]) -> None:
    if arquivo is None:
        return
    dados = {k: {"token": s.token, "idioma": s.idioma, "criada_em": s.criada_em} for k, s in sessoes.items()}
    temporario = arquivo.with_name(arquivo.name + ".novo")
    temporario.write_text(json.dumps(dados), encoding="utf-8")
    if os.name != "nt":
        os.chmod(temporario, 0o600)  # só o dono lê: o token dá acesso à API do NewClaw
    os.replace(temporario, arquivo)


def rota_permitida(metodo: str, caminho: str) -> bool:
    return any(metodo == m and padrao.fullmatch(caminho) for m, padrao in ROTAS_DO_CONTRATO)


def criar_app(config: cfg.Configuracao, cliente_http=None, montar_motor=None, janela_dir=None, arquivo_sessoes=None,
              dono_do_modelo=None, arquivo_ajustes=None, vigiar_ociosidade=False):
    """`cliente_http` (httpx.AsyncClient), `montar_motor` e `dono_do_modelo` são injetáveis para os testes; `janela_dir` é
    o build da janela (pasta com `index.html`), ausente quando ainda não foi gerado; `arquivo_sessoes` guarda as sessões
    entre reinícios (sem ele, ficam só na memória); `arquivo_ajustes` guarda os ajustes do modelo; `vigiar_ociosidade`
    liga a vigia que descarrega o modelo parado (D2), só no servidor de verdade."""
    import httpx
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse, PlainTextResponse

    if config.newclaw_url is None:
        raise ValueError("NEWCLAW_URL não informado: o servidor do harness precisa saber onde está o NewClaw.")

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    sessoes: dict[str, Sessao] = ler_sessoes(arquivo_sessoes)
    cliente = cliente_http or httpx.AsyncClient(base_url=config.newclaw_url, timeout=30.0)

    # O harness fala com o NewClaw só por token. O httpx guarda os cookies das respostas (o login do NewClaw devolve o dele)
    # e os manda nos pedidos seguintes; com cookie e sem Origin, a proteção contra CSRF do NewClaw recusa o próximo login
    # (achado da prova real, 30/10/2026: o primeiro login passava, os seguintes davam "senha recusada").
    async def esquecer_cookies(_resposta):
        cliente.cookies.clear()

    cliente.event_hooks["response"].append(esquecer_cookies)
    app.state.sessoes = sessoes  # para os testes conferirem que o token não sai daqui
    sinalizacao = {"handler": None}

    def erro(status: int, mensagem: str) -> JSONResponse:
        return JSONResponse({"erro": mensagem}, status_code=status)

    def sessao_de(request: Request) -> Sessao | None:
        s = sessoes.get(chave_da_sessao(request.cookies.get(COOKIE, "")))
        if s is not None and time.time() - s.criada_em > DURACAO_DA_SESSAO_S:
            encerrar(request)
            return None
        return s

    def encerrar(request: Request) -> None:
        if sessoes.pop(chave_da_sessao(request.cookies.get(COOKIE, "")), None) is not None:
            gravar_sessoes(arquivo_sessoes, sessoes)

    async def abrir_sessao(token: str, corpo: dict) -> JSONResponse:
        """Depois do login no NewClaw: confere o contrato, descobre o idioma e entrega o cookie."""
        # Confere se este NewClaw cumpre o contrato do turno que o harness conhece (ADR-031, regra 5).
        try:
            st = await cliente.get("/api/status", headers={"Authorization": f"Bearer {token}"})
            contratos = (st.json().get("status") or {}).get("contracts") or {}
        except (httpx.HTTPError, ValueError):
            return erro(502, "NewClaw respondeu ao login, mas não ao /api/status")
        versao = contratos.get("turn")
        if versao != CONTRATO_DO_TURNO:
            return erro(409, f"este NewClaw anuncia o contrato do turno {versao!r}; o harness usa a versão {CONTRATO_DO_TURNO}")

        # Idioma: o do .env (VOZ_IDIOMA) vence; vazio, vale o configurado no NewClaw. A rota /api/config não é do contrato
        # do turno — se ela não responder ou não trouxer um idioma aceito, a ausência continua reportada, sem adivinhar.
        idioma = config.idioma
        if idioma is None:
            try:
                cf = await cliente.get("/api/config", headers={"Authorization": f"Bearer {token}"})
                lido = (cf.json().get("config") or {}).get("language")
                idioma = lido if lido in cfg.IDIOMAS_ACEITOS else None
            except (httpx.HTTPError, ValueError):
                idioma = None

        sessao_id = secrets.token_urlsafe(32)
        sessoes[chave_da_sessao(sessao_id)] = Sessao(token=token, idioma=idioma)
        gravar_sessoes(arquivo_sessoes, sessoes)
        resposta = JSONResponse({**corpo, "contrato_do_turno": versao, "idioma": idioma})
        resposta.set_cookie(COOKIE, sessao_id, httponly=True, samesite="strict", secure=config.com_tls, path="/",
                            max_age=DURACAO_DA_SESSAO_S)
        return resposta

    async def painel_sem_senha() -> bool:
        """O NewClaw diz que o painel está sem senha. Na dúvida (sem resposta, ou a rota pedindo login), há senha."""
        try:
            r = await cliente.get("/api/auth/status")
            return r.status_code == 200 and (r.json().get("auth") or {}).get("enabled") is False
        except (httpx.HTTPError, ValueError):
            return False

    def origem_valida(request: Request) -> bool:
        return request.headers.get("origin") in config.origens_aceitas

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, chamar):
        resposta = await chamar(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Cache-Control"] = "no-store"
        resposta.headers["Content-Security-Policy"] = POLITICA_DE_CONTEUDO
        return resposta

    @app.get("/saude")
    async def saude():
        return {"ok": True}

    tem_janela = janela_dir is not None and (janela_dir / "index.html").is_file()
    if not tem_janela:
        @app.get("/")
        async def inicio():
            return PlainTextResponse(
                "newclaw-ivox: servidor no ar, mas a janela de voz ainda não foi gerada. "
                "Na pasta janela/: npm ci && npm run build"
            )

    @app.get("/newclaw/turn-client.js")
    async def cliente_do_turno():
        try:
            r = await cliente.get("/turn-client.js")
        except httpx.HTTPError as e:
            return erro(502, f"NewClaw inalcançável em {config.newclaw_url}: {type(e).__name__}")
        if r.status_code != 200:
            return erro(502, f"o NewClaw não serviu /turn-client.js (HTTP {r.status_code}); ele cumpre o contrato do turno?")
        return Response(content=r.content, media_type="text/javascript")

    @app.get("/voz")
    async def voz(request: Request):
        """O que este computador usa para ouvir e falar (cartão "Voz neste computador"). Sem chaves nem endereços."""
        s = sessao_de(request)
        if s is None:
            return erro(401, "entre primeiro (POST /entrar)")

        def servico(sv):
            if sv is None:
                return None
            return {"motor": sv.motor, "modelo": sv.modelo, "voz": sv.voz}

        return {"ouvir": servico(config.stt), "falar": servico(config.tts), "idioma": s.idioma,
                "dispositivo": config.dispositivo}

    @app.post("/entrar")
    async def entrar(request: Request):
        if not origem_valida(request):
            return erro(403, "origem não permitida")
        try:
            corpo = await request.json()
        except ValueError:
            return erro(400, "corpo JSON esperado: {\"senha\": \"...\"}")
        senha = corpo.get("senha") if isinstance(corpo, dict) else None
        if not isinstance(senha, str):
            return erro(400, "campo 'senha' ausente")
        try:
            r = await cliente.post("/api/auth/login", json={"password": senha})
        except httpx.HTTPError as e:
            return erro(502, f"NewClaw inalcançável em {config.newclaw_url}: {type(e).__name__}")
        if r.status_code == 429:
            return JSONResponse({"erro": "muitas tentativas de login"}, status_code=429,
                                headers={k: v for k, v in r.headers.items() if k.lower() == "retry-after"})
        if r.status_code != 200 or not r.json().get("token"):
            return erro(401, "senha recusada pelo NewClaw")
        return await abrir_sessao(r.json()["token"], {"ok": True})

    @app.post("/sair")
    async def sair(request: Request):
        if not origem_valida(request):
            return erro(403, "origem não permitida")
        encerrar(request)
        resposta = JSONResponse({"ok": True})
        resposta.delete_cookie(COOKIE, path="/")
        return resposta

    @app.get("/sessao")
    async def sessao(request: Request):
        sem_senha = await painel_sem_senha()
        if sessao_de(request) is not None:
            return {"entrou": True, "sem_senha": sem_senha}
        # Painel sem senha: não há o que pedir, a janela entra direto. Se depois a senha for ligada, o NewClaw passa a
        # recusar o token, a sessão acaba (repasse → 401) e a janela volta a pedir a senha.
        if not sem_senha:
            return {"entrou": False, "sem_senha": False}
        try:
            r = await cliente.post("/api/auth/login", json={"password": ""})
            token = r.json().get("token") if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            token = None
        if not token:
            return {"entrou": False, "sem_senha": True}
        resposta = await abrir_sessao(token, {"entrou": True, "sem_senha": True})
        return resposta if resposta.status_code == 200 else {"entrou": False, "sem_senha": True}

    @app.api_route("/newclaw/api/{caminho:path}", methods=["GET", "POST"])
    async def repassar(caminho: str, request: Request):
        s = sessao_de(request)
        if s is None:
            return erro(401, "entre primeiro (POST /entrar)")
        if request.method != "GET" and not origem_valida(request):
            return erro(403, "origem não permitida")
        if not rota_permitida(request.method, caminho):
            return erro(404, "rota fora do contrato do turno")
        cabecalhos = {"Authorization": f"Bearer {s.token}"}
        if "content-type" in request.headers:
            cabecalhos["Content-Type"] = request.headers["content-type"]
        try:
            r = await cliente.request(
                request.method, f"/api/{caminho}", params=request.query_params, content=await request.body(),
                headers=cabecalhos,
            )
        except httpx.HTTPError as e:
            return erro(502, f"NewClaw inalcançável: {type(e).__name__}")
        if r.status_code == 401:
            # O token deixou de valer (a senha do NewClaw mudou, por exemplo): a sessão acaba aqui também.
            encerrar(request)
            return erro(401, "o NewClaw recusou o token; entre de novo")
        return Response(
            content=r.content, status_code=r.status_code,
            headers={k: v for k, v in r.headers.items() if k.lower() in CABECALHOS_REPASSADOS},
        )

    # ─── o modelo de reconhecimento (ADR-037 do NewClaw): carregar e descarregar só por pedido da pessoa ──────────
    dono = dono_do_modelo or stt_local.dono()

    def ler_ajustes() -> dict:
        try:
            return json.loads(arquivo_ajustes.read_text(encoding="utf-8")) if arquivo_ajustes else {}
        except (OSError, ValueError):
            return {}

    def sintese() -> dict | None:
        """Onde a fala roda: os provedores que o próprio kokoro-onnx escolhe nesta instalação (a mesma função que ele usa
        ao abrir o modelo). A lista crua do onnxruntime não serve: ela traz provedores que o Kokoro não usa."""
        if config.tts is None:
            return None
        try:
            from kokoro_onnx.session import resolve_providers

            provedores = list(resolve_providers())
        except ImportError:
            provedores = None
        return {"motor": config.tts.motor, "provedores": provedores}

    def estado_do_modelo() -> dict:
        return {**dono.estado(), "sintese": sintese(), "ajustes": ler_ajustes()}

    def pedido_permitido(request: Request) -> JSONResponse | None:
        if sessao_de(request) is None:
            return erro(401, "entre primeiro (POST /entrar)")
        if request.method != "GET" and not origem_valida(request):
            return erro(403, "origem não permitida")
        return None

    @app.get("/api/modelo")
    async def modelo(request: Request):
        return pedido_permitido(request) or estado_do_modelo()

    @app.post("/api/modelo/carregar")
    async def carregar_modelo(request: Request):
        recusa = pedido_permitido(request)
        if recusa:
            return recusa
        corpo = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        try:
            await asyncio.to_thread(dono.pedir_carga, config, bool(corpo.get("na_cpu")))
        except stt_local.PedidoRecusado as e:
            return erro(409, str(e))
        except stt_local.SttIndisponivel as e:
            return erro(422, str(e))
        return estado_do_modelo()

    @app.post("/api/modelo/descarregar")
    async def descarregar_modelo(request: Request):
        recusa = pedido_permitido(request)
        if recusa:
            return recusa
        try:
            await asyncio.to_thread(dono.descarregar)
        except stt_local.PedidoRecusado as e:
            return erro(409, str(e))
        return estado_do_modelo()

    @app.post("/api/modelo/ajustes")
    async def ajustes_do_modelo(request: Request):
        recusa = pedido_permitido(request)
        if recusa:
            return recusa
        minutos = (await request.json()).get("descarregar_apos_min")
        if minutos is not None and (not isinstance(minutos, (int, float)) or isinstance(minutos, bool) or not 1 <= minutos <= 1440):
            return erro(422, "descarregar_apos_min: minutos entre 1 e 1440, ou null para desligar")
        if arquivo_ajustes is None:
            return erro(500, "este servidor não tem onde guardar os ajustes")
        arquivo_ajustes.write_text(json.dumps({**ler_ajustes(), "descarregar_apos_min": minutos}), encoding="utf-8")
        return estado_do_modelo()

    if vigiar_ociosidade:
        def vigiar():
            while True:
                time.sleep(30)
                try:
                    dono.descarregar_se_ocioso(ler_ajustes().get("descarregar_apos_min"))
                except Exception as e:  # noqa: BLE001 — a vigia não pode morrer; o motivo vai para o log
                    print(f"[harness] descarregar por ociosidade falhou: {e}", flush=True)

        threading.Thread(target=vigiar, daemon=True, name="ociosidade-do-modelo").start()

    def handler():
        if sinalizacao["handler"] is None:
            from pipecat.transports.smallwebrtc.connection import IceServer
            from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequestHandler

            servidores = [IceServer(urls=u) for u in config.ice_servidores] or None
            sinalizacao["handler"] = SmallWebRTCRequestHandler(ice_servers=servidores)
        return sinalizacao["handler"]

    @app.post("/api/offer")
    async def oferta(request: Request):
        s = sessao_de(request)
        if s is None:
            return erro(401, "entre primeiro (POST /entrar)")
        if not origem_valida(request):
            return erro(403, "origem não permitida")
        from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest

        dados = await request.json()
        pc_id = dados.get("pc_id") or dados.get("pcId")
        if pc_id and pc_id not in s.conexoes:
            return erro(403, "conexão de outra sessão")
        pedido = SmallWebRTCRequest.from_dict({k: v for k, v in dados.items() if k in ("sdp", "type", "pc_id", "restart_pc", "request_data", "requestData")})

        async def ao_conectar(conexao):
            import asyncio

            from . import motor

            argumentos = type("ArgumentosDoMotor", (), {"webrtc_connection": conexao, "idioma": s.idioma})()
            asyncio.get_running_loop().create_task((montar_motor or motor.bot)(argumentos))

        resposta = await handler().handle_web_request(request=pedido, webrtc_connection_callback=ao_conectar)
        if resposta and resposta.get("pc_id"):
            s.conexoes.add(resposta["pc_id"])
        return resposta

    @app.patch("/api/offer")
    async def candidatos(request: Request):
        s = sessao_de(request)
        if s is None:
            return erro(401, "entre primeiro (POST /entrar)")
        if not origem_valida(request):
            return erro(403, "origem não permitida")
        from pipecat.transports.smallwebrtc.request_handler import IceCandidate, SmallWebRTCPatchRequest

        dados = await request.json()
        pc_id = dados.get("pc_id") or dados.get("pcId")
        if pc_id not in s.conexoes:
            return erro(403, "conexão de outra sessão")
        lista = [
            IceCandidate(candidate=c["candidate"], sdp_mid=c.get("sdp_mid") or c.get("sdpMid"),
                         sdp_mline_index=c.get("sdp_mline_index", c.get("sdpMLineIndex")))
            for c in dados.get("candidates", [])
        ]
        await handler().handle_patch_request(SmallWebRTCPatchRequest(pc_id=pc_id, candidates=lista))
        return {"ok": True}

    if tem_janela:
        # Por último: as rotas acima têm prioridade sobre os arquivos da janela.
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(janela_dir), html=True), name="janela")

    return app


def principal(argumentos: list[str]) -> int:
    """`servidor [--eco]` — sobe o harness em HARNESS_HOST:HARNESS_PORTA (padrão 127.0.0.1:7860)."""
    from .comandos import RAIZ

    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    erros = [a for a in config.achados if a.nivel == cfg.ERRO]
    if erros or config.newclaw_url is None:
        for a in erros:
            print(f"[ERRO] {a.variavel}: {a.mensagem}")
        if config.newclaw_url is None:
            print("[ERRO] NEWCLAW_URL: informe o endereço do NewClaw (ex.: http://localhost:3090).")
        return 1
    if "--eco" in argumentos:
        from . import motor

        motor._EM_ECO = True
    import uvicorn

    janela = RAIZ / "janela" / "dist"
    if not (janela / "index.html").is_file():
        print("[harness] janela de voz não gerada: na pasta janela/, rode  npm ci && npm run build", flush=True)
    app = criar_app(config, janela_dir=janela, arquivo_sessoes=RAIZ / ARQUIVO_DAS_SESSOES,
                     arquivo_ajustes=RAIZ / ARQUIVO_DOS_AJUSTES, vigiar_ociosidade=True)
    print(f"[harness] {config.origem} → NewClaw em {config.newclaw_url}", flush=True)
    uvicorn.run(
        app, host=config.host, port=config.porta, log_level="warning",
        ssl_certfile=str(config.tls_cert) if config.com_tls else None,
        ssl_keyfile=str(config.tls_chave) if config.com_tls else None,
    )
    return 0
