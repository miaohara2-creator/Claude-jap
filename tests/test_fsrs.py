"""Testes do agendador FSRS-5."""

import unittest
from datetime import datetime, timedelta, timezone

from nihongo.fsrs import (
    AGAIN, EASY, FSRS, GOOD, HARD, REVIEW, Card,
    interval_for_retention, retrievability,
)

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


class TestFormulas(unittest.TestCase):
    def test_retrievabilidade_decai(self):
        self.assertAlmostEqual(retrievability(0, 10), 1.0, places=6)
        self.assertAlmostEqual(retrievability(10, 10), 0.9, places=6)
        self.assertLess(retrievability(30, 10), retrievability(10, 10))

    def test_intervalo_bate_com_a_retencao(self):
        for s in (1.0, 7.5, 60.0, 365.0):
            i = interval_for_retention(s, 0.9)
            self.assertAlmostEqual(retrievability(i, s), 0.9, places=6)

    def test_retencao_maior_encurta_intervalo(self):
        self.assertLess(interval_for_retention(30, 0.95), interval_for_retention(30, 0.85))


class TestAgendamento(unittest.TestCase):
    def setUp(self):
        self.f = FSRS()

    def test_primeira_nota_define_estabilidade_inicial(self):
        for rating, peso in ((AGAIN, 0), (HARD, 1), (GOOD, 2), (EASY, 3)):
            c = self.f.review(Card(), rating, T0)
            self.assertAlmostEqual(c.stability, self.f.w[peso], places=6)
            self.assertEqual(c.reps, 1)

    def test_intervalos_crescem_com_acertos(self):
        card, agora, intervalos = Card(), T0, []
        for _ in range(6):
            card = self.f.review(card, GOOD, agora)
            intervalos.append(card.scheduled_days)
            agora = card.due
        apos_aprendizado = [i for i in intervalos if i >= 1]
        self.assertEqual(apos_aprendizado, sorted(apos_aprendizado))
        self.assertGreater(apos_aprendizado[-1], apos_aprendizado[0])

    def test_erro_reduz_estabilidade_e_conta_lapso(self):
        card, agora = Card(), T0
        for _ in range(3):
            card = self.f.review(card, GOOD, agora)
            agora = card.due
        antes = card.stability
        card = self.f.review(card, AGAIN, agora)
        self.assertLess(card.stability, antes)
        self.assertEqual(card.lapses, 1)
        self.assertEqual(card.state, "relearning")

    def test_dificuldade_fica_na_faixa(self):
        card = Card()
        agora = T0
        for rating in (AGAIN, AGAIN, AGAIN, EASY, EASY, EASY, AGAIN, GOOD):
            card = self.f.review(card, rating, agora)
            agora = card.due
            self.assertGreaterEqual(card.difficulty, 1.0)
            self.assertLessEqual(card.difficulty, 10.0)

    def test_facil_agenda_mais_longe_que_dificil(self):
        base = self.f.review(Card(), GOOD, T0)
        depois = base.due + timedelta(days=1)
        self.assertGreater(
            self.f.review(base, EASY, depois).scheduled_days,
            self.f.review(base, HARD, depois).scheduled_days,
        )

    def test_revisao_no_mesmo_dia_usa_formula_curta(self):
        card = self.f.review(Card(), GOOD, T0)
        card = self.f.review(card, GOOD, T0 + timedelta(minutes=10))
        self.assertEqual(card.state, REVIEW)
        self.assertGreater(card.stability, 0)

    def test_previsao_cobre_as_quatro_notas(self):
        p = self.f.preview(self.f.review(Card(), GOOD, T0), T0 + timedelta(days=5))
        self.assertEqual(sorted(p), [1, 2, 3, 4])
        self.assertLess(p[AGAIN], p[GOOD])
        self.assertLess(p[GOOD], p[EASY])

    def test_nota_invalida(self):
        with self.assertRaises(ValueError):
            self.f.review(Card(), 7, T0)

    def test_pesos_invalidos(self):
        with self.assertRaises(ValueError):
            FSRS(weights=(1.0, 2.0))


if __name__ == "__main__":
    unittest.main()
