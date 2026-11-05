"""Implementacao do algoritmo FSRS-5 (Free Spaced Repetition Scheduler).

Referencia: https://github.com/open-spaced-repetition/fsrs4anki/wiki
Usa os 19 pesos padrao do FSRS-5. Todas as formulas sao implementadas em
termos de *dias* (fracionarios), de forma que revisoes no mesmo dia tambem
sejam tratadas corretamente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Pesos padrao do FSRS-5 (19 parametros).
DEFAULT_WEIGHTS: tuple[float, ...] = (
    0.40255, 1.18385, 3.173, 15.69105,   # w0..w3  -> estabilidade inicial por nota
    7.1949, 0.5345,                      # w4,w5   -> dificuldade inicial
    1.4604, 0.0046,                      # w6,w7   -> variacao/reversao da dificuldade
    1.54575, 0.1192, 1.01925,            # w8..w10 -> estabilidade apos acerto
    1.9395, 0.11, 0.29605, 2.2698,       # w11..w14-> estabilidade apos erro
    0.2315, 2.9898,                      # w15,w16 -> penalidade "hard" / bonus "easy"
    0.51655, 0.6621,                     # w17,w18 -> revisao no mesmo dia
)

DECAY = -0.5
FACTOR = 0.9 ** (1 / DECAY) - 1  # == 19/81

MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
MIN_STABILITY = 0.01
MAX_INTERVAL_DAYS = 36500

# Notas (ratings)
AGAIN = 1
HARD = 2
GOOD = 3
EASY = 4
RATINGS = (AGAIN, HARD, GOOD, EASY)
RATING_LABELS = {AGAIN: "errei", HARD: "difícil", GOOD: "bom", EASY: "fácil"}

# Estados do cartao
NEW = "new"
LEARNING = "learning"
REVIEW = "review"
RELEARNING = "relearning"

#: Intervalos curtos (em minutos) usados enquanto o cartao ainda nao "assentou".
LEARNING_STEPS_MIN = {AGAIN: 1, HARD: 6, GOOD: 10}
RELEARNING_STEPS_MIN = {AGAIN: 5, HARD: 10}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Cartao
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Card:
    """Estado de agendamento de um item de vocabulario."""

    stability: float = 0.0
    difficulty: float = 0.0
    due: datetime | None = None
    last_review: datetime | None = None
    state: str = NEW
    reps: int = 0
    lapses: int = 0
    scheduled_days: float = 0.0

    def elapsed_days(self, now: datetime) -> float:
        if self.last_review is None:
            return 0.0
        return max(0.0, (now - self.last_review).total_seconds() / 86400.0)

    def retrievability(self, now: datetime | None = None) -> float:
        """Probabilidade estimada de recordar o item agora (0..1)."""
        if self.state == NEW or self.stability <= 0:
            return 0.0
        return retrievability(self.elapsed_days(now or utcnow()), self.stability)


# ---------------------------------------------------------------------------
# Formulas nucleares
# ---------------------------------------------------------------------------


def retrievability(elapsed_days: float, stability: float) -> float:
    """R(t, S) = (1 + FACTOR * t / S) ^ DECAY"""
    if stability <= 0:
        return 0.0
    return (1 + FACTOR * max(0.0, elapsed_days) / stability) ** DECAY


def interval_for_retention(stability: float, desired_retention: float) -> float:
    """Intervalo (em dias) em que a retrievabilidade cai ate `desired_retention`."""
    desired_retention = min(max(desired_retention, 0.5), 0.99)
    return stability / FACTOR * (desired_retention ** (1 / DECAY) - 1)


def _clamp_d(d: float) -> float:
    return min(max(d, MIN_DIFFICULTY), MAX_DIFFICULTY)


def _clamp_s(s: float) -> float:
    return min(max(s, MIN_STABILITY), float(MAX_INTERVAL_DAYS))


class FSRS:
    """Agendador FSRS-5."""

    def __init__(
        self,
        weights: tuple[float, ...] | list[float] = DEFAULT_WEIGHTS,
        desired_retention: float = 0.9,
        maximum_interval: int = MAX_INTERVAL_DAYS,
    ) -> None:
        if len(weights) != 19:
            raise ValueError(f"FSRS-5 exige 19 pesos, recebeu {len(weights)}")
        self.w = tuple(float(x) for x in weights)
        self.desired_retention = desired_retention
        self.maximum_interval = maximum_interval

    # -- inicializacao ----------------------------------------------------

    def initial_stability(self, rating: int) -> float:
        return _clamp_s(self.w[rating - 1])

    def initial_difficulty(self, rating: int) -> float:
        # D0(G) = w4 - e^(w5 * (G-1)) + 1
        return _clamp_d(self.w[4] - math.exp(self.w[5] * (rating - 1)) + 1)

    # -- atualizacao ------------------------------------------------------

    def next_difficulty(self, difficulty: float, rating: int) -> float:
        # FSRS-5: amortecimento linear + reversao a media
        delta_d = -self.w[6] * (rating - 3)
        damped = difficulty + delta_d * (10 - difficulty) / 9
        target = self.initial_difficulty(EASY)
        return _clamp_d(self.w[7] * target + (1 - self.w[7]) * damped)

    def stability_after_recall(
        self, difficulty: float, stability: float, r: float, rating: int
    ) -> float:
        hard_penalty = self.w[15] if rating == HARD else 1.0
        easy_bonus = self.w[16] if rating == EASY else 1.0
        growth = (
            math.exp(self.w[8])
            * (11 - difficulty)
            * (stability ** -self.w[9])
            * (math.exp(self.w[10] * (1 - r)) - 1)
            * hard_penalty
            * easy_bonus
        )
        return _clamp_s(stability * (1 + growth))

    def stability_after_forget(
        self, difficulty: float, stability: float, r: float
    ) -> float:
        s_forget = (
            self.w[11]
            * (difficulty ** -self.w[12])
            * (((stability + 1) ** self.w[13]) - 1)
            * math.exp(self.w[14] * (1 - r))
        )
        # FSRS-5: a estabilidade nunca aumenta depois de um erro
        return _clamp_s(min(s_forget, stability))

    def stability_same_day(self, stability: float, rating: int) -> float:
        return _clamp_s(stability * math.exp(self.w[17] * (rating - 3 + self.w[18])))

    # -- API principal ----------------------------------------------------

    def next_interval_days(self, stability: float) -> int:
        days = interval_for_retention(stability, self.desired_retention)
        return int(min(max(round(days), 1), self.maximum_interval))

    def preview(self, card: Card, now: datetime | None = None) -> dict[int, float]:
        """Intervalo (em dias, fracionario) que cada nota produziria."""
        now = now or utcnow()
        out: dict[int, float] = {}
        for rating in RATINGS:
            nxt = self.review(card, rating, now)
            delta = (nxt.due - now).total_seconds() / 86400.0
            out[rating] = round(delta, 4)
        return out

    def review(self, card: Card, rating: int, now: datetime | None = None) -> Card:
        """Aplica uma nota ao cartao e devolve o novo estado agendado."""
        if rating not in RATINGS:
            raise ValueError(f"nota invalida: {rating}")
        now = now or utcnow()
        elapsed = card.elapsed_days(now)

        if card.state == NEW:
            stability = self.initial_stability(rating)
            difficulty = self.initial_difficulty(rating)
            state = LEARNING if rating in (AGAIN, HARD, GOOD) else REVIEW
            lapses = card.lapses
        else:
            r = retrievability(elapsed, card.stability) if card.stability > 0 else 0.0
            difficulty = self.next_difficulty(card.difficulty, rating)
            if elapsed < 1.0 and card.state in (LEARNING, RELEARNING, REVIEW) and card.reps > 0:
                # revisao no mesmo dia: formula de curto prazo
                stability = self.stability_same_day(card.stability, rating)
            elif rating == AGAIN:
                stability = self.stability_after_forget(difficulty, card.stability, r)
            else:
                stability = self.stability_after_recall(
                    difficulty, card.stability, r, rating
                )

            if rating == AGAIN:
                state = RELEARNING
                lapses = card.lapses + 1
            else:
                state = REVIEW
                lapses = card.lapses

        # Define o vencimento
        if state == LEARNING and rating in LEARNING_STEPS_MIN:
            due = now + timedelta(minutes=LEARNING_STEPS_MIN[rating])
            scheduled = LEARNING_STEPS_MIN[rating] / 1440.0
        elif state == RELEARNING:
            minutes = RELEARNING_STEPS_MIN.get(rating, 10)
            due = now + timedelta(minutes=minutes)
            scheduled = minutes / 1440.0
        else:
            days = self.next_interval_days(stability)
            due = now + timedelta(days=days)
            scheduled = float(days)

        return replace(
            card,
            stability=stability,
            difficulty=difficulty,
            due=due,
            last_review=now,
            state=state,
            reps=card.reps + 1,
            lapses=lapses,
            scheduled_days=scheduled,
        )
