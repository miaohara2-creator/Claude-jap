"""Modo terminal: estudar sem abrir o navegador."""

from __future__ import annotations

from .claude_client import ClaudeClient
from .db import Database
from .engine import Engine
from .fsrs import RATING_LABELS

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
YELLOW, GREEN, RED, CYAN = "\033[33m", "\033[32m", "\033[31m", "\033[36m"


def _highlight(pt: str, keyword: str) -> str:
    if not keyword:
        return pt
    idx = pt.lower().find(keyword.lower())
    if idx < 0:
        return pt
    end = idx + len(keyword)
    return f"{pt[:idx]}{BOLD}{YELLOW}{pt[idx:end]}{RESET}{pt[end:]}"


def run_cli(db_path: str | None = None, model: str | None = None,
            digitar: bool = False) -> int:
    """Estuda pelo terminal.

    Por padrão o fluxo é o mesmo da interface web: a frase aparece, você
    traduz de cabeça, revela e se avalia. Com `digitar=True` o modo antigo
    volta -- você escreve a tradução e o app corrige a palavra-chave
    sozinho, o que exige um teclado japonês (IME).
    """
    db = Database(db_path) if db_path else Database()
    engine = Engine(db, client=ClaudeClient(model=model))
    stats = engine.stats()
    print(f"\n{BOLD}日本語{RESET} — nível {stats['nivel_atual']} · "
          f"{stats['palavras_aprendidas']} palavras · {stats['gerador']}")
    if stats.get("motivo_local"):
        print(f"{DIM}  {stats['motivo_local']}{RESET}")
    print(f"{DIM}Enter mostra a resposta · depois você mesmo se avalia · "
          f"'sair' encerra{RESET}\n")

    try:
        while True:
            try:
                rodada = engine.next_round()
            except RuntimeError as exc:
                print(f"{RED}{exc}{RESET}")
                return 1

            item, frase = rodada.item, rodada.sentence
            tag = f"{CYAN}[{rodada.mode} · {item.level} · {rodada.source}]{RESET}"
            print(f"{tag} revisões pendentes: {rodada.due_count}")
            for aviso in rodada.warnings:
                print(f"{DIM}  ! {aviso}{RESET}")
            print(f"\n  {_highlight(frase['pt'], frase['keyword_pt'])}")
            print(f"{DIM}  palavra-chave: {item.pt} · {item.form_label}{RESET}")
            if rodada.mode == "nova":
                print(f"{GREEN}  nova palavra → {item.surface} ({item.reading}){RESET}")

            if digitar:
                resposta = input("\n  日本語 > ").strip()
                if resposta.lower() in ("sair", "exit", "quit"):
                    break
                fb = engine.check(item.item_id, frase["id"], resposta,
                                  revealed=not resposta)
                cor = GREEN if fb["acertou"] else RED
                print(f"\n  {cor}{fb['mensagem']}{RESET}")
            else:
                entrada = input("\n  traduza mentalmente e tecle Enter para ver > ").strip()
                if entrada.lower() in ("sair", "exit", "quit"):
                    break
                resposta = ""
                fb = engine.revelar(item.item_id, frase["id"])
            print(f"\n  referência: {BOLD}{fb['referencia']['ja']}{RESET}")
            print(f"{DIM}  leitura: {fb['referencia']['leitura']}{RESET}")
            print(f"  palavra-chave: {GREEN}{fb['palavra']['grafia']} "
                  f"({fb['palavra']['leitura']}){RESET}")
            if fb["referencia"]["nota"]:
                print(f"{DIM}  {fb['referencia']['nota']}{RESET}")

            permitidas = fb["notas_permitidas"]
            opcoes = " ".join(
                f"{n}={RATING_LABELS[n]} ({fb['previsao'][str(n)]})" for n in permitidas
            )
            escolha = input(f"\n  você acertou? [{opcoes}] "
                            f"(Enter={fb['nota_sugerida']}): ").strip()
            nota = (int(escolha) if escolha.isdigit() and int(escolha) in permitidas
                    else fb["nota_sugerida"])

            aplicado = engine.submit(item.item_id, frase["id"], resposta,
                                     rating=nota, autoavaliacao=not digitar)
            ag = aplicado["agendamento"]
            print(f"  {DIM}próxima revisão em {ag['intervalo_texto']} "
                  f"(S={ag['estabilidade']} D={ag['dificuldade']}){RESET}\n")
            print("─" * 64)
    except (KeyboardInterrupt, EOFError):
        print("\n  até logo!")
    finally:
        s = engine.stats()
        print(f"\n  {s['palavras_aprendidas']} palavras aprendidas · "
              f"{s['revisoes_totais']} revisões · {s['acerto_percentual']}% de acerto")
        db.close()
    return 0
