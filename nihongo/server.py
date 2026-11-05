"""Servidor HTTP (biblioteca padrao) que serve a interface e a API JSON."""

from __future__ import annotations

import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .conjugation import LEVEL_ORDER
from .db import Database
from .engine import DEFAULTS, Engine

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class AppState:
    """Estado compartilhado entre as threads do servidor."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.lock = threading.Lock()


def make_handler(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Nihongo/1.0"
        protocol_version = "HTTP/1.1"

        # -- utilidades ----------------------------------------------------

        def log_message(self, fmt: str, *args) -> None:  # menos ruido
            if self.path.startswith("/api/"):
                print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _error(self, exc: Exception, status: int = 400) -> None:
            self._json({"erro": str(exc) or exc.__class__.__name__}, status)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw or b"{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido no corpo da requisição: {exc}") from exc

        def _static(self, rel: str) -> None:
            path = (WEB_DIR / rel).resolve()
            if not str(path).startswith(str(WEB_DIR.resolve())) or not path.is_file():
                self._json({"erro": "arquivo não encontrado"}, 404)
                return
            ctype = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
            self._send(200, path.read_bytes(), ctype)

        # -- rotas ---------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route, query = parsed.path, parse_qs(parsed.query)
            try:
                if route in ("/", "/index.html"):
                    self._static("index.html")
                elif route.startswith("/static/"):
                    self._static(route[len("/static/"):])
                elif route == "/api/estado":
                    with state.lock:
                        self._json(
                            {
                                "estatisticas": state.engine.stats(),
                                "config": state.engine.all_config(),
                                "niveis": LEVEL_ORDER,
                            }
                        )
                elif route == "/api/agenda":
                    limite = int(query.get("limite", ["80"])[0])
                    with state.lock:
                        self._json({"agenda": state.engine.agenda(limite)})
                elif route == "/api/historico":
                    limite = int(query.get("limite", ["25"])[0])
                    with state.lock:
                        self._json({"historico": state.engine.db.recent_reviews(limite)})
                elif route == "/api/frases":
                    with state.lock:
                        rows = state.engine.db.conn.execute(
                            "SELECT s.*, c.pt AS significado FROM sentences s "
                            "LEFT JOIN cards c ON c.item_id = s.item_id "
                            "ORDER BY s.id DESC LIMIT ?",
                            (int(query.get("limite", ["50"])[0]),),
                        ).fetchall()
                        self._json({"frases": [dict(r) for r in rows]})
                else:
                    self._json({"erro": f"rota desconhecida: {route}"}, 404)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self._error(exc, 500)

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            try:
                data = self._body()
                if route == "/api/rodada":
                    with state.lock:
                        rodada = state.engine.next_round(force=data.get("modo"))
                        payload = rodada.to_dict()
                        payload["estatisticas"] = state.engine.stats()
                    self._json(payload)
                elif route == "/api/revelar":
                    with state.lock:
                        self._json(
                            state.engine.revelar(
                                item_id=data["item_id"],
                                sentence_id=int(data["sentence_id"]),
                            )
                        )
                elif route == "/api/corrigir":
                    with state.lock:
                        self._json(
                            state.engine.check(
                                item_id=data["item_id"],
                                sentence_id=int(data["sentence_id"]),
                                answer=data.get("resposta", ""),
                                hint_used=bool(data.get("dica")),
                                revealed=bool(data.get("revelou")),
                            )
                        )
                elif route == "/api/responder":
                    with state.lock:
                        self._json(
                            state.engine.submit(
                                item_id=data["item_id"],
                                sentence_id=int(data["sentence_id"]),
                                answer=data.get("resposta", ""),
                                rating=(int(data["nota"]) if data.get("nota") else None),
                                hint_used=bool(data.get("dica")),
                                revealed=bool(data.get("revelou")),
                                autoavaliacao=bool(data.get("autoavaliacao")),
                            )
                        )
                elif route == "/api/dica":
                    with state.lock:
                        self._json(state.engine.hint(data["item_id"]))
                elif route == "/api/config":
                    with state.lock:
                        for key, value in data.items():
                            if key in DEFAULTS:
                                state.engine.db.set_setting(key, value)
                        self._json({"config": state.engine.all_config()})
                else:
                    self._json({"erro": f"rota desconhecida: {route}"}, 404)
            except KeyError as exc:
                self._error(ValueError(f"campo obrigatório ausente: {exc}"), 400)
            except (ValueError, RuntimeError) as exc:
                self._error(exc, 400)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self._error(exc, 500)

    return Handler


def _abrir_no_navegador(url: str, atraso: float = 1.0) -> None:
    """Abre a interface no navegador padrao, sem derrubar o servidor se falhar."""
    import webbrowser

    def alvo() -> None:
        import time

        time.sleep(atraso)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - navegador e um extra, nao um requisito
            pass

    threading.Thread(target=alvo, daemon=True).start()


def serve(
    db_path: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    model: str | None = None,
    abrir_navegador: bool = False,
) -> None:
    from .claude_client import ClaudeClient

    db = Database(db_path) if db_path else Database()
    client = ClaudeClient(model=model)
    engine = Engine(db, client=client)
    state = AppState(engine)
    httpd = ThreadingHTTPServer((host, port), make_handler(state))

    stats = engine.stats()
    print(f"\n  日本語 — aprendizado incremental de japonês")
    print(f"  ──────────────────────────────────────────")
    print(f"  interface:  http://{host}:{port}")
    print(f"  banco:      {db.path}")
    print(f"  gerador:    {stats['gerador']}")
    print(f"  vocabulário:{len(engine.vocab)} formas estudáveis")
    print(f"  nível atual: {stats['nivel_atual']} | aprendidas: "
          f"{stats['palavras_aprendidas']} | a revisar: {stats['revisoes_pendentes']}")
    if "local" in stats["gerador"]:
        from .config import COMANDO_LOGIN

        print("\n  Atenção: as frases virão do gerador local, que é limitado.")
        print("  Para a Claude escrevê-las, conecte a sua conta: duplo clique em")
        print(f"  conectar-conta.bat (ou rode `{COMANDO_LOGIN}`).")
        motivo = engine.client.motivo_indisponivel() if engine.client else None
        if motivo:
            print(f"  Motivo atual: {motivo}")
    print("\n  Ctrl+C para encerrar (ou feche esta janela).\n")
    if abrir_navegador:
        _abrir_no_navegador(f"http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  encerrando…")
    finally:
        httpd.server_close()
        db.close()
