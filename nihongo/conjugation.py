"""Conjugacao de verbos e adjetivos japoneses.

Cada forma conjugada vira um *item de vocabulario independente* (com cartao
FSRS proprio), conforme o pedido: "se a palavra for um verbo, considerar cada
forma do verbo como uma palavra chave".

A conjugacao e feita em paralelo na escrita (kanji + okurigana) e na leitura
(kana), aproveitando o fato de que a okurigana final de um verbo e identica
nas duas representacoes.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tabelas de kana
# ---------------------------------------------------------------------------

_U_ROW = "うくぐすずつづぬふぶぷむる"
_A_ROW = "わかがさざただなはばぱまら"
_I_ROW = "いきぎしじちぢにひびぴみり"
_E_ROW = "えけげせぜてでねへべぺめれ"
_O_ROW = "おこごそぞとどのほぼぽもろ"

_ROW = {
    "a": dict(zip(_U_ROW, _A_ROW)),
    "i": dict(zip(_U_ROW, _I_ROW)),
    "e": dict(zip(_U_ROW, _E_ROW)),
    "o": dict(zip(_U_ROW, _O_ROW)),
}

#: terminacao da forma て para cada kana final de verbo godan
_TE_GODAN = {
    "う": "って", "つ": "って", "る": "って",
    "む": "んで", "ぶ": "んで", "ぬ": "んで",
    "く": "いて", "ぐ": "いで",
    "す": "して",
}

#: verbos godan/irregulares com forma て excepcional (chave = leitura)
_TE_EXCEPTIONS = {"いく": "いって", "ゆく": "ゆいて"}

# Tipos de palavra
VERB_GODAN = "verb-godan"
VERB_ICHIDAN = "verb-ichidan"
VERB_SURU = "verb-suru"      # 〜する (composto) e する puro
VERB_KURU = "verb-kuru"      # 来る
VERB_ARU = "verb-aru"        # ある (negativo irregular)
ADJ_I = "adj-i"
ADJ_NA = "adj-na"
VERB_TYPES = {VERB_GODAN, VERB_ICHIDAN, VERB_SURU, VERB_KURU, VERB_ARU}
ADJ_TYPES = {ADJ_I, ADJ_NA}


# ---------------------------------------------------------------------------
# Catalogo de formas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormSpec:
    """Metadados de uma forma gramatical."""

    form_id: str
    pt_label: str          # descricao curta em portugues
    pt_hint: str           # como a frase em portugues sinaliza essa forma
    level: str             # nivel JLPT minimo para introduzir a forma
    order: int             # ordem pedagogica dentro do nivel


VERB_FORMS: tuple[FormSpec, ...] = (
    FormSpec("masu", "presente polido (〜ます)", "ação habitual ou futura, registro polido", "N5", 1),
    FormSpec("dict", "forma do dicionário (informal)", "fala informal, oração subordinada", "N5", 2),
    FormSpec("masen", "negativo polido (〜ません)", "negação polida", "N5", 3),
    FormSpec("mashita", "passado polido (〜ました)", "ação concluída, registro polido", "N5", 4),
    FormSpec("te", "forma て", "ligação de orações, pedido com ください", "N5", 5),
    FormSpec("te_imasu", "progressivo (〜ています)", "ação em andamento ou estado contínuo", "N5", 6),
    FormSpec("nai", "negativo informal (〜ない)", "negação informal", "N5", 7),
    FormSpec("ta", "passado informal (〜た)", "passado informal", "N5", 8),
    FormSpec("masen_deshita", "passado negativo polido (〜ませんでした)", "negação no passado, polido", "N5", 9),
    FormSpec("tai", "desejo (〜たい)", "\"quero ...\"", "N5", 10),
    FormSpec("masho", "convite (〜ましょう)", "\"vamos ...\"", "N5", 11),
    FormSpec("nakatta", "passado negativo informal (〜なかった)", "negação no passado, informal", "N4", 1),
    FormSpec("potential", "potencial (poder 〜)", "\"consigo / posso ...\"", "N4", 2),
    FormSpec("tara", "condicional 〜たら", "\"se / quando ...\"", "N4", 3),
    FormSpec("ba", "condicional 〜ば", "\"se ...\" (condição)", "N4", 4),
    FormSpec("volitional", "volitivo informal (〜よう)", "intenção, \"vou ...\" informal", "N4", 5),
    FormSpec("passive", "passiva (〜られる)", "\"ser 〜do\"", "N4", 6),
    FormSpec("imperative", "imperativo (〜ろ/〜え)", "ordem direta", "N3", 1),
    FormSpec("causative", "causativa (〜させる)", "\"fazer/deixar alguém 〜\"", "N3", 2),
    FormSpec("causative_passive", "causativa-passiva (〜させられる)", "\"ser obrigado a 〜\"", "N3", 3),
    FormSpec("nakereba", "〜なければ (se não)", "\"se não ...\" / obrigação", "N3", 4),
    FormSpec("humble", "humilde (お〜します)", "registro humilde (kenjougo)", "N2", 1),
)

ADJ_I_FORMS: tuple[FormSpec, ...] = (
    FormSpec("adj_plain", "forma básica (〜い)", "atributo no presente", "N5", 1),
    FormSpec("adj_neg", "negativo (〜くない)", "negação de atributo", "N5", 2),
    FormSpec("adj_past", "passado (〜かった)", "atributo no passado", "N5", 3),
    FormSpec("adj_past_neg", "passado negativo (〜くなかった)", "negação no passado", "N4", 1),
    FormSpec("adj_adverb", "advérbio (〜く)", "modifica um verbo", "N4", 2),
    FormSpec("adj_te", "forma くて", "ligação de atributos", "N4", 3),
)

ADJ_NA_FORMES: tuple[FormSpec, ...] = (
    FormSpec("adj_plain", "forma básica (〜です)", "atributo no presente", "N5", 1),
    FormSpec("adj_neg", "negativo (〜じゃありません)", "negação de atributo", "N5", 2),
    FormSpec("adj_past", "passado (〜でした)", "atributo no passado", "N5", 3),
    FormSpec("adj_te", "forma で", "ligação de atributos", "N4", 2),
)

FORM_SPECS: dict[str, FormSpec] = {}
for _group in (VERB_FORMS, ADJ_I_FORMS, ADJ_NA_FORMES):
    for _spec in _group:
        FORM_SPECS.setdefault(_spec.form_id, _spec)


@dataclass(frozen=True)
class Conjugation:
    form_id: str
    surface: str   # escrita (kanji + okurigana)
    reading: str   # leitura em kana
    spec: FormSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_tail(surface: str, reading: str, tail_len: int = 1) -> tuple[str, str]:
    """Remove `tail_len` kana do fim da escrita e da leitura."""
    return surface[:-tail_len], reading[:-tail_len]


def _shift(kana: str, row: str) -> str:
    return _ROW[row].get(kana, kana)


def _te_stem(surface: str, reading: str, voiced: bool) -> tuple[str, str]:
    """Radical + terminacao て/た de um verbo godan (trata 行く -> 行って)."""
    base_s, base_r = _split_tail(surface, reading)
    if reading in _TE_EXCEPTIONS:
        te = "って"
    else:
        te = _TE_GODAN[reading[-1]]
    if voiced:
        te = te[:-1] + ("だ" if te[-1] == "で" else "た")
    return base_s + te, base_r + te


# ---------------------------------------------------------------------------
# Conjugacao de verbos
# ---------------------------------------------------------------------------


def _godan(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    last = reading[-1]
    s_stem, r_stem = _split_tail(surface, reading)

    def with_row(row: str, suffix: str) -> tuple[str, str]:
        k = _shift(last, row)
        return s_stem + k + suffix, r_stem + k + suffix

    i_s, i_r = with_row("i", "")
    a_s, a_r = with_row("a", "")
    e_s, e_r = with_row("e", "")
    o_s, o_r = with_row("o", "")
    te_s, te_r = _te_stem(surface, reading, voiced=False)
    ta_s, ta_r = _te_stem(surface, reading, voiced=True)

    return {
        "dict": (surface, reading),
        "masu": (i_s + "ます", i_r + "ます"),
        "masen": (i_s + "ません", i_r + "ません"),
        "mashita": (i_s + "ました", i_r + "ました"),
        "masen_deshita": (i_s + "ませんでした", i_r + "ませんでした"),
        "masho": (i_s + "ましょう", i_r + "ましょう"),
        "tai": (i_s + "たい", i_r + "たい"),
        "humble": ("お" + i_s + "します", "お" + i_r + "します"),
        "te": (te_s, te_r),
        "te_imasu": (te_s + "います", te_r + "います"),
        "ta": (ta_s, ta_r),
        "tara": (ta_s + "ら", ta_r + "ら"),
        "nai": (a_s + "ない", a_r + "ない"),
        "nakatta": (a_s + "なかった", a_r + "なかった"),
        "nakereba": (a_s + "なければ", a_r + "なければ"),
        "passive": (a_s + "れる", a_r + "れる"),
        "causative": (a_s + "せる", a_r + "せる"),
        "causative_passive": (a_s + "せられる", a_r + "せられる"),
        "potential": (e_s + "る", e_r + "る"),
        "ba": (e_s + "ば", e_r + "ば"),
        "imperative": (e_s, e_r),
        "volitional": (o_s + "う", o_r + "う"),
    }


def _ichidan(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    s, r = _split_tail(surface, reading)  # remove る
    return {
        "dict": (surface, reading),
        "masu": (s + "ます", r + "ます"),
        "masen": (s + "ません", r + "ません"),
        "mashita": (s + "ました", r + "ました"),
        "masen_deshita": (s + "ませんでした", r + "ませんでした"),
        "masho": (s + "ましょう", r + "ましょう"),
        "tai": (s + "たい", r + "たい"),
        "humble": ("お" + s + "します", "お" + r + "します"),
        "te": (s + "て", r + "て"),
        "te_imasu": (s + "ています", r + "ています"),
        "ta": (s + "た", r + "た"),
        "tara": (s + "たら", r + "たら"),
        "nai": (s + "ない", r + "ない"),
        "nakatta": (s + "なかった", r + "なかった"),
        "nakereba": (s + "なければ", r + "なければ"),
        "passive": (s + "られる", r + "られる"),
        "causative": (s + "させる", r + "させる"),
        "causative_passive": (s + "させられる", r + "させられる"),
        "potential": (s + "られる", r + "られる"),
        "ba": (s + "れば", r + "れば"),
        "imperative": (s + "ろ", r + "ろ"),
        "volitional": (s + "よう", r + "よう"),
    }


def _suru(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    # 勉強する -> prefixo 勉強 ; する puro -> prefixo vazio
    s, r = surface[:-2], reading[:-2]
    def pair(suffix_kana: str) -> tuple[str, str]:
        return s + suffix_kana, r + suffix_kana
    return {
        "dict": (surface, reading),
        "masu": pair("します"),
        "masen": pair("しません"),
        "mashita": pair("しました"),
        "masen_deshita": pair("しませんでした"),
        "masho": pair("しましょう"),
        "tai": pair("したい"),
        "humble": (("お" + s + "します") if s else "いたします",
                   ("お" + r + "します") if r else "いたします"),
        "te": pair("して"),
        "te_imasu": pair("しています"),
        "ta": pair("した"),
        "tara": pair("したら"),
        "nai": pair("しない"),
        "nakatta": pair("しなかった"),
        "nakereba": pair("しなければ"),
        "passive": pair("される"),
        "causative": pair("させる"),
        "causative_passive": pair("させられる"),
        "potential": pair("できる"),
        "ba": pair("すれば"),
        "imperative": pair("しろ"),
        "volitional": pair("しよう"),
    }


def _kuru(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    # 来る / くる  -> o kanji 来 cobre as leituras き/こ/く
    kanji = surface.endswith("来る")
    pre = surface[:-2] if kanji else ""
    pre_r = reading[:-2]

    def pair(kanji_tail: str, kana_tail: str) -> tuple[str, str]:
        if kanji:
            return pre + "来" + kanji_tail, pre_r + kana_tail
        return pre_r + kana_tail, pre_r + kana_tail

    return {
        "dict": (surface, reading),
        "masu": pair("ます", "きます"),
        "masen": pair("ません", "きません"),
        "mashita": pair("ました", "きました"),
        "masen_deshita": pair("ませんでした", "きませんでした"),
        "masho": pair("ましょう", "きましょう"),
        "tai": pair("たい", "きたい"),
        "humble": ("参ります", "まいります"),
        "te": pair("て", "きて"),
        "te_imasu": pair("ています", "きています"),
        "ta": pair("た", "きた"),
        "tara": pair("たら", "きたら"),
        "nai": pair("ない", "こない"),
        "nakatta": pair("なかった", "こなかった"),
        "nakereba": pair("なければ", "こなければ"),
        "passive": pair("られる", "こられる"),
        "causative": pair("させる", "こさせる"),
        "causative_passive": pair("させられる", "こさせられる"),
        "potential": pair("られる", "こられる"),
        "ba": pair("れば", "くれば"),
        "imperative": pair("い", "こい"),
        "volitional": pair("よう", "こよう"),
    }


def _aru(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    forms = _godan(surface, reading)
    # ある nao tem あらない: o negativo e ない
    forms["nai"] = ("ない", "ない")
    forms["nakatta"] = ("なかった", "なかった")
    forms["nakereba"] = ("なければ", "なければ")
    # formas que nao ocorrem naturalmente com ある
    for dead in ("passive", "causative", "causative_passive", "imperative",
                 "tai", "volitional", "humble", "potential", "masho", "te_imasu"):
        forms.pop(dead, None)
    return forms


_VERB_ENGINES = {
    VERB_GODAN: _godan,
    VERB_ICHIDAN: _ichidan,
    VERB_SURU: _suru,
    VERB_KURU: _kuru,
    VERB_ARU: _aru,
}


# ---------------------------------------------------------------------------
# Conjugacao de adjetivos
# ---------------------------------------------------------------------------


def _adj_i(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    s, r = _split_tail(surface, reading)  # remove い
    if reading == "いい":  # いい / 良い
        s, r = surface[:-2] + "良", "よ"
        return {
            "adj_plain": (surface, reading),
            "adj_neg": ("良くない", "よくない"),
            "adj_past": ("良かった", "よかった"),
            "adj_past_neg": ("良くなかった", "よくなかった"),
            "adj_adverb": ("良く", "よく"),
            "adj_te": ("良くて", "よくて"),
        }
    return {
        "adj_plain": (surface, reading),
        "adj_neg": (s + "くない", r + "くない"),
        "adj_past": (s + "かった", r + "かった"),
        "adj_past_neg": (s + "くなかった", r + "くなかった"),
        "adj_adverb": (s + "く", r + "く"),
        "adj_te": (s + "くて", r + "くて"),
    }


def _adj_na(surface: str, reading: str) -> dict[str, tuple[str, str]]:
    return {
        "adj_plain": (surface + "です", reading + "です"),
        "adj_neg": (surface + "じゃありません", reading + "じゃありません"),
        "adj_past": (surface + "でした", reading + "でした"),
        "adj_te": (surface + "で", reading + "で"),
    }


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

LEVEL_ORDER = ("N5", "N4", "N3", "N2", "N1")


def level_index(level: str) -> int:
    try:
        return LEVEL_ORDER.index(level)
    except ValueError:
        return len(LEVEL_ORDER) - 1


def inflects(word_type: str) -> bool:
    return word_type in VERB_TYPES or word_type in ADJ_TYPES


def form_catalog(word_type: str) -> tuple[FormSpec, ...]:
    if word_type in VERB_TYPES:
        return VERB_FORMS
    if word_type == ADJ_I:
        return ADJ_I_FORMS
    if word_type == ADJ_NA:
        return ADJ_NA_FORMES
    return ()


def conjugate(surface: str, reading: str, word_type: str) -> list[Conjugation]:
    """Devolve todas as formas conjugadas disponiveis para a palavra."""
    if word_type in _VERB_ENGINES:
        table = _VERB_ENGINES[word_type](surface, reading)
    elif word_type == ADJ_I:
        table = _adj_i(surface, reading)
    elif word_type == ADJ_NA:
        table = _adj_na(surface, reading)
    else:
        return []

    out: list[Conjugation] = []
    for spec in form_catalog(word_type):
        pair = table.get(spec.form_id)
        if pair is None:
            continue
        out.append(Conjugation(spec.form_id, pair[0], pair[1], spec))
    return out


def conjugate_one(surface: str, reading: str, word_type: str, form_id: str) -> Conjugation | None:
    for c in conjugate(surface, reading, word_type):
        if c.form_id == form_id:
            return c
    return None
