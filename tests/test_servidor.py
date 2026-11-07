"""Testes de segurança do servidor do harness (Etapa 3), com um NewClaw falso no lugar do de verdade.

Critérios da ADR-030: sem login → 401; outra origem → recusada; motor de voz inalcançável sem sessão. E o token do NewClaw
nunca chega ao navegador.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TEM_FASTAPI = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None

ORIGEM = "http://localhost:7860"
TOKEN = "token-secreto-do-newclaw"


class NewClawFalso:
    def __init__(self, senha="certa", contrato=1, idioma="pt-BR", sem_senha=False):
        self.senha, self.contrato, self.idioma, self.sem_senha = senha, contrato, idioma, sem_senha
        self.pedidos = []
        self.token_valido = True

    def __call__(self, pedido):
        import httpx

        self.pedidos.append(pedido)
        caminho = pedido.url.path
        if caminho == "/turn-client.js":  # arquivo público do NewClaw, sem autenticação
            return httpx.Response(200, text="export const TURN_CONTRACT_VERSION = 1;",
                                  headers={"content-type": "application/javascript", "set-cookie": "x=vazaria"})
        if caminho == "/api/auth/status" and self.sem_senha:  # com senha, a rota pede login (cai no 401 abaixo)
            return httpx.Response(200, json={"success": True, "auth": {"enabled": False, "hasPassword": False}})
        if caminho == "/api/auth/login":
            # Como o NewClaw de verdade: pedido com o cookie dele e sem Origin é recusado (proteção contra CSRF).
            if "newclaw_session" in pedido.headers.get("cookie", "") and "origin" not in pedido.headers:
                return httpx.Response(403, json={"error": "Forbidden: invalid origin"})
            if self.sem_senha:  # o NewClaw sem senha aceita qualquer login
                return httpx.Response(200, json={"success": True, "token": TOKEN})
            if json.loads(pedido.content).get("password") == self.senha:
                return httpx.Response(200, json={"success": True, "token": TOKEN},
                                      headers={"set-cookie": "newclaw_session=sessao-do-painel; Path=/; HttpOnly"})
            return httpx.Response(401, json={"error": "Invalid password"})
        if pedido.headers.get("authorization") != f"Bearer {TOKEN}" or not self.token_valido:
            return httpx.Response(401, json={"error": "Unauthorized"})
        if caminho == "/api/status":
            return httpx.Response(200, json={"success": True, "status": {"contracts": {"turn": self.contrato}, "hostname": "segredo"}})
        if caminho == "/api/config":
            return httpx.Response(200, json={"success": True, "config": {"language": self.idioma}})
        if caminho == "/api/chat":
            return httpx.Response(202, json={"success": True, "turnId": "t1", "sessionId": "s1"})
        if caminho == "/api/chat/active":
            return httpx.Response(200, json={"success": True, "active": [], "pendingAuth": [], "pending": False},
                                  headers={"set-cookie": "newclaw_session=vazaria", "x-interno": "1"})
        return httpx.Response(404, json={"error": "nao existe"})


@unittest.skipUnless(TEM_FASTAPI, "FastAPI/httpx não instalados neste Python (vêm com o extra 'motor')")
class TestServidor(unittest.TestCase):
    def montar(self, ambiente=None, arquivo_sessoes=None, dono=None, arquivo_ajustes=None, **kw):
        import httpx
        from fastapi.testclient import TestClient

        from newclaw_ivox import configuracao as cfg
        from newclaw_ivox.servidor import criar_app

        self.newclaw = NewClawFalso(**kw)
        config = cfg.carregar({"NEWCLAW_URL": "http://newclaw.falso:3090", **(ambiente or {})})
        cliente = httpx.AsyncClient(base_url=config.newclaw_url, transport=httpx.MockTransport(self.newclaw))
        self.motores = []

        async def motor_falso(argumentos):
            self.motores.append(argumentos)

        self.app = criar_app(config, cliente_http=cliente, montar_motor=motor_falso, arquivo_sessoes=arquivo_sessoes,
                             dono_do_modelo=dono, arquivo_ajustes=arquivo_ajustes)
        return TestClient(self.app, base_url="http://localhost:7860")

    # ─── sessão: uma senha só (a do painel), 30 dias, sem tela quando o painel não tem senha ─────────────────

    def test_painel_sem_senha_entra_direto(self):
        c = self.montar(sem_senha=True)
        r = c.get("/sessao")
        self.assertEqual(r.json()["entrou"], True)
        self.assertTrue(r.json()["sem_senha"])
        self.assertNotIn(TOKEN, r.text)
        self.assertIn("max-age=2592000", r.headers["set-cookie"].lower())
        self.assertEqual(c.get("/voz").status_code, 200)

    def test_painel_com_senha_nao_entra_sozinho(self):
        c = self.montar()
        self.assertEqual(c.get("/sessao").json(), {"entrou": False, "sem_senha": False})
        self.assertFalse(any(p.url.path == "/api/auth/login" for p in self.newclaw.pedidos))  # nem gasta tentativa

    def test_sessao_sobrevive_ao_reinicio_e_o_arquivo_nao_tem_o_cookie(self):
        arquivo = Path(tempfile.mkdtemp()) / ".sessoes-da-janela.json"
        c = self.montar(arquivo_sessoes=arquivo)
        cookie = self.entrar(c).cookies.get("ivox_sessao")
        self.assertNotIn(cookie, arquivo.read_text(encoding="utf-8"))
        c2 = self.montar(arquivo_sessoes=arquivo)  # outro processo, mesmo arquivo
        c2.cookies.set("ivox_sessao", cookie)
        self.assertEqual(c2.get("/sessao").json(), {"entrou": True, "sem_senha": False})
        c2.post("/sair", headers={"Origin": ORIGEM})
        self.assertEqual(json.loads(arquivo.read_text(encoding="utf-8")), {})

    def test_sessao_vencida_nao_volta(self):
        from newclaw_ivox import servidor

        arquivo = Path(tempfile.mkdtemp()) / ".sessoes-da-janela.json"
        arquivo.write_text(json.dumps({"x": {"token": TOKEN, "idioma": None, "criada_em": 0}}), encoding="utf-8")
        self.assertEqual(servidor.ler_sessoes(arquivo), {})
        arquivo.write_text("{quebrado", encoding="utf-8")
        self.assertEqual(servidor.ler_sessoes(arquivo), {})

    def entrar(self, c, senha="certa", origem=ORIGEM):
        return c.post("/entrar", json={"senha": senha}, headers={"Origin": origem})

    # ─── o modelo de reconhecimento (ADR-037): só por pedido, com sessão e origem ────────────────────────────

    def dono_falso(self):
        class Dono:
            def __init__(self):
                self.pedidos, self.descargas, self.estado_atual = [], 0, "descarregado"

            def estado(self):
                return {"estado": self.estado_atual, "em_uso": 0}

            def pedir_carga(self, config, na_cpu=False):
                self.pedidos.append(na_cpu)
                self.estado_atual = "carregando"

            def descarregar(self):
                self.descargas += 1
                self.estado_atual = "descarregado"

        return Dono()

    def test_modelo_pede_sessao_e_origem(self):
        dono = self.dono_falso()
        c = self.montar(dono=dono)
        self.assertEqual(c.get("/api/modelo").status_code, 401)
        self.assertEqual(c.post("/api/modelo/carregar", headers={"Origin": ORIGEM}).status_code, 401)
        self.entrar(c)
        self.assertEqual(c.post("/api/modelo/carregar", headers={"Origin": "http://outro.site"}).status_code, 403)
        self.assertEqual(c.post("/api/modelo/descarregar").status_code, 403, "sem Origin também é recusado")
        self.assertEqual(dono.pedidos, [], "nada carregou sem sessão e origem certas")

    def test_entrar_e_conectar_nao_carregam_o_modelo(self):
        dono = self.dono_falso()
        c = self.montar(dono=dono)
        self.entrar(c)
        self.assertEqual(c.get("/api/modelo").json()["estado"], "descarregado")
        self.assertEqual(dono.pedidos, [])

    def test_carregar_na_cpu_e_descarregar(self):
        dono = self.dono_falso()
        c = self.montar(dono=dono)
        self.entrar(c)
        r = c.post("/api/modelo/carregar", json={"na_cpu": True}, headers={"Origin": ORIGEM})
        self.assertEqual((r.status_code, r.json()["estado"], dono.pedidos), (200, "carregando", [True]))
        r = c.post("/api/modelo/descarregar", headers={"Origin": ORIGEM})
        self.assertEqual((r.json()["estado"], dono.descargas), ("descarregado", 1))

    def test_ajustes_da_ociosidade(self):
        arquivo = Path(tempfile.mkdtemp()) / ".ajustes-do-modelo.json"
        c = self.montar(dono=self.dono_falso(), arquivo_ajustes=arquivo)
        self.entrar(c)
        self.assertEqual(c.get("/api/modelo").json()["ajustes"], {}, "desligado por padrão")
        for ruim in (0, 5000, "10", True):
            with self.subTest(ruim=ruim):
                r = c.post("/api/modelo/ajustes", json={"descarregar_apos_min": ruim}, headers={"Origin": ORIGEM})
                self.assertEqual(r.status_code, 422)
        r = c.post("/api/modelo/ajustes", json={"descarregar_apos_min": 15}, headers={"Origin": ORIGEM})
        self.assertEqual(r.json()["ajustes"], {"descarregar_apos_min": 15})
        r = c.post("/api/modelo/ajustes", json={"descarregar_apos_min": None}, headers={"Origin": ORIGEM})
        self.assertEqual(r.json()["ajustes"], {"descarregar_apos_min": None})

    # ─── login ───────────────────────────────────────────────────────────────

    def test_login_guarda_o_token_so_no_servidor(self):
        c = self.montar()
        r = self.entrar(c)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(TOKEN, r.text)
        cookie = r.headers["set-cookie"]
        self.assertNotIn(TOKEN, cookie)
        for atributo in ("HttpOnly", "SameSite=strict", "Path=/"):
            self.assertIn(atributo.lower(), cookie.lower())
        self.assertNotIn("secure", cookie.lower())  # sem HTTPS, o navegador não mandaria um cookie Secure
        self.assertEqual([s.token for s in self.app.state.sessoes.values()], [TOKEN])

    def test_entrar_de_novo_funciona_o_harness_nao_guarda_o_cookie_do_newclaw(self):
        # Achado da prova real (30/10/2026): o primeiro login passava e os seguintes davam "senha recusada".
        c = self.montar()
        for vez in range(3):
            with self.subTest(vez=vez):
                self.assertEqual(self.entrar(c).status_code, 200)
        self.assertEqual(len(self.app.state.sessoes), 3)

    def test_senha_errada(self):
        c = self.montar()
        self.assertEqual(self.entrar(c, senha="errada").status_code, 401)
        self.assertEqual(self.app.state.sessoes, {})

    def test_login_de_outra_origem_e_recusado_sem_chamar_o_newclaw(self):
        c = self.montar()
        for origem in ("http://atacante.example", "null", ""):
            with self.subTest(origem=origem):
                r = c.post("/entrar", json={"senha": "certa"}, headers={"Origin": origem} if origem else {})
                self.assertEqual(r.status_code, 403)
        self.assertEqual(self.newclaw.pedidos, [])

    def test_contrato_abaixo_do_minimo_ou_invalido_e_recusado(self):
        for contrato in (0, None, "2", 1.5, True):
            with self.subTest(contrato=contrato):
                c = self.montar(contrato=contrato)
                r = self.entrar(c)
                self.assertEqual(r.status_code, 409)
                self.assertIn("contrato do turno", r.json()["erro"])
                self.assertEqual(self.app.state.sessoes, {})

    def test_contrato_de_versao_maior_e_aceito(self):
        # O NewClaw da versão 2 (ADR-033) recusava o login com o harness exigindo a versão exata 1 (achado de 07/11/2026).
        for contrato in (1, 2, 3):
            with self.subTest(contrato=contrato):
                c = self.montar(contrato=contrato)
                r = self.entrar(c)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["contrato_do_turno"], contrato)

    def test_idioma_vem_do_newclaw_quando_o_env_nao_diz(self):
        c = self.montar()
        self.assertEqual(self.entrar(c).json()["idioma"], "pt-BR")
        c = self.montar(ambiente={"VOZ_IDIOMA": "en-US"})
        self.assertEqual(self.entrar(c).json()["idioma"], "en-US")
        self.assertNotIn("/api/config", [p.url.path for p in self.newclaw.pedidos])
        c = self.montar(idioma="fr-FR")  # idioma que o harness não aceita: ausência, nunca adivinhado
        self.assertIsNone(self.entrar(c).json()["idioma"])

    def test_sair(self):
        c = self.montar()
        self.entrar(c)
        self.assertEqual(c.post("/sair", headers={"Origin": ORIGEM}).status_code, 200)
        self.assertEqual(self.app.state.sessoes, {})
        self.assertEqual(c.get("/newclaw/api/chat/active").status_code, 401)

    # ─── repasse ─────────────────────────────────────────────────────────────

    def test_sem_login_401_em_tudo_que_alcanca_o_newclaw_ou_o_motor(self):
        c = self.montar()
        self.assertEqual(c.get("/newclaw/api/chat/active").status_code, 401)
        self.assertEqual(c.post("/newclaw/api/chat", json={"message": "oi"}, headers={"Origin": ORIGEM}).status_code, 401)
        self.assertEqual(c.post("/api/offer", json={"sdp": "x", "type": "offer"}, headers={"Origin": ORIGEM}).status_code, 401)
        self.assertEqual(c.patch("/api/offer", json={"pc_id": "x", "candidates": []}, headers={"Origin": ORIGEM}).status_code, 401)
        self.assertEqual(self.newclaw.pedidos, [])
        self.assertEqual(self.motores, [])

    def test_repasse_com_bearer_e_sem_vazar_cabecalhos_do_newclaw(self):
        c = self.montar()
        self.entrar(c)
        r = c.post("/newclaw/api/chat", json={"message": "oi", "sessionId": "s1"}, headers={"Origin": ORIGEM})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["turnId"], "t1")
        enviado = self.newclaw.pedidos[-1]
        self.assertEqual(enviado.headers["authorization"], f"Bearer {TOKEN}")
        self.assertEqual(json.loads(enviado.content)["message"], "oi")
        r = c.get("/newclaw/api/chat/active", params={"sessionId": "s1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.newclaw.pedidos[-1].url.params["sessionId"], "s1")
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers})
        self.assertNotIn("x-interno", {k.lower() for k in r.headers})

    def test_post_de_outra_origem_com_sessao_e_recusado(self):
        c = self.montar()
        self.entrar(c)
        antes = len(self.newclaw.pedidos)
        r = c.post("/newclaw/api/chat", json={"message": "oi"}, headers={"Origin": "http://atacante.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(self.newclaw.pedidos), antes)

    def test_so_rotas_do_contrato(self):
        c = self.montar()
        self.entrar(c)
        antes = len(self.newclaw.pedidos)
        for metodo, rota in (("GET", "config"), ("POST", "config"), ("GET", "status"), ("GET", "memory"),
                             ("POST", "chat/../config"), ("GET", "chat/outbox/../../config"), ("POST", "chat/active"),
                             ("PUT", "chat"), ("POST", "voz/vocabulario"), ("PUT", "voz/vocabulario/../../config"),
                             ("GET", "voz/outra")):
            with self.subTest(metodo=metodo, rota=rota):
                r = c.request(metodo, f"/newclaw/api/{rota}", headers={"Origin": ORIGEM})
                self.assertIn(r.status_code, (404,))
        self.assertEqual(len(self.newclaw.pedidos), antes)

    def test_dicionario_da_voz_e_repassado(self):
        # ADR-039 do NewClaw, Revisão 2: as palavras moram no NewClaw (vão no backup dele); a janela lê e grava por aqui.
        c = self.montar()
        self.entrar(c)
        r = c.get("/newclaw/api/voz/vocabulario")
        self.assertEqual(self.newclaw.pedidos[-1].url.path, "/api/voz/vocabulario")
        self.assertEqual(self.newclaw.pedidos[-1].headers["authorization"], f"Bearer {TOKEN}")
        self.assertEqual(r.status_code, 404)  # o NewClaw falso não tem a rota: a resposta dele vem como veio
        r = c.put("/newclaw/api/voz/vocabulario", json={"revisao": 0, "palavras": []}, headers={"Origin": ORIGEM})
        self.assertEqual(self.newclaw.pedidos[-1].method, "PUT")
        self.assertEqual(json.loads(self.newclaw.pedidos[-1].content), {"revisao": 0, "palavras": []})
        antes = len(self.newclaw.pedidos)
        r = c.put("/newclaw/api/voz/vocabulario", json={"revisao": 0, "palavras": []},
                  headers={"Origin": "http://atacante.example"})
        self.assertEqual(r.status_code, 403)  # gravar exige a origem da janela, como o POST
        self.assertEqual(len(self.newclaw.pedidos), antes)

    def test_token_revogado_encerra_a_sessao(self):
        c = self.montar()
        self.entrar(c)
        self.newclaw.token_valido = False
        self.assertEqual(c.get("/newclaw/api/chat/active").status_code, 401)
        self.assertEqual(self.app.state.sessoes, {})

    # ─── sinalização ─────────────────────────────────────────────────────────

    def test_oferta_de_outra_origem_e_recusada(self):
        c = self.montar()
        self.entrar(c)
        r = c.post("/api/offer", json={"sdp": "x", "type": "offer"}, headers={"Origin": "http://atacante.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.motores, [])

    def test_candidatos_de_conexao_alheia_sao_recusados(self):
        c = self.montar()
        self.entrar(c)
        r = c.patch("/api/offer", json={"pc_id": "de-outra-sessao", "candidates": []}, headers={"Origin": ORIGEM})
        self.assertEqual(r.status_code, 403)
        r = c.post("/api/offer", json={"sdp": "x", "type": "offer", "pc_id": "de-outra-sessao"}, headers={"Origin": ORIGEM})
        self.assertEqual(r.status_code, 403)

    # ─── cabeçalhos e páginas ───────────────────────────────────────────────

    def test_cabecalhos_de_seguranca(self):
        c = self.montar()
        r = c.get("/saude")
        self.assertEqual(r.json(), {"ok": True})
        for nome in ("x-content-type-options", "referrer-policy", "x-frame-options", "cache-control"):
            self.assertIn(nome, {k.lower() for k in r.headers})

    def test_sem_documentacao_automatica(self):
        c = self.montar()
        for rota in ("/docs", "/redoc", "/openapi.json"):
            self.assertEqual(c.get(rota).status_code, 404)

    def test_politica_de_conteudo_so_aceita_esta_origem(self):
        c = self.montar()
        csp = c.get("/saude").headers["content-security-policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("http", csp)  # nenhum endereço de terceiros

    # ─── janela ─────────────────────────────────────────────────────────────

    def test_cliente_do_turno_vem_do_proprio_newclaw_sem_vazar_cabecalhos(self):
        c = self.montar()
        r = c.get("/newclaw/turn-client.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn("TURN_CONTRACT_VERSION = 1", r.text)
        self.assertTrue(r.headers["content-type"].startswith("text/javascript"))
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers})
        self.assertEqual(self.newclaw.pedidos[-1].url.path, "/turn-client.js")
        self.assertNotIn("authorization", {k.lower() for k in self.newclaw.pedidos[-1].headers})

    def test_voz_exige_sessao_e_nao_expoe_chaves(self):
        c = self.montar({"VOZ_STT_MOTOR": "url", "VOZ_STT_URL": "http://stt.local", "VOZ_STT_CHAVE": "chave-secreta",
                         "VOZ_STT_MODELO": "whisper-1"})
        self.assertEqual(c.get("/voz").status_code, 401)
        self.entrar(c)
        r = c.get("/voz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ouvir"], {"motor": "url", "modelo": "whisper-1", "voz": None})
        self.assertEqual(r.json()["idioma"], "pt-BR")
        self.assertNotIn("chave-secreta", r.text)
        self.assertNotIn("stt.local", r.text)

    def test_sem_build_da_janela_a_raiz_explica_como_gerar(self):
        c = self.montar()
        r = c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("npm run build", r.text)

    def test_com_build_a_janela_e_servida_sem_esconder_as_rotas(self):
        import httpx
        from fastapi.testclient import TestClient

        from newclaw_ivox import configuracao as cfg
        from newclaw_ivox.servidor import criar_app

        with tempfile.TemporaryDirectory() as pasta:
            dist = Path(pasta)
            (dist / "index.html").write_text("<!doctype html><title>NewClaw Voz</title>", encoding="utf-8")
            (dist / "assets").mkdir()
            (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
            newclaw = NewClawFalso()
            config = cfg.carregar({"NEWCLAW_URL": "http://newclaw.falso:3090"})
            cliente = httpx.AsyncClient(base_url=config.newclaw_url, transport=httpx.MockTransport(newclaw))
            c = TestClient(criar_app(config, cliente_http=cliente, janela_dir=dist), base_url="http://localhost:7860")
            self.assertIn("NewClaw Voz", c.get("/").text)
            self.assertEqual(c.get("/assets/app.js").status_code, 200)
            self.assertIn("content-security-policy", {k.lower() for k in c.get("/").headers})
            self.assertEqual(c.get("/saude").json(), {"ok": True})
            self.assertEqual(c.get("/newclaw/api/chat/active").status_code, 401)  # o repasse continua exigindo sessão


class TestConfiguracaoDoServidor(unittest.TestCase):
    def test_host_de_rede_sem_https_e_erro(self):
        from newclaw_ivox import configuracao as cfg

        c = cfg.carregar({"NEWCLAW_URL": "http://localhost:3090", "HARNESS_HOST": "0.0.0.0"})
        self.assertTrue(any(a.variavel == "HARNESS_HOST" and a.nivel == cfg.ERRO for a in c.achados))

    def test_host_de_rede_com_https(self):
        from newclaw_ivox import configuracao as cfg

        with tempfile.TemporaryDirectory() as pasta:
            cert, chave = Path(pasta) / "c.pem", Path(pasta) / "k.pem"
            cert.write_text("x")
            chave.write_text("x")
            c = cfg.carregar({"NEWCLAW_URL": "http://localhost:3090", "HARNESS_HOST": "192.0.2.20",
                              "HARNESS_TLS_CERT": str(cert), "HARNESS_TLS_CHAVE": str(chave), "HARNESS_PORTA": "8443"})
            self.assertFalse(c.tem_erro, c.achados)
            self.assertEqual(c.origem, "https://192.0.2.20:8443")
            self.assertEqual(c.origens_aceitas, ("https://192.0.2.20:8443",))

    def test_tls_pela_metade_e_arquivo_ausente(self):
        from newclaw_ivox import configuracao as cfg

        self.assertTrue(cfg.carregar({"HARNESS_TLS_CERT": "a.pem"}).tem_erro)
        self.assertTrue(cfg.carregar({"HARNESS_TLS_CERT": "nao.pem", "HARNESS_TLS_CHAVE": "nao.key"}).tem_erro)

    def test_newclaw_url(self):
        from newclaw_ivox import configuracao as cfg

        self.assertEqual(cfg.carregar({"NEWCLAW_URL": "http://localhost:3090/"}).newclaw_url, "http://localhost:3090")
        for ruim in ("localhost:3090", "ftp://x", "http://x/api"):
            with self.subTest(ruim=ruim):
                self.assertTrue(cfg.carregar({"NEWCLAW_URL": ruim}).tem_erro)

    def test_origens_em_loopback(self):
        from newclaw_ivox import configuracao as cfg

        c = cfg.carregar({})
        self.assertIn("http://localhost:7860", c.origens_aceitas)
        self.assertIn("http://127.0.0.1:7860", c.origens_aceitas)


if __name__ == "__main__":
    unittest.main()
