"""Motor do aplicativo: escolhe a palavra da rodada, obtem a frase e aplica o FSRS."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .claude_client import ClaudeClient, ClaudeRefusal, ClaudeUnavailable
from .conjugation import LEVEL_ORDER, level_index
from .db import Database, from_iso
from .fsrs import AGAIN, FSRS, GOOD, HARD, RATING_LABELS, RATINGS, utcnow
from .generator import SYSTEM_PROMPT, build_user_prompt, validate_sentence
from .grading import grade_answer, normalize_ja
from .templates import build_local_sentence, corpus_entries
from .vocab import Item, Vocabulary

DEFAULTS: dict[str, Any] = {
    "desired_retention": 0.9,      # alvo de retencao do FSRS
    "new_per_day": 10,             # palavras novas por dia
    "advance_ratio": 0.8,          # fracao do nivel a introduzir antes de liberar o proximo
    "mix_threshold": 0.5,          # a partir daqui o nivel seguinte pode aparecer
    "mix_probability": 0.15,       # chance de puxar uma palavra do nivel seguinte
    "new_round_ratio": 0.25,       # chance de introduzir palavra nova havendo revisoes
    "generation_attempts": 3,      # tentativas de geracao com a Claude por rodada
    "reuse_sentences": True,       # reaproveitar frases do banco nas revisoes
}


@dataclass
class Round:
    mode: str                 # "nova" | "revisão"
    item: Item
    sentence: dict            # linha da tabela `sentences`
    source: str               # claude | banco | corpus | local
    due_count: int
    warnings: list[str]

    def to_dict(self) -> dict:
        palavra = {
            "item_id": self.item.item_id,
            "nivel": self.item.level,
            "forma": self.item.form_label,
            "dica_forma": self.item.form_hint,
            "classe": self.item.word_type,
            "significado": self.item.pt,
        }
        if self.mode == "nova":
            # rodada de apresentacao: a palavra e ENSINADA antes de ser cobrada
            palavra.update(
                {
                    "grafia": self.item.surface,
                    "leitura": self.item.reading,
                    "lema": f"{self.item.lemma} ({self.item.lemma_reading})",
                }
            )
        return {
            "modo": self.mode,
            "origem": self.source,
            "avisos": self.warnings,
            "revisoes_pendentes": self.due_count,
            "frase": {
                "id": self.sentence["id"],
                "pt": self.sentence["pt"],
                "keyword_pt": self.sentence["keyword_pt"],
                "nota": self.sentence["note"],
            },
            "palavra": palavra,
        }

    @property
    def is_introduction(self) -> bool:
        return self.mode == "nova"


class Engine:
    def __init__(
        self,
        db: Database,
        vocab: Vocabulary | None = None,
        client: ClaudeClient | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.db = db
        self.vocab = vocab or Vocabulary.load()
        self.client = client if client is not None else ClaudeClient()
        self.rng = rng or random.Random()
        self.corpus = corpus_entries()
        #: motivo pelo qual paramos de chamar a API nesta execucao (ou None)
        self.api_desativada: str | None = None

    # -- configuracao -----------------------------------------------------

    def setting(self, key: str) -> Any:
        return self.db.get_setting(key, DEFAULTS.get(key))

    def all_config(self) -> dict[str, Any]:
        return {k: self.setting(k) for k in DEFAULTS}

    def scheduler(self) -> FSRS:
        return FSRS(desired_retention=float(self.setting("desired_retention")))

    # -- niveis -----------------------------------------------------------

    def level_status(self) -> dict:
        totals = self.vocab.level_counts()
        introduced = {lv: 0 for lv in LEVEL_ORDER}
        for lv, data in self.db.level_progress().items():
            introduced[lv] = data["introduzidos"]
        ratios = {
            lv: (introduced[lv] / totals[lv] if totals[lv] else 1.0) for lv in LEVEL_ORDER
        }
        advance = float(self.setting("advance_ratio"))
        current = LEVEL_ORDER[-1]
        for lv in LEVEL_ORDER:
            if ratios[lv] < advance:
                current = lv
                break
        return {
            "nivel_atual": current,
            "totais": totals,
            "introduzidos": introduced,
            "progresso": {lv: round(100 * ratios[lv], 1) for lv in LEVEL_ORDER},
        }

    def allowed_levels(self) -> set[str]:
        """Niveis liberados agora (com uma chance de espiar o nivel seguinte)."""
        status = self.level_status()
        current = status["nivel_atual"]
        idx = level_index(current)
        allowed = set(LEVEL_ORDER[: idx + 1])
        ratio = status["progresso"][current] / 100
        if (
            idx + 1 < len(LEVEL_ORDER)
            and ratio >= float(self.setting("mix_threshold"))
            and self.rng.random() < float(self.setting("mix_probability"))
        ):
            allowed.add(LEVEL_ORDER[idx + 1])
        return allowed

    # -- selecao da palavra -----------------------------------------------

    def new_words_today(self) -> int:
        row = self.db.conn.execute(
            "SELECT COUNT(*) AS n FROM cards "
            "WHERE introduced_at IS NOT NULL AND date(introduced_at) = date('now')"
        ).fetchone()
        return row["n"]

    def can_introduce(self) -> bool:
        return self.new_words_today() < int(self.setting("new_per_day"))

    def pick_new_item(self, skip: set[str] | None = None) -> Item | None:
        """Proxima palavra-chave inedita, na ordem pedagogica."""
        known = self.db.known_item_ids()
        # so saem da fila as palavras realmente apresentadas (reps > 0); uma
        # rodada abandonada ou adiada volta a ser oferecida depois
        seen = known | (skip or set())
        levels = self.allowed_levels()
        for item in self.vocab.items:
            if item.item_id in seen or item.level not in levels:
                continue
            anteriores = self.vocab.earlier_forms(item)
            if anteriores and not any(f.item_id in known for f in anteriores):
                # as formas de um verbo saem na ordem pedagogica: so libera a
                # proxima depois que alguma forma anterior ja foi apresentada
                continue
            return item
        return None

    def pick_due_item(self, now: datetime) -> Item | None:
        for row in self.db.due_rows(now, limit=30):
            item = self.vocab.get(row["item_id"])
            if item is not None:
                return item
        return None

    def pick_ahead_item(self) -> Item | None:
        """Sem nada vencido nem inedito: antecipa o cartao mais proximo."""
        row = self.db.conn.execute(
            "SELECT item_id FROM cards WHERE reps > 0 ORDER BY due ASC LIMIT 1"
        ).fetchone()
        return self.vocab.get(row["item_id"]) if row else None

    # -- obtencao da frase ------------------------------------------------

    def _known_items(self, known_ids: set[str]) -> list[Item]:
        return [self.vocab.by_id[i] for i in known_ids if i in self.vocab.by_id]

    def _stored_sentence(self, item: Item, known_ids: set[str]) -> dict | None:
        for row in self.db.sentences_for_item(item.item_id):
            if validate_sentence(row, item, self.vocab, known_ids).ok:
                return row
        return None

    def _persist(self, item: Item, data: dict, source: str) -> dict:
        sid = self.db.save_sentence(
            item_id=item.item_id,
            pt=data["pt"],
            ja=data["ja"],
            ja_reading=data.get("ja_reading", ""),
            keyword_pt=data.get("keyword_pt", ""),
            tokens=data.get("words_used", []),
            note=data.get("note", ""),
            source=source,
            level=item.level,
        )
        row = self.db.get_sentence(sid)
        if row is None:  # pragma: no cover
            raise RuntimeError(
                f"a frase {sid} de {item.item_id} sumiu logo após ser gravada"
            )
        return row

    def generate_with_claude(
        self, item: Item, known_ids: set[str], warnings: list[str]
    ) -> dict | None:
        """Pede a frase a Claude, revalidando e reenviando o erro em caso de falha."""
        if not self.client or not self.client.available() or self.api_desativada:
            return None
        known = sorted(self._known_items(known_ids), key=lambda it: it.sort_key)
        recent = [
            r["pt"] for r in self.db.sentences_for_item(item.item_id)
        ] + self._recent_sentence_texts()
        attempts = int(self.setting("generation_attempts"))
        feedback: list[str] = []

        for attempt in range(1, attempts + 1):
            user = build_user_prompt(item, known, recent)
            if feedback:
                user += (
                    "\n\nA TENTATIVA ANTERIOR FOI REJEITADA PELO VALIDADOR:\n- "
                    + "\n- ".join(feedback)
                    + "\nCorrija exatamente esses pontos nesta nova tentativa."
                )
            try:
                result = self.client.generate_sentence(SYSTEM_PROMPT, user)
            except (ClaudeUnavailable, ClaudeRefusal) as exc:
                warnings.append(str(exc))
                return None
            except Exception as exc:  # erro de rede/API
                motivo, definitivo = explicar_erro_api(exc)
                warnings.append(motivo)
                if definitivo:
                    # nao adianta insistir a cada rodada: desliga ate reiniciar
                    self.api_desativada = motivo
                return None

            self._count_tokens(result.input_tokens, result.output_tokens)
            check = validate_sentence(result.data, item, self.vocab, known_ids)
            if check.ok:
                if attempt > 1:
                    warnings.append(f"Frase aceita na tentativa {attempt}.")
                return result.data
            feedback = check.problems

        warnings.append(
            "A Claude não produziu uma frase válida em "
            f"{attempts} tentativas ({'; '.join(feedback)}). Usei o gerador local."
        )
        return None

    def _recent_sentence_texts(self, limit: int = 6) -> list[str]:
        rows = self.db.conn.execute(
            "SELECT pt FROM sentences ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [r["pt"] for r in rows]

    def _count_tokens(self, inp: int, out: int) -> None:
        self.db.set_setting("tokens_entrada", int(self.setting("tokens_entrada") or 0) + inp)
        self.db.set_setting("tokens_saida", int(self.setting("tokens_saida") or 0) + out)

    def sentence_for(
        self, item: Item, known_ids: set[str], mode: str, warnings: list[str]
    ) -> tuple[dict, str]:
        """Frase da rodada: banco -> Claude -> corpus -> moldes locais."""
        if mode == "revisão" and self.setting("reuse_sentences"):
            stored = self._stored_sentence(item, known_ids)
            if stored:
                return stored, "banco"

        data = self.generate_with_claude(item, known_ids, warnings)
        if data:
            return self._persist(item, data, "claude"), "claude"

        for entry in self.corpus.get(item.item_id, []):
            if validate_sentence(entry, item, self.vocab, known_ids).ok:
                return self._persist(item, entry, "corpus"), "corpus"

        local = build_local_sentence(item, known_ids, self.rng)
        if local and validate_sentence(local, item, self.vocab, known_ids).ok:
            return self._persist(item, local, "local"), "local"

        stored = self._stored_sentence(item, known_ids)
        if stored:
            return stored, "banco"

        raise RuntimeError(
            f"Não consegui montar uma frase para {item.surface} ({item.form_label}). "
            "Configure ANTHROPIC_API_KEY para que a Claude gere as frases."
        )

    # -- rodada -----------------------------------------------------------

    def next_round(self, force: str | None = None) -> Round:
        now = utcnow()
        due_count = self.db.count_due(now)
        warnings: list[str] = []

        item, mode = None, "nova"
        want_new = force == "nova" or (
            force != "revisão"
            and (
                due_count == 0
                or (self.can_introduce() and self.rng.random() < float(self.setting("new_round_ratio")))
            )
        )

        if want_new and self.can_introduce():
            item = self.pick_new_item()
            if item is None and due_count == 0:
                warnings.append("Nenhuma palavra nova disponível neste nível.")
        if item is None:
            item = self.pick_due_item(now)
            mode = "revisão"
        if item is None and self.can_introduce():
            item = self.pick_new_item()
            mode = "nova"
        if item is None:
            item = self.pick_ahead_item()
            mode = "revisão"
            if item is not None:
                warnings.append(
                    "Nada vencido agora e o limite de palavras novas de hoje foi "
                    "atingido — esta é uma revisão antecipada."
                )
        if item is None:
            raise RuntimeError("Não há palavras para estudar.")

        # Sem a API da Claude, nem toda forma tem frase disponivel localmente;
        # nesse caso seguimos para a proxima palavra apresentavel em vez de travar.
        pulados: set[str] = set()
        ultimo_erro: RuntimeError | None = None
        for _ in range(25):
            known_ids = self.db.known_item_ids() - {item.item_id}
            try:
                sentence, source = self.sentence_for(item, known_ids, mode, warnings)
            except RuntimeError as exc:
                ultimo_erro = exc
                if mode != "nova":
                    raise
                pulados.add(item.item_id)
                proximo = self.pick_new_item(skip=pulados)
                if proximo is None:
                    raise
                item = proximo
                continue
            if pulados:
                warnings.append(
                    f"{len(pulados)} palavra(s) foram adiadas: o gerador local não "
                    "cobre essas formas. Com ANTHROPIC_API_KEY a Claude escreve "
                    "frases para todas."
                )
            self.db.ensure_card(item)
            self.db.mark_sentence_shown(sentence["id"])
            return Round(mode, item, sentence, source, due_count, warnings)
        raise ultimo_erro or RuntimeError("Não consegui montar uma frase para esta rodada.")

    # -- resposta ---------------------------------------------------------

    def revelar(self, item_id: str, sentence_id: int) -> dict:
        """Mostra a resposta de referência para o aluno se autoavaliar.

        Não julga nada e não agenda nada: quem diz se acertou é o aluno, na
        nota que escolher em seguida. É o fluxo padrão do app -- digitar
        japonês exigiria um IME instalado.
        """
        item = self.vocab.get(item_id)
        if item is None:
            raise ValueError(f"palavra desconhecida: {item_id}")
        sentence = self.db.get_sentence(sentence_id)
        if sentence is None:
            raise ValueError(f"frase inexistente: {sentence_id}")

        now = utcnow()
        before = self.db.get_card(item_id)
        introducao = before.state == "new"
        # numa apresentação a grafia estava na tela: "fácil" não se sustenta
        permitidas = [AGAIN, HARD, GOOD] if introducao else list(RATINGS)

        fsrs = self.scheduler()
        return {
            "apresentacao": introducao,
            "notas_permitidas": permitidas,
            "nota_sugerida": GOOD if introducao else GOOD,
            "palavra": {
                "grafia": item.surface,
                "leitura": item.reading,
                "significado": item.pt,
                "forma": item.form_label,
                "lema": f"{item.lemma} ({item.lemma_reading})",
                "nivel": item.level,
            },
            "referencia": {
                "ja": sentence["ja"],
                "leitura": sentence["ja_reading"],
                "nota": sentence["note"],
                "origem": sentence["source"],
                "palavras": self.analyze(sentence["ja"], item),
            },
            "previsao": {
                str(r): humanize_days(d) for r, d in fsrs.preview(before, now).items()
            },
        }


    def check(
        self,
        item_id: str,
        sentence_id: int,
        answer: str,
        hint_used: bool = False,
        revealed: bool = False,
    ) -> dict:
        """Corrige a resposta SEM agendar nada: devolve o feedback e as notas possíveis.

        Assim o aluno vê a correção, confere a frase de referência e só então
        escolhe a nota (o FSRS é aplicado em `submit`).
        """
        item = self.vocab.get(item_id)
        if item is None:
            raise ValueError(f"palavra desconhecida: {item_id}")
        sentence = self.db.get_sentence(sentence_id)
        if sentence is None:
            raise ValueError(f"frase inexistente: {sentence_id}")

        now = utcnow()
        before = self.db.get_card(item_id)
        introducao = before.state == "new"
        grade = grade_answer(item, answer, sentence["ja"], hint_used, revealed)

        if not grade.keyword_ok:
            permitidas = [AGAIN]
        elif grade.status == "quase":
            permitidas = [AGAIN, HARD]
        elif introducao:
            permitidas = [AGAIN, HARD, GOOD]
        else:
            permitidas = list(RATINGS)

        sugerida = grade.suggested_rating
        if sugerida not in permitidas:
            sugerida = max(r for r in permitidas)

        fsrs = self.scheduler()
        return {
            "acertou": grade.keyword_ok,
            "situacao": grade.status,
            "mensagem": grade.message,
            "observacoes": grade.diff_notes,
            "semelhanca": round(grade.similarity, 2),
            "apresentacao": introducao,
            "nota_sugerida": sugerida,
            "notas_permitidas": permitidas,
            "palavra": {
                "grafia": item.surface,
                "leitura": item.reading,
                "significado": item.pt,
                "forma": item.form_label,
                "lema": f"{item.lemma} ({item.lemma_reading})",
                "nivel": item.level,
            },
            "referencia": {
                "ja": sentence["ja"],
                "leitura": sentence["ja_reading"],
                "nota": sentence["note"],
                "origem": sentence["source"],
                "palavras": self.analyze(sentence["ja"], item),
            },
            "previsao": {
                str(r): humanize_days(d) for r, d in fsrs.preview(before, now).items()
            },
        }


    def submit(
        self,
        item_id: str,
        sentence_id: int,
        answer: str = "",
        rating: int | None = None,
        hint_used: bool = False,
        revealed: bool = False,
        autoavaliacao: bool = False,
    ) -> dict:
        """Aplica a nota ao FSRS.

        Com `autoavaliacao`, a nota vem do aluno e é respeitada: o app não
        viu resposta nenhuma, então não tem como contradizê-lo. Com resposta
        digitada, errar a palavra-chave força `AGAIN` -- aí o app sabe.
        """
        item = self.vocab.get(item_id)
        if item is None:
            raise ValueError(f"palavra desconhecida: {item_id}")
        sentence = self.db.get_sentence(sentence_id)
        if sentence is None:
            raise ValueError(f"frase inexistente: {sentence_id}")

        now = utcnow()
        self.db.ensure_card(item)
        before = self.db.get_card(item_id)
        grade = grade_answer(item, answer, sentence["ja"], hint_used, revealed)

        introducao = before.state == "new"
        chosen = rating if rating in RATINGS else grade.suggested_rating
        if autoavaliacao:
            if rating not in RATINGS:
                raise ValueError("a autoavaliação precisa de uma nota")
            chosen = rating
        elif not grade.keyword_ok:
            chosen = AGAIN   # errou a palavra-chave: o FSRS tem de saber disso
        elif grade.status == "quase" and chosen > HARD:
            chosen = HARD
        if introducao and chosen > GOOD:
            # a grafia estava visivel na tela: nao da para creditar "fácil"
            chosen = GOOD

        fsrs = self.scheduler()
        retr = before.retrievability(now) if before.state != "new" else 0.0
        after = fsrs.review(before, chosen, now)
        self.db.save_card(item_id, after, mark_introduced=(before.state == "new"))
        self.db.log_review(
            item_id=item_id,
            sentence_id=sentence_id,
            answer=answer,
            keyword_ok=1 if (chosen > AGAIN if autoavaliacao else grade.keyword_ok) else 0,
            rating=chosen,
            elapsed_days=before.elapsed_days(now),
            scheduled_days=after.scheduled_days,
            stability=after.stability,
            difficulty=after.difficulty,
            retrievability=retr,
            state_before=before.state,
        )

        return {
            "acertou": (chosen > AGAIN) if autoavaliacao else grade.keyword_ok,
            "apresentacao": introducao,
            "situacao": "autoavaliacao" if autoavaliacao else grade.status,
            "mensagem": (
                f"Nota registrada: {RATING_LABELS[chosen]}."
                if autoavaliacao else grade.message
            ),
            "observacoes": grade.diff_notes,
            "semelhanca": round(grade.similarity, 2),
            "nota_aplicada": chosen,
            "nota_label": RATING_LABELS[chosen],
            "palavra": {
                "grafia": item.surface,
                "leitura": item.reading,
                "significado": item.pt,
                "forma": item.form_label,
                "lema": f"{item.lemma} ({item.lemma_reading})",
                "nivel": item.level,
            },
            "referencia": {
                "ja": sentence["ja"],
                "leitura": sentence["ja_reading"],
                "nota": sentence["note"],
                "palavras": self.analyze(sentence["ja"], item),
            },
            "agendamento": {
                "proxima_revisao": after.due.isoformat() if after.due else None,
                "intervalo_dias": round(after.scheduled_days, 3),
                "intervalo_texto": humanize_days(after.scheduled_days),
                "estabilidade": round(after.stability, 2),
                "dificuldade": round(after.difficulty, 2),
                "estado": after.state,
                "repeticoes": after.reps,
                "lapsos": after.lapses,
                "retrievabilidade_antes": round(retr, 3),
            },
            "previsao": {
                str(r): humanize_days(d) for r, d in fsrs.preview(before, now).items()
            },
            "estatisticas": self.stats(),
        }

    # -- apoio ------------------------------------------------------------

    def analyze(self, ja: str, target: Item | None = None) -> list[dict]:
        """Decompoe a frase de referencia nas palavras do vocabulario (p/ feedback)."""
        norm = normalize_ja(ja)
        found: list[dict] = []
        used: set[str] = set()
        for item in sorted(self.vocab.items, key=lambda i: -len(i.surface)):
            surf = normalize_ja(item.surface)
            if len(surf) < 2 and item.word_type not in ("noun", "pronoun"):
                continue
            pos = norm.find(surf)
            if pos < 0 or item.lemma in used:
                continue
            used.add(item.lemma)
            found.append(
                {
                    "grafia": item.surface,
                    "leitura": item.reading,
                    "significado": item.pt,
                    "forma": item.form_label,
                    "posicao": pos,
                    "alvo": bool(target and item.item_id == target.item_id),
                }
            )
        found.sort(key=lambda d: d["posicao"])
        return found

    def hint(self, item_id: str) -> dict:
        item = self.vocab.get(item_id)
        if item is None:
            raise ValueError(item_id)
        card = self.db.get_card(item_id)
        return {
            "significado": item.pt,
            "forma": item.form_label,
            "dica_forma": item.form_hint,
            "primeira_letra": item.reading[0] if item.reading else "",
            "tamanho": len(item.reading),
            "lema_leitura": item.lemma_reading,
            "ja_visto": card.reps > 0,
        }

    def stats(self) -> dict:
        now = utcnow()
        base = self.db.stats()
        base["revisoes_pendentes"] = self.db.count_due(now)
        base["novas_hoje"] = self.new_words_today()
        base["limite_novas"] = int(self.setting("new_per_day"))
        base.update(self.level_status())
        base["tokens"] = {
            "entrada": int(self.setting("tokens_entrada") or 0),
            "saida": int(self.setting("tokens_saida") or 0),
        }
        # `gerador` é curto (cabe no rodapé); o porquê vai em `motivo_local`
        base["motivo_local"] = None
        if self.api_desativada:
            base["gerador"] = "gerador local"
            base["motivo_local"] = self.api_desativada
        elif self.client and self.client.available():
            from .config import origem_credencial

            base["gerador"] = f"Claude {self.client.model} · {origem_credencial()}"
        elif self.client:
            base["gerador"] = "gerador local"
            base["motivo_local"] = self.client.motivo_indisponivel()
        else:
            base["gerador"] = "gerador local"
        return base

    def agenda(self, limit: int = 100) -> list[dict]:
        out = []
        for row in self.db.cards_overview(limit):
            due = from_iso(row["due"])
            row["vence_em"] = (
                humanize_days((due - utcnow()).total_seconds() / 86400.0) if due else "—"
            )
            row["estabilidade"] = round(row["stability"], 2)
            row["dificuldade"] = round(row["difficulty"], 2)
            out.append(row)
        return out


def explicar_erro_api(exc: Exception) -> tuple[str, bool]:
    """Traduz a falha da API para o usuário.

    Devolve (mensagem, definitivo). `definitivo` indica que não adianta tentar
    de novo nesta execução — chave inválida ou sem crédito, por exemplo.
    """
    status = getattr(exc, "status_code", None)
    texto = str(exc).lower()

    if status == 401 or "authentication_error" in texto or "invalid x-api-key" in texto:
        return (
            "A API da Claude recusou a chave (401). Confira o conteúdo do arquivo "
            "chave-api.txt ou a variável ANTHROPIC_API_KEY. Seguindo com o gerador "
            "local até você corrigir e reiniciar o aplicativo.",
            True,
        )
    if status == 403 or "permission_error" in texto:
        return (
            "A chave não tem permissão para usar este modelo (403). Seguindo com o "
            "gerador local nesta execução.",
            True,
        )
    if status == 402 or "credit balance" in texto or "billing" in texto:
        return (
            "A conta da API está sem crédito. Seguindo com o gerador local nesta "
            "execução.",
            True,
        )
    if status == 429 or "rate_limit" in texto:
        return ("Limite de requisições atingido; vou tentar de novo na próxima "
                "rodada.", False)
    if status is not None and 500 <= int(status) < 600:
        return (f"A API da Claude teve um erro temporário ({status}); tento de novo "
                "na próxima rodada.", False)
    if "connection" in texto or "timeout" in texto or "network" in texto:
        return ("Não consegui falar com a API da Claude (rede). Usando o gerador "
                "local nesta rodada.", False)
    return (f"Falha ao falar com a API da Claude: {exc}", False)


def humanize_days(days: float) -> str:
    if days <= 0:
        return "agora"
    if days < 1:
        minutes = max(1, int(round(days * 1440)))
        if minutes < 60:
            return f"{minutes} min"
        hours = minutes / 60
        return f"{hours:.0f} h"
    if days < 30:
        d = int(round(days))
        return f"{d} dia" if d == 1 else f"{d} dias"
    if days < 365:
        m = days / 30.44
        return f"{m:.1f} meses".replace(".0", "")
    return f"{days / 365.25:.1f} anos".replace(".0", "")
