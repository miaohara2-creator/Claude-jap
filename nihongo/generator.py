"""Construcao dos prompts e validacao das frases geradas.

Invariante central do app: **a frase pode conter no maximo uma palavra que o
usuario ainda nao conhece** -- a palavra-chave da rodada. A validacao abaixo
e objetiva (nao depende do auto-relato do modelo): varremos a frase japonesa
procurando grafias de itens do vocabulario que ainda nao foram apresentados.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .grading import normalize_ja
from .vocab import Item, Vocabulary

#: Palavras funcionais sempre liberadas (particulas, copula, demonstrativos,
#: numerais basicos). Nao contam como "palavra nova".
FREE_WORDS: tuple[str, ...] = (
    "は", "が", "を", "に", "で", "と", "も", "の", "へ", "や", "から", "まで",
    "より", "ね", "よ", "か", "な", "ので", "けど", "し", "だけ", "ずつ",
    "です", "でした", "ですか", "じゃありません", "ではありません", "だ", "である",
    "ます", "ません", "ました", "ませんでした",
    "これ", "それ", "あれ", "この", "その", "あの", "ここ", "そこ", "あそこ",
    "はい", "いいえ", "さん", "ちゃん", "くん",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "一つ", "二つ", "三つ", "一人", "二人", "一枚", "一本", "一冊", "一回",
)

SYSTEM_PROMPT = """\
Você é professor de japonês de um aluno brasileiro adulto. O aplicativo mostra \
uma frase em PORTUGUÊS e o aluno a traduz para o japonês. A frase é construída \
em volta de UMA única palavra-chave nova; todo o resto já foi estudado.

REGRAS ABSOLUTAS

1. UMA PALAVRA NOVA. A tradução japonesa de referência pode usar:
   (a) a palavra-chave pedida, exatamente na forma indicada;
   (b) palavras da lista "VOCABULÁRIO JÁ CONHECIDO" do pedido;
   (c) as palavras funcionais liberadas (partículas, copula です/でした, \
これ/それ/あれ, numerais simples, はい/いいえ, sufixos de tratamento).
   Nenhuma outra palavra de conteúdo é permitida — nem palavras "fáceis", nem \
nomes próprios, nem empréstimos do inglês. Se a lista conhecida for curta, \
escreva uma frase curta: isso é esperado nas primeiras rodadas.

2. FORMA EXATA. A palavra-chave aparece em `ja` exatamente na grafia indicada \
em "FORMA EXIGIDA". Não troque por outra conjugação, não acrescente nem remova \
a okurigana, não use kana onde o pedido traz kanji.

3. A FRASE EM PORTUGUÊS DEVE EXIGIR AQUELA FORMA. O tempo, a polidez, a \
negação e o aspecto precisam ficar claros em português, sem ambiguidade: \
quem lê a frase em português deve ser capaz de escolher a forma japonesa certa. \
Use marcas explícitas quando necessário ("ontem", "ainda não", "todos os dias", \
"você poderia", "vamos", "eu quero", "fui obrigado a").

4. CONTEXTO NOS DOIS IDIOMAS. A frase precisa descrever uma situação concreta e \
plausível (casa, trabalho, escola, viagem, saúde, amizade) e soar natural nas \
duas línguas. Nada de frases de manual sem contexto ("Isto é uma caneta."), \
nada de poesia, nada de listas.

5. PORTUGUÊS BRASILEIRO natural, uma frase só (pode ter vírgula), entre 4 e 16 \
palavras. Sem reticências, sem parênteses, sem o japonês embutido.

6. `keyword_pt` é o trecho EXATO da frase em português que corresponde à \
palavra-chave — copiado caractere por caractere de `pt`, com a mesma \
acentuação e flexão (é o que o app vai destacar na tela). Pode ter mais de uma \
palavra ("não bebi", "vou estudar").

7. `ja_reading` é a mesma frase de `ja`, inteiramente em kana.

8. `words_used` lista, na forma de dicionário, todas as palavras de conteúdo \
usadas em `ja` (inclusive a palavra-chave). Não inclua partículas.

