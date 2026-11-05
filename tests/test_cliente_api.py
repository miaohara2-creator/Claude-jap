"""Testa o cliente da Claude contra um servidor de API simulado.

Sobe um servidor HTTP local que imita `POST /v1/messages`, aponta o SDK para
ele e confere que o corpo enviado tem o formato esperado (schema JSON,
cache do prompt de sistema, fallbacks) e que a resposta e lida corretamente.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nihongo.claude_client import ClaudeClient, ClaudeRefusal

RECEBIDO: list[dict] = []
RESPOSTA = {"modo": "normal"}


class FakeAPI(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        RECEBIDO.append({"caminho": self.path, "corpo": corpo,
                         "beta": self.headers.get("anthropic-beta")})
        if RESPOSTA["modo"] == "recusa":
            payload = {"id": "msg_1", "type": "message", "role": "assistant",
                       "model": "claude-opus-5-5", "content": [],
                       "stop_reason": "refusal",
                       "stop_details": {"type": "refusal", "category": "cyber"},
                       "usage": {"input_tokens": 1, "output_tokens": 0}}
        else:
            frase = {"pt": "Todos os dias eu bebo água no trabalho.",
                     "keyword_pt": "bebo", "ja": "毎日、仕事で水を飲みます。",
                     "ja_reading": "まいにち、しごとでみずをのみます。",
                     "words_used": ["毎日", "仕事", "水", "飲む"], "note": "ます polido."}
            payload = {"id": "msg_1", "type": "message", "role": "assistant",
                       "model": "claude-opus-5-5",
                       "content": [{"type": "text",
                                    "text": json.dumps(frase, ensure_ascii=False)}],
                       "stop_reason": "end_turn",
                       "usage": {"input_tokens": 1234, "output_tokens": 98}}
        corpo_resp = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo_resp)))
        self.end_headers()
        self.wfile.write(corpo_resp)


class TestClienteClaude(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        RECEBIDO.clear()
        RESPOSTA["modo"] = "normal"
        import anthropic
        self.cliente = ClaudeClient()
        self.cliente._client = anthropic.Anthropic(
            api_key="chave-de-teste",
            base_url=f"http://127.0.0.1:{self.porta}",
            max_retries=0,
        )

    def test_envia_o_schema_e_le_a_resposta(self):
        r = self.cliente.generate_sentence("sistema", "pedido")
        self.assertEqual(r.data["keyword_pt"], "bebo")
        self.assertEqual(r.input_tokens, 1234)
        self.assertEqual(r.output_tokens, 98)

        corpo = RECEBIDO[0]["corpo"]
        self.assertEqual(corpo["model"], "claude-opus-5-5")
        fmt = corpo["output_config"]["format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertEqual(
            sorted(fmt["schema"]["required"]),
            ["ja", "ja_reading", "keyword_pt", "note", "pt", "words_used"],
        )
        self.assertEqual(corpo["output_config"]["effort"], "medium")
        # prompt de sistema marcado para cache
        self.assertEqual(corpo["system"][0]["cache_control"], {"type": "ephemeral"})
        # recuperacao automatica em caso de recusa
        self.assertEqual(corpo["fallbacks"], "default")
        self.assertIn("server-side-fallback", RECEBIDO[0]["beta"] or "")
        self.assertEqual(RECEBIDO[0]["caminho"], "/v1/messages")
        # sem amostragem nem budget_tokens (removidos nos modelos atuais)
        self.assertNotIn("temperature", corpo)
        self.assertNotIn("thinking", corpo)

    def test_recusa_vira_excecao(self):
        RESPOSTA["modo"] = "recusa"
        with self.assertRaises(ClaudeRefusal):
            self.cliente.generate_sentence("sistema", "pedido")

    def test_modelo_configuravel(self):
        self.cliente.model = "claude-sonnet-5-5"
        self.cliente.generate_sentence("s", "u")
        self.assertEqual(RECEBIDO[0]["corpo"]["model"], "claude-sonnet-5-5")

    def test_sem_credencial_nao_fica_disponivel(self):
        c = ClaudeClient()
        c._client = None
        if not ClaudeClient.credentials_present():
            self.assertFalse(c.available())


if __name__ == "__main__":
    unittest.main()
