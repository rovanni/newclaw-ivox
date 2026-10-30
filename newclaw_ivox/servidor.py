"""Servidor do harness (Etapa 3 da ADR-030, decisões H1 e H3): um processo, uma origem.

- **Login:** `POST /entrar` repassa a senha ao NewClaw (`/api/auth/login`). O token volta para este servidor e fica aqui; o
  navegador recebe só um cookie de sessão próprio (`httpOnly`, `SameSite=Strict`, `Secure` com HTTPS).
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
import re
import secrets
import time
from dataclasses import dataclass, field

from . import configuracao as cfg

# Versão do contrato do turno que este harness sabe usar (NewClaw, status.contracts.turn).
CONTRATO_DO_TURNO = 1

COOKIE = "ivox_sessao"

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


def rota_permitida(metodo: str, caminho: str) -> bool:
    return any(metodo == m and padrao.fullmatch(caminho) for m, padrao in ROTAS_DO_CONTRATO)


def criar_app(config: cfg.Configuracao, cliente_http=None, montar_motor=None, janela_dir=None):
    """`cliente_http` (httpx.AsyncClient) e `montar_motor` são injetáveis para os testes; `janela_dir` é o build da janela
    (pasta com `index.html`), ausente quando ainda não foi gerado."""
    import httpx
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse, PlainTextResponse

    if config.newclaw_url is None:
        raise ValueError("NEWCLAW_URL não informado: o servidor do harness precisa saber onde está o NewClaw.")

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    sessoes: dict[str, Sessao] = {}
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
        return sessoes.get(request.cookies.get(COOKIE, ""))

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
        token = r.json()["token"]

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
        sessoes[sessao_id] = Sessao(token=token, idioma=idioma)
        resposta = JSONResponse({"ok": True, "contrato_do_turno": versao, "idioma": idioma})
        resposta.set_cookie(COOKIE, sessao_id, httponly=True, samesite="strict", secure=config.com_tls, path="/")
        return resposta

    @app.post("/sair")
    async def sair(request: Request):
        if not origem_valida(request):
            return erro(403, "origem não permitida")
        sessoes.pop(request.cookies.get(COOKIE, ""), None)
        resposta = JSONResponse({"ok": True})
        resposta.delete_cookie(COOKIE, path="/")
        return resposta

    @app.get("/sessao")
    async def sessao(request: Request):
        return {"entrou": sessao_de(request) is not None}

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
            sessoes.pop(request.cookies.get(COOKIE, ""), None)
            return erro(401, "o NewClaw recusou o token; entre de novo")
        return Response(
            content=r.content, status_code=r.status_code,
            headers={k: v for k, v in r.headers.items() if k.lower() in CABECALHOS_REPASSADOS},
        )

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
    app = criar_app(config, janela_dir=janela)
    print(f"[harness] {config.origem} → NewClaw em {config.newclaw_url}", flush=True)
    uvicorn.run(
        app, host=config.host, port=config.porta, log_level="warning",
        ssl_certfile=str(config.tls_cert) if config.com_tls else None,
        ssl_keyfile=str(config.tls_chave) if config.com_tls else None,
    )
    return 0
