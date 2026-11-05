"""Testes do motor: selecao de palavras, niveis, FSRS aplicado e API HTTP."""

import json
import random
import tempfile
import threading
import unittest
import urllib.request
from datetime import timedelta
from http.server import ThreadingHTTPServer

from nihongo.db import Database
from nihongo.engine import Engine, humanize_days
from nihongo.fsrs import AGAIN, EASY, GOOD, utcnow
from nihongo.generator import validate_sentence
from nihongo.server import AppState, make_handler
from nihongo.vocab import Vocabulary

V = Vocabulary.load()


_ABERTOS: list[Database] = []


def motor(**config):
    db = Database(tempfile.mktemp(suffix=".db"))
    _ABERTOS.append(db)
    eng = Engine(db, V, client=None, rng=random.Random(42))
    for k, valor in config.items():
        db.set_setting(k, valor)
    return eng


def tearDownModule():
    for db in _ABERTOS:
        db.close()
    _ABERTOS.clear()


class TestSelecao(unittest.TestCase):
    def test_comeca_no_n5_pela_ordem_pedagogica(self):
        eng = motor()
        item = eng.pick_new_item()
        self.assertEqual(item.level, "N5")
        self.assertEqual(item.item_id, "私|base")

    def test_formas_do_verbo_sao_liberadas_em_ordem(self):
        eng = motor()
        masu, dicionario = V.get("飲む|masu"), V.get("飲む|dict")
        self.assertEqual(eng.vocab.previous_form(dicionario).item_id, masu.item_id)
        # sem a forma ます aprendida, a forma do dicionário não pode ser escolhida
        eng.db.ensure_card(dicionario)
        self.assertNotEqual(eng.pick_new_item().item_id, dicionario.item_id)

    def test_limite_diario_de_palavras_novas(self):
        eng = motor(new_per_day=3)
        for _ in range(3):
            r = eng.next_round(force="nova")
            eng.submit(r.item.item_id, r.sentence["id"], r.sentence["ja"])
        self.assertFalse(eng.can_introduce())
        self.assertEqual(eng.next_round().mode, "revisão")

    def test_revisao_vencida_tem_prioridade(self):
        eng = motor(new_round_ratio=0.0)
        r = eng.next_round(force="nova")
        eng.submit(r.item.item_id, r.sentence["id"], r.sentence["ja"])
        # força o vencimento do cartão
        card = eng.db.get_card(r.item.item_id)
        eng.db.save_card(r.item.item_id, card.__class__(
            **{**card.__dict__, "due": utcnow() - timedelta(days=1)}))
        self.assertEqual(eng.next_round().mode, "revisão")

    def test_nivel_avanca_quando_a_fracao_e_atingida(self):
        eng = motor(advance_ratio=0.001, new_per_day=10_000)
        self.assertEqual(eng.level_status()["nivel_atual"], "N5")
        for _ in range(3):
            r = eng.next_round(force="nova")
            eng.submit(r.item.item_id, r.sentence["id"], r.sentence["ja"])
        self.assertEqual(eng.level_status()["nivel_atual"], "N4")
        self.assertIn("N4", eng.allowed_levels())

    def test_niveis_avancados_bloqueados_no_comeco(self):
        self.assertEqual(motor().allowed_levels(), {"N5"})

    def test_cartao_sem_resposta_continua_na_fila(self):
        """Mostrar a frase cria o cartão, mas só responder tira a palavra da fila."""
        eng = motor()
        rodada = eng.next_round(force="nova")
        self.assertEqual(eng.db.seen_item_ids(), {rodada.item.item_id})
        self.assertEqual(eng.db.known_item_ids(), set())
        self.assertEqual(eng.pick_new_item().item_id, rodada.item.item_id)
        eng.submit(rodada.item.item_id, rodada.sentence["id"], rodada.sentence["ja"])
        self.assertEqual(eng.db.known_item_ids(), {rodada.item.item_id})
        self.assertNotEqual(eng.pick_new_item().item_id, rodada.item.item_id)

    def test_palavra_adiada_nao_ganha_cartao(self):
        """Forma sem frase disponível é pulada sem sujar o banco."""
        eng = motor()
        sem_molde = V.get("とても|base")          # advérbio: nenhum molde local
        with self.assertRaises(RuntimeError):
            eng.sentence_for(sem_molde, set(), "nova", [])
        self.assertEqual(eng.db.seen_item_ids(), set())

    def test_rodada_abandonada_volta_a_ser_oferecida(self):
        eng = motor()
        primeira = eng.next_round(force="nova")        # usuário fecha o app aqui
        segunda = eng.next_round(force="nova")
        self.assertEqual(primeira.item.item_id, segunda.item.item_id)


