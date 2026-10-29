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
    def __init__(self, senha="certa", contrato=1, idioma="pt-BR"):
        self.senha, self.contrato, self.idioma = senha, contrato, idioma
        self.pedidos = []
        self.token_valido = True

    def __call__(self, pedido):
        import httpx

        self.pedidos.append(pedido)
        caminho = pedido.url.path
        if caminho == "/api/auth/login":
            if json.loads(pedido.content).get("password") == self.senha:
                return httpx.Response(200, json={"success": True, "token": TOKEN})
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
    def montar(self, ambiente=None, **kw):
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

        self.app = criar_app(config, cliente_http=cliente, montar_motor=motor_falso)
        return TestClient(self.app, base_url="http://localhost:7860")

    def entrar(self, c, senha="certa", origem=ORIGEM):
        return c.post("/entrar", json={"senha": senha}, headers={"Origin": origem})

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

    def test_contrato_de_outra_versao(self):
        c = self.montar(contrato=2)
        r = self.entrar(c)
        self.assertEqual(r.status_code, 409)
        self.assertIn("contrato do turno", r.json()["erro"])
        self.assertEqual(self.app.state.sessoes, {})

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
        self.assertEqual(c.get("/newclaw/chat/active").status_code, 401)

    # ─── repasse ─────────────────────────────────────────────────────────────

    def test_sem_login_401_em_tudo_que_alcanca_o_newclaw_ou_o_motor(self):
        c = self.montar()
        self.assertEqual(c.get("/newclaw/chat/active").status_code, 401)
        self.assertEqual(c.post("/newclaw/chat", json={"message": "oi"}, headers={"Origin": ORIGEM}).status_code, 401)
        self.assertEqual(c.post("/api/offer", json={"sdp": "x", "type": "offer"}, headers={"Origin": ORIGEM}).status_code, 401)
        self.assertEqual(c.patch("/api/offer", json={"pc_id": "x", "candidates": []}, headers={"Origin": ORIGEM}).status_code, 401)
        self.assertEqual(self.newclaw.pedidos, [])
        self.assertEqual(self.motores, [])

    def test_repasse_com_bearer_e_sem_vazar_cabecalhos_do_newclaw(self):
        c = self.montar()
        self.entrar(c)
        r = c.post("/newclaw/chat", json={"message": "oi", "sessionId": "s1"}, headers={"Origin": ORIGEM})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["turnId"], "t1")
        enviado = self.newclaw.pedidos[-1]
        self.assertEqual(enviado.headers["authorization"], f"Bearer {TOKEN}")
        self.assertEqual(json.loads(enviado.content)["message"], "oi")
        r = c.get("/newclaw/chat/active", params={"sessionId": "s1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.newclaw.pedidos[-1].url.params["sessionId"], "s1")
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers})
        self.assertNotIn("x-interno", {k.lower() for k in r.headers})

    def test_post_de_outra_origem_com_sessao_e_recusado(self):
        c = self.montar()
        self.entrar(c)
        antes = len(self.newclaw.pedidos)
        r = c.post("/newclaw/chat", json={"message": "oi"}, headers={"Origin": "http://atacante.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(self.newclaw.pedidos), antes)

    def test_so_rotas_do_contrato(self):
        c = self.montar()
        self.entrar(c)
        antes = len(self.newclaw.pedidos)
        for metodo, rota in (("GET", "config"), ("POST", "config"), ("GET", "status"), ("GET", "memory"),
                             ("POST", "chat/../config"), ("GET", "chat/outbox/../../config"), ("POST", "chat/active")):
            with self.subTest(rota=rota):
                r = c.request(metodo, f"/newclaw/{rota}", headers={"Origin": ORIGEM})
                self.assertIn(r.status_code, (404,))
        self.assertEqual(len(self.newclaw.pedidos), antes)

    def test_token_revogado_encerra_a_sessao(self):
        c = self.montar()
        self.entrar(c)
        self.newclaw.token_valido = False
        self.assertEqual(c.get("/newclaw/chat/active").status_code, 401)
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