9. `note` explica em uma ou duas frases, em português, por que aquela forma \
japonesa é a correta ali.
"""


@dataclass
class Validation:
    ok: bool
    problems: list[str] = field(default_factory=list)
    unknown_words: list[str] = field(default_factory=list)


def build_user_prompt(
    item: Item,
    known: list[Item],
    recent_sentences: list[str] | None = None,
    known_limit: int = 450,
) -> str:
    """Monta a parte variavel do pedido."""
    lines = [
        "PALAVRA-CHAVE NOVA DESTA RODADA",
        f"- forma exigida (use exatamente assim em `ja`): {item.surface}",
        f"- leitura: {item.reading}",
        f"- significado em português: {item.pt}",
        f"- lema: {item.lemma} ({item.lemma_reading})",
        f"- classe: {_type_label(item.word_type)}",
        f"- FORMA EXIGIDA: {item.form_label}",
    ]
    if item.form_hint:
        lines.append(f"- como o português deve sinalizar essa forma: {item.form_hint}")
    lines.append(f"- nível JLPT: {item.level}")
    lines.append("")

    if known:
        shown = _select_known(known, known_limit)
        lines.append(
            f"VOCABULÁRIO JÁ CONHECIDO ({len(shown)} de {len(known)} formas disponíveis)"
        )
        lines.append(
            "Cada linha é: grafia (leitura) = significado. Use somente estas formas; "
            "para verbos e adjetivos use exatamente a forma listada."
        )
        for it in shown:
            lines.append(f"- {it.surface} ({it.reading}) = {it.pt}")
        if len(shown) < len(known):
            lines.append(
                f"- (… e {len(known) - len(shown)} outras formas já estudadas; "
                "se precisar, prefira as listadas acima)"
            )
    else:
        lines.append("VOCABULÁRIO JÁ CONHECIDO")
        lines.append(
            "- (vazio: esta é a primeira palavra do aluno; escreva uma frase "
            "mínima usando só a palavra-chave e palavras funcionais)"
        )
    lines.append("")

    if recent_sentences:
        lines.append("FRASES JÁ USADAS RECENTEMENTE (escreva algo diferente destas)")
        for s in recent_sentences[:8]:
            lines.append(f"- {s}")
        lines.append("")

    lines.append(
        "Escreva a frase da rodada seguindo todas as regras. Responda apenas o JSON."
    )
    return "\n".join(lines)


def _type_label(word_type: str) -> str:
    return {
        "verb-godan": "verbo godan (五段)",
        "verb-ichidan": "verbo ichidan (一段)",
        "verb-suru": "verbo composto com する",
        "verb-kuru": "verbo irregular 来る",
        "verb-aru": "verbo irregular ある",
        "adj-i": "adjetivo-i",
        "adj-na": "adjetivo-na",
        "noun": "substantivo",
        "adverb": "advérbio",
        "pronoun": "pronome",
        "conjunction": "conjunção",
    }.get(word_type, word_type)


def _select_known(known: list[Item], limit: int) -> list[Item]:
    """Mantem o prompt limitado: prioriza itens mais basicos e variados."""
    if len(known) <= limit:
        return known
    ordered = sorted(known, key=lambda it: it.sort_key)
    head = ordered[: limit // 2]
    tail = ordered[limit // 2:]
    step = max(1, len(tail) // (limit - len(head)))
    return head + tail[::step][: limit - len(head)]


# ---------------------------------------------------------------------------
# Validacao
# ---------------------------------------------------------------------------


def forbidden_surfaces(
    vocab: Vocabulary, known_ids: set[str], target: Item
) -> dict[str, str]:
    """Grafias de itens ainda nao apresentados (-> nao podem aparecer na frase).

    Grafias que sao subcadeia da propria palavra-chave sao ignoradas: `います`
    faz parte de `飲んでいます`, por exemplo.
    """
    target_norm = normalize_ja(target.surface)
    out: dict[str, str] = {}
    for it in vocab.items:
        if it.item_id in known_ids or it.item_id == target.item_id:
            continue
        if it.lemma == target.lemma:
            continue  # outras formas do mesmo lema nao sao "palavra nova"
        surf = normalize_ja(it.surface)
        if len(surf) < 2 or surf in target_norm or surf in FREE_WORDS:
            continue
        out.setdefault(surf, it.item_id)
    return out


def validate_sentence(
    data: dict,
    item: Item,
    vocab: Vocabulary,
    known_ids: set[str],
) -> Validation:
    """Checa as invariantes do app sobre a frase gerada."""
    problems: list[str] = []
    unknown: list[str] = []

    pt = (data.get("pt") or "").strip()
    ja = (data.get("ja") or "").strip()
    keyword_pt = (data.get("keyword_pt") or "").strip()

    if not pt or not ja:
        return Validation(False, ["frase vazia"])

    ja_norm = normalize_ja(ja)

    # 1. a palavra-chave precisa estar na forma exigida
    if normalize_ja(item.surface) not in ja_norm:
        problems.append(
            f"a forma exigida {item.surface} não aparece na tradução japonesa"
        )

    # 2. o trecho destacavel precisa existir na frase em portugues
    if not keyword_pt:
        problems.append("keyword_pt vazio")
    elif keyword_pt.lower() not in pt.lower():
        problems.append(f"keyword_pt ({keyword_pt!r}) não é um trecho exato de `pt`")

    # 3. nenhuma outra palavra do vocabulario pode estar desconhecida
    for surf, item_id in forbidden_surfaces(vocab, known_ids, item).items():
        if surf in ja_norm:
            unknown.append(surf)
    if unknown:
        problems.append(
            "a frase usa palavra(s) que o aluno ainda não aprendeu: "
            + ", ".join(sorted(set(unknown))[:6])
        )

    # 4. tamanho da frase em portugues
    n_words = len(pt.split())
    if n_words < 3:
        problems.append("frase em português muito curta")
    elif n_words > 22:
        problems.append("frase em português longa demais")

    return Validation(not problems, problems, sorted(set(unknown)))