class TestRodadaCompleta(unittest.TestCase):
    def test_apresentacao_mostra_a_palavra_e_revisao_esconde(self):
        eng = motor()
        r = eng.next_round(force="nova")
        self.assertIn("grafia", r.to_dict()["palavra"])
        eng.submit(r.item.item_id, r.sentence["id"], r.sentence["ja"])
        card = eng.db.get_card(r.item.item_id)
        eng.db.save_card(r.item.item_id, card.__class__(
            **{**card.__dict__, "due": utcnow() - timedelta(days=1)}))
        r2 = eng.next_round(force="revisão")
        self.assertEqual(r2.mode, "revisão")
        self.assertNotIn("grafia", r2.to_dict()["palavra"])

    def test_apresentacao_nao_pode_receber_facil(self):
        eng = motor()
        r = eng.next_round(force="nova")
        fb = eng.submit(r.item.item_id, r.sentence["id"], r.sentence["ja"], rating=EASY)
        self.assertEqual(fb["nota_aplicada"], GOOD)

    def test_errar_a_palavra_chave_forca_errei(self):
        eng = motor()
        r = eng.next_round(force="nova")
        fb = eng.submit(r.item.item_id, r.sentence["id"], "ぜんぜん違う文", rating=EASY)
        self.assertEqual(fb["nota_aplicada"], AGAIN)
        self.assertFalse(fb["acertou"])

    def test_corrigir_nao_agenda_nada(self):
        eng = motor()
        r = eng.next_round(force="nova")
        antes = eng.db.get_card(r.item.item_id)
        eng.check(r.item.item_id, r.sentence["id"], r.sentence["ja"])
        self.assertEqual(eng.db.get_card(r.item.item_id).reps, antes.reps)

    def test_frase_e_salva_no_banco(self):
        eng = motor()
        r = eng.next_round(force="nova")
        self.assertEqual(eng.db.count_sentences(), 1)
        salva = eng.db.get_sentence(r.sentence["id"])
        self.assertEqual(salva["pt"], r.sentence["pt"])

    def test_historico_registra_a_resposta(self):
        eng = motor()
        r = eng.next_round(force="nova")
        eng.submit(r.item.item_id, r.sentence["id"], "minha resposta")
        h = eng.db.recent_reviews(1)[0]
        self.assertEqual(h["answer"], "minha resposta")
        self.assertEqual(h["item_id"], r.item.item_id)


class TestSessaoLonga(unittest.TestCase):
    def test_invariante_de_uma_palavra_nova_por_frase(self):
        """Em 120 rodadas, nenhuma frase pode trazer palavra não apresentada."""
        eng = motor(new_per_day=10_000)
        vistas = 0
        for _ in range(120):
            rodada = eng.next_round()
            conhecidos = eng.db.known_item_ids() - {rodada.item.item_id}
            check = validate_sentence(dict(rodada.sentence), rodada.item, V, conhecidos)
            self.assertTrue(check.ok, f"{rodada.sentence['pt']}: {check.problems}")
            eng.submit(rodada.item.item_id, rodada.sentence["id"], rodada.sentence["ja"])
            vistas += 1
        self.assertEqual(vistas, 120)
        self.assertGreater(eng.stats()["palavras_aprendidas"], 20)

    def test_intervalos_crescem_ao_longo_da_sessao(self):
        eng = motor()
        r = eng.next_round(force="nova")
        intervalos = []
        for _ in range(5):
            card = eng.db.get_card(r.item.item_id)
            if card.due:
                eng.db.save_card(r.item.item_id, card.__class__(
                    **{**card.__dict__, "due": utcnow(),
                       "last_review": card.last_review}))
            fb = eng.submit(r.item.item_id, r.sentence["id"], r.sentence["ja"], rating=GOOD)
            intervalos.append(fb["agendamento"]["intervalo_dias"])
        crescentes = [i for i in intervalos if i >= 1]
        self.assertEqual(crescentes, sorted(crescentes))
        self.assertGreater(crescentes[-1], 1)


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eng = motor()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(AppState(cls.eng)))
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def pedir(self, rota, corpo=None):
        url = f"http://127.0.0.1:{self.porta}{rota}"
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(
            url, data=dados, headers={"Content-Type": "application/json"},
            method="POST" if dados is not None else "GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())

    def test_pagina_inicial(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}/") as r:
            self.assertEqual(r.status, 200)
            self.assertIn(b"Japon", r.read())

    def test_fluxo_completo(self):
        _, estado = self.pedir("/api/estado")
        self.assertEqual(estado["estatisticas"]["nivel_atual"], "N5")

        _, rodada = self.pedir("/api/rodada", {})
        self.assertIn("frase", rodada)
        item_id, sid = rodada["palavra"]["item_id"], rodada["frase"]["id"]

        _, dica = self.pedir("/api/dica", {"item_id": item_id})
        self.assertIn("significado", dica)

        _, correcao = self.pedir("/api/corrigir", {
            "item_id": item_id, "sentence_id": sid, "resposta": "テスト"})
        self.assertFalse(correcao["acertou"])
        self.assertEqual(correcao["notas_permitidas"], [1])

        _, aplicado = self.pedir("/api/responder", {
            "item_id": item_id, "sentence_id": sid, "resposta": "テスト", "nota": 1})
        self.assertEqual(aplicado["nota_aplicada"], 1)

        _, agenda = self.pedir("/api/agenda")
        self.assertEqual(len(agenda["agenda"]), 1)
        _, hist = self.pedir("/api/historico")
        self.assertEqual(len(hist["historico"]), 1)

    def test_config_persiste(self):
        _, resp = self.pedir("/api/config", {"new_per_day": 7, "ignorado": 1})
        self.assertEqual(resp["config"]["new_per_day"], 7)
        self.assertNotIn("ignorado", resp["config"])

    def test_rota_desconhecida(self):
        try:
            self.pedir("/api/nada")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)
        else:
            self.fail("deveria ter dado 404")

    def test_campo_faltando_devolve_400(self):
        try:
            self.pedir("/api/dica", {})
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            self.assertIn("item_id", json.loads(e.read())["erro"])
        else:
            self.fail("deveria ter dado 400")


class TestFormatacao(unittest.TestCase):
    def test_humanize(self):
        self.assertEqual(humanize_days(0), "agora")
        self.assertEqual(humanize_days(10 / 1440), "10 min")
        self.assertEqual(humanize_days(1), "1 dia")
        self.assertEqual(humanize_days(5), "5 dias")
        self.assertIn("meses", humanize_days(60))
        self.assertIn("anos", humanize_days(500))


if __name__ == "__main__":
    unittest.main()
