"""Persistencia em SQLite: cartoes FSRS, frases geradas e historico."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .fsrs import Card, NEW

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "progresso.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Estado de agendamento (FSRS) de cada palavra-chave.
CREATE TABLE IF NOT EXISTS cards (
    item_id        TEXT PRIMARY KEY,
    lemma          TEXT NOT NULL,
    surface        TEXT NOT NULL,
    reading        TEXT NOT NULL,
    form_id        TEXT NOT NULL,
    level          TEXT NOT NULL,
    pt             TEXT NOT NULL,
    stability      REAL NOT NULL DEFAULT 0,
    difficulty     REAL NOT NULL DEFAULT 0,
    due            TEXT,
    last_review    TEXT,
    state          TEXT NOT NULL DEFAULT 'new',
    reps           INTEGER NOT NULL DEFAULT 0,
    lapses         INTEGER NOT NULL DEFAULT 0,
    scheduled_days REAL NOT NULL DEFAULT 0,
    introduced_at  TEXT,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due);
CREATE INDEX IF NOT EXISTS idx_cards_level ON cards(level);

-- Frases geradas, reaproveitaveis entre rodadas.
CREATE TABLE IF NOT EXISTS sentences (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      TEXT NOT NULL,
    pt           TEXT NOT NULL,
    ja           TEXT NOT NULL,
    ja_reading   TEXT NOT NULL DEFAULT '',
    keyword_pt   TEXT NOT NULL DEFAULT '',
    tokens       TEXT NOT NULL DEFAULT '[]',
    note         TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'claude',
    level        TEXT NOT NULL DEFAULT 'N5',
    created_at   TEXT NOT NULL,
    times_shown  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(item_id, pt)
);
CREATE INDEX IF NOT EXISTS idx_sentences_item ON sentences(item_id);

-- Historico de respostas.
CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         TEXT NOT NULL,
    sentence_id     INTEGER,
    answer          TEXT NOT NULL DEFAULT '',
    keyword_ok      INTEGER NOT NULL DEFAULT 0,
    rating          INTEGER NOT NULL,
    elapsed_days    REAL NOT NULL DEFAULT 0,
    scheduled_days  REAL NOT NULL DEFAULT 0,
    stability       REAL NOT NULL DEFAULT 0,
    difficulty      REAL NOT NULL DEFAULT 0,
    retrievability  REAL NOT NULL DEFAULT 0,
    state_before    TEXT NOT NULL DEFAULT 'new',
    reviewed_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_item ON reviews(item_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(reviewed_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- settings ---------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def set_setting(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        self.conn.commit()

    def all_settings(self) -> dict[str, Any]:
        rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except json.JSONDecodeError:
                out[r["key"]] = r["value"]
        return out

    # -- cards ------------------------------------------------------------

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> Card:
        return Card(
            stability=row["stability"],
            difficulty=row["difficulty"],
            due=from_iso(row["due"]),
            last_review=from_iso(row["last_review"]),
            state=row["state"],
            reps=row["reps"],
            lapses=row["lapses"],
            scheduled_days=row["scheduled_days"],
        )

    def get_card_row(self, item_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM cards WHERE item_id = ?", (item_id,)
        ).fetchone()

    def get_card(self, item_id: str) -> Card:
        row = self.get_card_row(item_id)
        return self._row_to_card(row) if row else Card()

    def ensure_card(self, item: Any) -> None:
        """Cria a linha do cartao (estado `new`) se ainda nao existir."""
        self.conn.execute(
            """INSERT OR IGNORE INTO cards
               (item_id, lemma, surface, reading, form_id, level, pt, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                item.item_id, item.lemma, item.surface, item.reading,
                item.form_id, item.level, item.pt, utcnow_iso(),
            ),
        )
        self.conn.commit()

    def save_card(self, item_id: str, card: Card, mark_introduced: bool = False) -> None:
        intro = ", introduced_at = COALESCE(introduced_at, ?)" if mark_introduced else ""
        params: list[Any] = [
            card.stability, card.difficulty, to_iso(card.due), to_iso(card.last_review),
            card.state, card.reps, card.lapses, card.scheduled_days,
        ]
        if mark_introduced:
            params.append(utcnow_iso())
        params.append(item_id)
        self.conn.execute(
            f"""UPDATE cards SET stability = ?, difficulty = ?, due = ?, last_review = ?,
                   state = ?, reps = ?, lapses = ?, scheduled_days = ?{intro}
                WHERE item_id = ?""",
            params,
        )
        self.conn.commit()

    def known_item_ids(self) -> set[str]:
        """Itens ja apresentados ao usuario (podem aparecer como palavra conhecida)."""
        rows = self.conn.execute(
            "SELECT item_id FROM cards WHERE reps > 0"
        ).fetchall()
        return {r["item_id"] for r in rows}

    def seen_item_ids(self) -> set[str]:
        rows = self.conn.execute("SELECT item_id FROM cards").fetchall()
        return {r["item_id"] for r in rows}

    def due_rows(self, now: datetime, limit: int = 50) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM cards
               WHERE reps > 0 AND due IS NOT NULL AND due <= ?
               ORDER BY due ASC LIMIT ?""",
            (now.isoformat(), limit),
        ).fetchall()

    def count_due(self, now: datetime) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM cards WHERE reps > 0 AND due IS NOT NULL AND due <= ?",
            (now.isoformat(),),
        ).fetchone()
        return row["n"]

    def level_progress(self) -> dict[str, dict[str, int]]:
        rows = self.conn.execute(
            """SELECT level,
                      COUNT(*) AS introduzidos,
                      SUM(CASE WHEN stability >= 21 THEN 1 ELSE 0 END) AS consolidados
               FROM cards WHERE reps > 0 GROUP BY level"""
        ).fetchall()
        return {
            r["level"]: {
                "introduzidos": r["introduzidos"],
                "consolidados": r["consolidados"] or 0,
            }
            for r in rows
        }

    def cards_overview(self, limit: int = 500) -> list[dict]:
        rows = self.conn.execute(
            """SELECT item_id, lemma, surface, reading, form_id, level, pt,
                      stability, difficulty, due, state, reps, lapses
               FROM cards WHERE reps > 0
               ORDER BY due ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- sentences --------------------------------------------------------

    def save_sentence(
        self,
        item_id: str,
        pt: str,
        ja: str,
        ja_reading: str = "",
        keyword_pt: str = "",
        tokens: Iterable[str] = (),
        note: str = "",
        source: str = "claude",
        level: str = "N5",
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO sentences
                 (item_id, pt, ja, ja_reading, keyword_pt, tokens, note, source, level, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(item_id, pt) DO UPDATE SET
                 ja = excluded.ja, ja_reading = excluded.ja_reading,
                 keyword_pt = excluded.keyword_pt, tokens = excluded.tokens,
                 note = excluded.note""",
            (
                item_id, pt, ja, ja_reading, keyword_pt,
                json.dumps(list(tokens), ensure_ascii=False), note, source, level,
                utcnow_iso(),
            ),
        )
        self.conn.commit()
        if cur.lastrowid:
            return int(cur.lastrowid)
        row = self.conn.execute(
            "SELECT id FROM sentences WHERE item_id = ? AND pt = ?", (item_id, pt)
        ).fetchone()
        return int(row["id"])

    def sentences_for_item(self, item_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM sentences WHERE item_id = ? ORDER BY times_shown ASC, id ASC",
            (item_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sentence(self, sentence_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM sentences WHERE id = ?", (sentence_id,)
        ).fetchone()
        return dict(row) if row else None

    def mark_sentence_shown(self, sentence_id: int) -> None:
        self.conn.execute(
            "UPDATE sentences SET times_shown = times_shown + 1 WHERE id = ?",
            (sentence_id,),
        )
        self.conn.commit()

    def count_sentences(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM sentences").fetchone()["n"]

    # -- reviews ----------------------------------------------------------

    def log_review(self, **kw: Any) -> int:
        cur = self.conn.execute(
            """INSERT INTO reviews
                 (item_id, sentence_id, answer, keyword_ok, rating, elapsed_days,
                  scheduled_days, stability, difficulty, retrievability,
                  state_before, reviewed_at)
               VALUES (:item_id, :sentence_id, :answer, :keyword_ok, :rating,
                       :elapsed_days, :scheduled_days, :stability, :difficulty,
                       :retrievability, :state_before, :reviewed_at)""",
            {"reviewed_at": utcnow_iso(), **kw},
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def recent_reviews(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            """SELECT r.*, s.pt AS frase_pt, s.ja AS frase_ja, c.surface, c.pt AS significado
               FROM reviews r
               LEFT JOIN sentences s ON s.id = r.sentence_id
               LEFT JOIN cards c ON c.item_id = r.item_id
               ORDER BY r.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) AS n FROM cards WHERE reps > 0"
        ).fetchone()["n"]
        reviews = self.conn.execute("SELECT COUNT(*) AS n FROM reviews").fetchone()["n"]
        acertos = self.conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE keyword_ok = 1"
        ).fetchone()["n"]
        hoje = self.conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE date(reviewed_at) = date('now')"
        ).fetchone()["n"]
        streak_row = self.conn.execute(
            "SELECT COUNT(DISTINCT date(reviewed_at)) AS n FROM reviews"
        ).fetchone()
        maturos = self.conn.execute(
            "SELECT COUNT(*) AS n FROM cards WHERE stability >= 21"
        ).fetchone()["n"]
        return {
            "palavras_aprendidas": total,
            "palavras_consolidadas": maturos,
            "revisoes_totais": reviews,
            "revisoes_hoje": hoje,
            "dias_estudados": streak_row["n"],
            "acerto_percentual": round(100 * acertos / reviews, 1) if reviews else 0.0,
            "frases_no_banco": self.count_sentences(),
        }
