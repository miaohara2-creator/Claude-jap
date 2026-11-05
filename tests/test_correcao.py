"""Testes da correcao de respostas."""

import unittest

from nihongo.grading import grade_answer, kata_to_hira, levenshtein, normalize_ja
from nihongo.fsrs import AGAIN, EASY, GOOD, HARD
from nihongo.vocab import Vocabulary

V = Vocabulary.load()


class TestNormalizacao(unittest.TestCase):
    def test_pontuacao_e_espacos_somem(self):
        self.assertEqual(normalize_ja("私 は、水を 飲みます。"), "私は水を飲みます")

    def test_katakana_vira_hiragana(self):
        self.assertEqual(kata_to_hira("コーヒー"), "こーひー")

    def test_largura_normalizada(self):
        self.assertEqual(normalize_ja("ＡＢ１"), "AB1")

    def test_levenshtein(self):
        self.assertEqual(levenshtein("あい", "あい"), 0)
        self.assertEqual(levenshtein("あい", "あう"), 1)
        self.assertEqual(levenshtein("あい", "うえお", cap=2), 3)


class TestCorrecao(unittest.TestCase):
    def grade(self, item_id, resposta, referencia, **kw):
        return grade_answer(V.get(item_id), resposta, referencia, **kw)

    def test_acerto_exato_e_facil(self):
        g = self.grade("飲む|masu", "毎日水を飲みます。", "毎日水を飲みます。")
        self.assertTrue(g.keyword_ok)
        self.assertEqual(g.suggested_rating, EASY)

    def test_so_kana_tambem_acerta(self):
        g = self.grade("飲む|masu", "まいにちみずをのみます", "毎日水を飲みます。")
        self.assertTrue(g.keyword_ok)
        self.assertEqual(g.suggested_rating, GOOD)

    def test_forma_errada_do_mesmo_verbo_e_erro(self):
        g = self.grade("飲む|masen_deshita", "お茶を飲みました", "昨日お茶を飲みませんでした。")
        self.assertFalse(g.keyword_ok)
        self.assertEqual(g.suggested_rating, AGAIN)

    def test_quase_acerto_vira_dificil(self):
        g = self.grade("飲む|masen_deshita", "お茶を飲みませんでしだ",
                       "昨日お茶を飲みませんでした。")
        self.assertEqual(g.status, "quase")
        self.assertEqual(g.suggested_rating, HARD)

    def test_palavra_curta_nao_aceita_quase(self):
        g = self.grade("水|base", "これはお茶です", "これは水です。")
        self.assertEqual(g.status, "erro")

    def test_romaji_e_recusado(self):
        g = self.grade("水|base", "kore wa mizu desu", "これは水です。")
        self.assertEqual(g.status, "sem_japones")

    def test_resposta_vazia(self):
        self.assertEqual(self.grade("水|base", "", "これは水です。").suggested_rating, AGAIN)

    def test_dica_limita_a_dificil(self):
        g = self.grade("水|base", "これは水です。", "これは水です。", hint_used=True)
        self.assertTrue(g.keyword_ok)
        self.assertEqual(g.suggested_rating, HARD)

    def test_revelar_conta_como_erro(self):
        g = self.grade("水|base", "これは水です。", "これは水です。", revealed=True)
        self.assertFalse(g.keyword_ok)

    def test_escrita_alternativa_aceita(self):
        g = self.grade("椅子|base", "いすは新しいです", "椅子は新しいです。")
        self.assertTrue(g.keyword_ok)


if __name__ == "__main__":
    unittest.main()


class TestSaidaUTF8(unittest.TestCase):
    """O app imprime japonês; um console cp1252 não pode derrubá-lo."""

    def test_print_de_japones_em_console_cp1252(self):
        import io
        import sys

        from nihongo.config import configurar_saida_utf8

        original = sys.stdout
        buffer = io.BytesIO()
        sys.stdout = io.TextIOWrapper(buffer, encoding="cp1252")
        try:
            configurar_saida_utf8()
            print("日本語 — aprendizado incremental de japonês")
            sys.stdout.flush()
            # o buffer é fechado junto com o wrapper ao restaurar o stdout
            escrito = buffer.getvalue()
        finally:
            sys.stdout = original
        self.assertIn("日本語".encode("utf-8"), escrito)

    def test_funciona_com_fluxo_sem_reconfigure(self):
        import io
        import sys

        from nihongo.config import configurar_saida_utf8

        original = sys.stdout
        sys.stdout = io.StringIO()   # não tem .reconfigure
        try:
            configurar_saida_utf8()  # não pode levantar exceção
        finally:
            sys.stdout = original
