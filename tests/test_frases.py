"""Testes da geracao e validacao de frases (incluindo o caminho da Claude)."""

import random
import tempfile
import unittest
from pathlib import Path

from nihongo.claude_client import GenerationResult
from nihongo.db import Database
from nihongo.engine import Engine
from nihongo.generator import build_user_prompt, forbidden_surfaces, validate_sentence
from nihongo.templates import build_local_sentence, corpus_entries, first_gloss, gerund
from nihongo.vocab import Vocabulary

V = Vocabulary.load()


class ClienteFalso:
    """Cliente de Claude simulado, para testar o laco de geracao."""

    def __init__(self, respostas, model="falso"):
        self.respostas = list(respostas)
        self.model = model
        self.prompts = []

    def available(self):
        return True

    def generate_sentence(self, system, user):
        self.prompts.append(user)
        return GenerationResult(data=self.respostas.pop(0), model=self.model,
                                input_tokens=10, output_tokens=5)


class TestValidacao(unittest.TestCase):
    def setUp(self):
        self.alvo = V.get("飲む|masu")
        self.conhecidos = {"水|base", "毎日|base"}

    def frase(self, **kw):
        base = {
            "pt": "Todos os dias eu bebo água no trabalho.",
            "keyword_pt": "bebo",
            "ja": "毎日、水を飲みます。",
            "ja_reading": "まいにち、みずをのみます。",
            "words_used": ["毎日", "水", "飲む"],
            "note": "",
        }
        base.update(kw)
        return base

    def test_frase_valida(self):
        self.assertTrue(validate_sentence(self.frase(), self.alvo, V, self.conhecidos).ok)

    def test_rejeita_palavra_desconhecida(self):
        r = validate_sentence(self.frase(ja="毎日、お茶を飲みます。"), self.alvo, V, self.conhecidos)
        self.assertFalse(r.ok)
        self.assertIn("お茶", r.unknown_words)

    def test_rejeita_forma_errada(self):
        r = validate_sentence(self.frase(ja="毎日、水を飲みました。"), self.alvo, V, self.conhecidos)
        self.assertFalse(r.ok)

    def test_rejeita_destaque_fora_da_frase(self):
        r = validate_sentence(self.frase(keyword_pt="tomo"), self.alvo, V, self.conhecidos)
        self.assertFalse(r.ok)

    def test_rejeita_frase_curtissima(self):
        self.assertFalse(
            validate_sentence(self.frase(pt="Bebo água.", keyword_pt="Bebo"),
                              self.alvo, V, self.conhecidos).ok
        )

    def test_outras_formas_do_mesmo_lema_sao_permitidas(self):
        proibidas = forbidden_surfaces(V, self.conhecidos, self.alvo)
        self.assertNotIn("飲みました", proibidas)
        self.assertIn("お茶", proibidas)

    def test_auxiliar_dentro_da_forma_alvo_nao_e_proibida(self):
        alvo = V.get("飲む|te_imasu")          # 飲んでいます contém います
        proibidas = forbidden_surfaces(V, set(), alvo)
        self.assertNotIn("います", proibidas)

    def test_prompt_lista_a_forma_exigida(self):
        p = build_user_prompt(self.alvo, [V.get("水|base")])
        self.assertIn("飲みます", p)
        self.assertIn("水 (みず)", p)
        self.assertIn("presente polido", p)


class TestGeradorLocal(unittest.TestCase):
    def test_gerundio_e_glosa(self):
        self.assertEqual(gerund("beber"), "bebendo")
        self.assertEqual(gerund("ir"), "indo")
        self.assertEqual(first_gloss("ter; segurar"), "ter")
        self.assertEqual(first_gloss("alto (preço)"), "alto")

    def test_moldes_passam_na_validacao(self):
        rng = random.Random(0)
        for item_id in ("飲む|masu", "食べる|tai", "高い|adj_neg", "静か|adj_past", "水|base"):
            item = V.get(item_id)
            frase = build_local_sentence(item, set(), rng)
            self.assertIsNotNone(frase, item_id)
            self.assertTrue(validate_sentence(frase, item, V, set()).ok, item_id)

    def test_molde_so_usa_palavra_de_tempo_conhecida(self):
        item = V.get("飲む|te_imasu")
        frase = build_local_sentence(item, set(), random.Random(0))
        self.assertNotIn("今", frase["ja"])

    def test_corpus_e_valido(self):
        for item_id, entradas in corpus_entries().items():
            item = V.get(item_id)
            self.assertIsNotNone(item, item_id)
            for e in entradas:
                self.assertIn(item.surface, e["ja"])
                self.assertIn(e["keyword_pt"].lower(), e["pt"].lower())


class TestLacoDeGeracao(unittest.TestCase):
    def motor(self, cliente):
        db = Database(tempfile.mktemp(suffix=".db"))
        self.addCleanup(db.close)
        return Engine(db, V, client=cliente, rng=random.Random(0))

    def test_usa_a_frase_da_claude(self):
        boa = {
            "pt": "Sou eu na foto antiga da escola.", "keyword_pt": "eu",
            "ja": "私です。", "ja_reading": "わたしです。",
            "words_used": ["私"], "note": "nota",
        }
        eng = self.motor(ClienteFalso([boa]))
        rodada = eng.next_round()
        self.assertEqual(rodada.source, "claude")
        self.assertEqual(rodada.sentence["pt"], boa["pt"])

    def test_reenvia_o_erro_e_aceita_a_segunda_tentativa(self):
        ruim = {
            "pt": "Eu bebo chá todos os dias.", "keyword_pt": "eu",
            "ja": "私はお茶を飲みます。", "ja_reading": "", "words_used": [], "note": "",
        }
        boa = {
            "pt": "Sou eu quem mora nesta casa.", "keyword_pt": "eu",
            "ja": "私です。", "ja_reading": "わたしです。", "words_used": ["私"], "note": "",
        }
        cliente = ClienteFalso([ruim, boa])
        eng = self.motor(cliente)
        rodada = eng.next_round()
        self.assertEqual(rodada.source, "claude")
        self.assertEqual(len(cliente.prompts), 2)
        self.assertIn("REJEITADA PELO VALIDADOR", cliente.prompts[1])
        self.assertIn("お茶", cliente.prompts[1])

    def test_cai_para_o_gerador_local_quando_a_claude_falha(self):
        ruim = {"pt": "x", "keyword_pt": "x", "ja": "x", "ja_reading": "",
                "words_used": [], "note": ""}
        eng = self.motor(ClienteFalso([ruim, ruim, ruim]))
        rodada = eng.next_round()
        self.assertIn(rodada.source, ("corpus", "local"))
        self.assertTrue(any("gerador local" in a or "tentativas" in a for a in rodada.warnings))

    def test_contabiliza_tokens(self):
        boa = {"pt": "Sou eu mesmo na porta de casa.", "keyword_pt": "eu",
               "ja": "私です。", "ja_reading": "わたしです。", "words_used": ["私"], "note": ""}
        eng = self.motor(ClienteFalso([boa]))
        eng.next_round()
        self.assertEqual(eng.stats()["tokens"], {"entrada": 10, "saida": 5})


if __name__ == "__main__":
    unittest.main()
