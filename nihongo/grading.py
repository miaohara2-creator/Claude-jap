"""Correcao da resposta do usuario.

A checagem principal e a *palavra-chave*: a frase so conta como acerto se a
forma-alvo (ex. `飲みませんでした`) aparecer na traducao. Aceitam-se a escrita
com kanji, a leitura em kana e escritas alternativas registradas no
vocabulario. Tambem detectamos "quase acertos" (1 caractere de diferenca),
que sugerem a nota `difícil` em vez de `errei`.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from .fsrs import AGAIN, EASY, GOOD, HARD

_PUNCT = "。、，．・！？!?,.「」『』（）()［］\"'　 \t\n~〜ー…:：;；"
_PUNCT_KEEP_CHOUON = "。、，．・！？!?,.「」『』（）()［］\"'　 \t\n…:：;；"

_KANA_RE = re.compile(r"[぀-ヿ一-鿿ｦ-ﾟ]")
_LATIN_RE = re.compile(r"[A-Za-zÀ-ÿ]")


def kata_to_hira(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # katakana -> hiragana
            out.append(chr(code - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def normalize_ja(text: str, fold_kana: bool = True) -> str:
    """Normaliza texto japones para comparacao."""
    text = unicodedata.normalize("NFKC", text or "")
    text = "".join(ch for ch in text if ch not in _PUNCT_KEEP_CHOUON)
    if fold_kana:
        text = kata_to_hira(text)
    return text.strip()


def has_japanese(text: str) -> bool:
    return bool(_KANA_RE.search(text or ""))


def looks_like_romaji(text: str) -> bool:
    return bool(_LATIN_RE.search(text or "")) and not has_japanese(text)


def levenshtein(a: str, b: str, cap: int = 3) -> int:
    """Distancia de edicao com corte em `cap` (retorna cap+1 se exceder)."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def accepted_forms(item) -> list[str]:
    """Todas as grafias aceitas para a palavra-chave (normalizadas)."""
    forms = {item.surface, item.reading}
    for alt in getattr(item, "alt", ()) or ():
        forms.add(alt)
    # forma com okurigana em kana no lugar do kanji ja esta coberta pela leitura
    return sorted({normalize_ja(f) for f in forms if f}, key=len, reverse=True)


def tolerance_for(form: str) -> int:
    """Tolerancia de edicao conforme o tamanho da forma.

    Para palavras de 1-2 caracteres qualquer troca muda a palavra (`私` vs `水`),
    entao a tolerancia e zero; a partir de 3 caracteres aceitamos um erro de
    okurigana/kana como "quase".
    """
    return 0 if len(form) <= 2 else 1


def _contains_near(answer: str, form: str, max_dist: int | None = None) -> tuple[bool, int]:
    """Procura `form` em `answer` tolerando `max_dist` edicoes."""
    if form in answer:
        return True, 0
    if max_dist is None:
        max_dist = tolerance_for(form)
    if max_dist <= 0:
        return False, 99
    n = len(form)
    best = max_dist + 1
    for width in (n - 1, n, n + 1):
        if width <= 0:
            continue
        for start in range(0, max(1, len(answer) - width + 1)):
            chunk = answer[start:start + width]
            if not chunk:
                continue
            d = levenshtein(chunk, form, cap=max_dist)
            if d < best:
                best = d
            if best == 0:
                return True, 0
    return (best <= max_dist), best


@dataclass
class Grade:
    keyword_ok: bool
    status: str                  # "acerto" | "quase" | "erro" | "sem_japones"
    distance: int
    suggested_rating: int
    similarity: float            # 0..1 comparado a traducao de referencia
    matched_form: str | None
    message: str
    diff_notes: list[str] = field(default_factory=list)


def grade_answer(
    item,
    answer: str,
    reference_ja: str,
    hint_used: bool = False,
    revealed: bool = False,
) -> Grade:
    """Compara a resposta do usuario com a frase de referencia."""
    raw = (answer or "").strip()
    norm = normalize_ja(raw)
    ref = normalize_ja(reference_ja)
    similarity = difflib.SequenceMatcher(None, norm, ref).ratio() if norm else 0.0

    if revealed:
        return Grade(False, "erro", 99, AGAIN, similarity, None,
                     "Resposta revelada — a palavra volta em breve.")

    if not raw:
        return Grade(False, "erro", 99, AGAIN, 0.0, None,
                     "Resposta vazia.")

    if looks_like_romaji(raw):
        return Grade(False, "sem_japones", 99, AGAIN, 0.0, None,
                     "Escreva em japonês (kanji/kana), não em romaji.")

    if not has_japanese(raw):
        return Grade(False, "sem_japones", 99, AGAIN, 0.0, None,
                     "Não encontrei caracteres japoneses na resposta.")

    best_form, best_dist, exact = None, 99, False
    for form in accepted_forms(item):
        ok, dist = _contains_near(norm, form)
        if dist < best_dist:
            best_dist, best_form = dist, form
        if ok and dist == 0:
            exact, best_form, best_dist = True, form, 0
            break

    notes: list[str] = []
    if similarity >= 0.92:
        notes.append("A frase inteira ficou praticamente igual à referência.")
    elif similarity >= 0.6:
        notes.append("A estrutura geral está próxima da referência.")

    if exact:
        if hint_used:
            rating = HARD
            msg = f"Correto: {item.surface} — mas você usou a dica, então conta como difícil."
        elif similarity >= 0.9:
            rating = EASY
            msg = f"Perfeito: {item.surface} ({item.reading})."
        else:
            rating = GOOD
            msg = f"Palavra-chave correta: {item.surface} ({item.reading})."
        return Grade(True, "acerto", 0, rating, similarity, best_form, msg, notes)

    if best_form and best_dist <= tolerance_for(best_form) and best_dist > 0:
        return Grade(
            True, "quase", best_dist, HARD, similarity, best_form,
            f"Quase: a forma esperada era {item.surface} ({item.reading}). "
            "Conta como difícil.",
            notes,
        )

    return Grade(
        False, "erro", best_dist, AGAIN, similarity, None,
        f"A forma esperada era {item.surface} ({item.reading}) — "
        f"{item.form_label}.",
        notes,
    )
