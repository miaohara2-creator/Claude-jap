"""Testes do motor de conjugacao."""

import unittest

from nihongo.conjugation import conjugate, conjugate_one
from nihongo.vocab import Vocabulary

ESPERADO = {
    ("飲む", "のむ", "verb-godan"): {
        "masu": "飲みます", "te": "飲んで", "ta": "飲んだ", "nai": "飲まない",
        "potential": "飲める", "volitional": "飲もう", "passive": "飲まれる",
        "causative": "飲ませる", "imperative": "飲め", "ba": "飲めば",
        "masen_deshita": "飲みませんでした", "tara": "飲んだら",
    },
    ("書く", "かく", "verb-godan"): {"te": "書いて", "ta": "書いた", "potential": "書ける"},
    ("泳ぐ", "およぐ", "verb-godan"): {"te": "泳いで", "ta": "泳いだ"},
    ("話す", "はなす", "verb-godan"): {"te": "話して", "masu": "話します"},
    ("待つ", "まつ", "verb-godan"): {"te": "待って", "nai": "待たない"},
    ("遊ぶ", "あそぶ", "verb-godan"): {"te": "遊んで", "ta": "遊んだ"},
    ("買う", "かう", "verb-godan"): {"te": "買って", "nai": "買わない"},
    ("行く", "いく", "verb-godan"): {"te": "行って", "ta": "行った"},  # irregular
    ("食べる", "たべる", "verb-ichidan"): {
        "masu": "食べます", "te": "食べて", "nai": "食べない",
        "potential": "食べられる", "causative": "食べさせる", "imperative": "食べろ",
    },
    ("する", "する", "verb-suru"): {
        "masu": "します", "te": "して", "nai": "しない", "potential": "できる",
        "passive": "される", "volitional": "しよう",
    },
    ("勉強する", "べんきょうする", "verb-suru"): {
        "masu": "勉強します", "ta": "勉強した", "potential": "勉強できる",
    },
    ("来る", "くる", "verb-kuru"): {"masu": "来ます", "te": "来て", "nai": "来ない"},
    ("高い", "たかい", "adj-i"): {
        "adj_neg": "高くない", "adj_past": "高かった", "adj_adverb": "高く",
    },
    ("いい", "いい", "adj-i"): {"adj_neg": "良くない", "adj_past": "良かった"},
    ("静か", "しずか", "adj-na"): {"adj_plain": "静かです", "adj_past": "静かでした"},
}

LEITURAS = {
    ("来る", "くる", "verb-kuru"): {"masu": "きます", "nai": "こない", "ba": "くれば"},
    ("飲む", "のむ", "verb-godan"): {"te": "のんで", "causative": "のませる"},
}


class TestConjugacao(unittest.TestCase):
    def test_formas_escritas(self):
        for (w, r, t), formas in ESPERADO.items():
            for form_id, esperado in formas.items():
                c = conjugate_one(w, r, t, form_id)
                self.assertIsNotNone(c, f"{w} não tem a forma {form_id}")
                self.assertEqual(c.surface, esperado, f"{w} / {form_id}")

    def test_leituras(self):
        for (w, r, t), formas in LEITURAS.items():
            for form_id, esperado in formas.items():
                self.assertEqual(conjugate_one(w, r, t, form_id).reading, esperado)

    def test_aru_tem_negativo_irregular(self):
        self.assertEqual(conjugate_one("ある", "ある", "verb-aru", "nai").surface, "ない")
        self.assertIsNone(conjugate_one("ある", "ある", "verb-aru", "imperative"))

    def test_leitura_e_escrita_tem_o_mesmo_numero_de_formas(self):
        for (w, r, t) in ESPERADO:
            for c in conjugate(w, r, t):
                self.assertTrue(c.surface and c.reading)

    def test_todo_o_vocabulario_conjuga_sem_erro(self):
        v = Vocabulary.load()
        self.assertGreater(len(v), 3000)
        for item in v.items:
            self.assertTrue(item.surface)
            self.assertTrue(item.reading)
            self.assertIn(item.level, ("N5", "N4", "N3", "N2", "N1"))

    def test_cada_forma_e_um_item_distinto(self):
        v = Vocabulary.load()
        formas = {i.item_id for i in v.items if i.lemma == "飲む"}
        self.assertGreater(len(formas), 15)
        self.assertIn("飲む|masu", formas)
        self.assertIn("飲む|causative_passive", formas)

    def test_formas_avancadas_sobem_de_nivel(self):
        v = Vocabulary.load()
        self.assertEqual(v.get("飲む|masu").level, "N5")
        self.assertEqual(v.get("飲む|causative").level, "N3")


if __name__ == "__main__":
    unittest.main()
