# Japonês incremental — guia do projeto

App de estudo de japonês: cada rodada mostra uma frase em **português** com
exatamente **uma palavra que o aluno ainda não conhece**, destacada, para ele
traduzir ao japonês. As revisões são agendadas pelo **FSRS-5**.

Leia o `README.md` para a visão completa. Este arquivo é o resumo operacional.

## Comandos

```bash
iniciar.bat                             # Windows: duplo clique (cria .venv, instala, abre o navegador)
atualizar.bat                           # Windows: baixa a versão do GitHub por cima e reabre o app
python3 app.py                          # interface web em http://127.0.0.1:8765
python3 app.py --cli                    # modo terminal
python3 app.py --porta 9000 --banco ~/japones.db
python3 -m unittest discover -s tests   # 76 testes — rode antes de concluir qualquer mudança
```

Só a biblioteca padrão do Python (3.9+) é obrigatória. O piso é 3.9 porque
o código não usa nada mais novo; a automação do Windows testa 3.9, 3.10 e
3.12 e falha se alguma mudança quebrar isso. O pacote opcional `anthropic`
exige 3.10+, então em 3.9 o app roda com o gerador local — `ClaudeClient.
motivo_indisponivel()` explica isso ao usuário em vez de só sumir com a API.

**Saída em japonês:** `config.configurar_saida_utf8()` é chamado no início de
`app.py`. Sem isso o app morre com `UnicodeEncodeError` num console cp1252
(o padrão do Windows). Não remova, e não dependa do `iniciar.bat` para isso. `anthropic` é opcional
e habilita a geração de frases; sem `ANTHROPIC_API_KEY` o app cai no gerador
local. **Não introduza outras dependências sem pedir.**

## Arquitetura

| Módulo | Responsabilidade |
|---|---|
| `nihongo/fsrs.py` | FSRS-5 puro (19 pesos). Sem I/O, sem dependência do resto. |
| `nihongo/conjugation.py` | Conjuga verbos (godan/ichidan/する/来る/ある) e adjetivos. Tabelas de kana + exceções. |
| `nihongo/vocab.py` | Lê `data/vocab_n*.json` e expande em itens (lema × forma). `item_id = "飲む\|masu"`. |
| `nihongo/db.py` | SQLite: `cards`, `sentences`, `reviews`, `settings`. |
| `nihongo/generator.py` | Prompt de sistema + **validação** das frases. |
| `nihongo/claude_client.py` | Messages API com saída estruturada por schema. |
| `nihongo/templates.py` | Gerador local de reserva (corpus + moldes). |
| `nihongo/grading.py` | Correção da resposta do aluno. |
| `nihongo/engine.py` | Orquestra: escolhe a palavra, obtém a frase, aplica o FSRS. |
| `nihongo/config.py` | Lê a chave da API de `chave-api.txt` quando não há variável de ambiente. |
| `nihongo/server.py`, `cli.py` | Interface web (stdlib `http.server`) e terminal. |
| `web/` | HTML/CSS/JS sem framework nem CDN. |

## Invariantes — não quebre sem um teste que cubra a mudança

1. **Uma palavra nova por frase.** `generator.validate_sentence` é a guarda:
   varre a tradução japonesa procurando grafias de itens ainda não
   apresentados. Toda frase — da Claude, do corpus ou dos moldes — passa por
   ela antes de chegar ao aluno. Nunca afrouxe essa checagem para "fazer
   passar" uma frase.
2. **Cada forma conjugada é uma palavra-chave independente**, com cartão FSRS
   próprio e nível JLPT próprio (`飲みます` N5, `飲ませる` N3).
3. **A correção é sobre a palavra-chave, não sobre a frase inteira.** Uma
   forma diferente do mesmo verbo é **erro**: `飲みました` não vale por
   `飲みませんでした`. Aceita kanji, a leitura em kana e grafias alternativas.
4. **Palavras de 1–2 caracteres não têm tolerância de "quase"** (`私` e `水`
   seriam quase idênticos). Ver `grading.tolerance_for`.
5. **Rodada de apresentação ensina, não cobra:** mostra grafia e leitura, e a
   nota máxima é `GOOD` (a palavra estava na tela).
6. **Errar a palavra-chave aplica `AGAIN`** mesmo que o aluno escolha outra
   nota — o FSRS precisa do dado verdadeiro.
7. **Só sai da fila de palavras novas quem tem `reps > 0`.** Uma rodada
   aberta e abandonada precisa voltar a ser oferecida.
8. **`check()` não agenda nada**; só `submit()` grava no FSRS.

## API da Claude

- Modelo padrão `claude-opus-5-5`. Não troque sem o usuário pedir.
- Saída estruturada via `output_config={"format": {"type": "json_schema", ...}}`.
- `betas` e `fallbacks` só existem em `client.beta.messages.create`.
- Nada de `temperature`, `top_p` ou `thinking.budget_tokens`: os modelos
  atuais recusam esses parâmetros.
- O prompt de sistema vai com `cache_control` (é estável entre rodadas); a
  parte variável vai na mensagem do usuário.
- Quando o validador rejeita a frase, o erro é reenviado ao modelo na
  tentativa seguinte. Preserve esse laço.

## Vocabulário

`data/vocab_n5.json` … `vocab_n1.json`, um objeto por palavra:

```json
{"w": "飲む", "r": "のむ", "t": "verb-godan", "pt": "beber", "alt": ["のむ"]}
```

`t` é um dos tipos de `conjugation.py` (`verb-godan`, `verb-ichidan`,
`verb-suru`, `verb-kuru`, `verb-aru`, `adj-i`, `adj-na`, `noun`, `adverb`,
`pronoun`, `conjunction`). A ordem dentro do arquivo é a ordem pedagógica.
Ao acrescentar verbos, rode os testes: `test_conjugacao.py` conjuga o
vocabulário inteiro e falha se alguma forma quebrar.

## Lançadores do Windows (`iniciar.bat`, `atualizar.bat`)

Mantenha o arquivo **em ASCII puro e com quebras CRLF**: o `cmd.exe` lê o
script enquanto executa, e caracteres não-ASCII antes do `chcp 65001` viram
lixo na tela. O japonês aparece pelo Python, com `PYTHONUTF8=1`.
O script cria `.venv`, instala `anthropic`, pergunta a chave uma única vez e
chama `app.py`. Erros previstos (sem Python, Python antigo, falha no venv)
têm mensagem própria e `pause` para a janela não sumir.

`atualizar.bat` baixa o zip do branch pelo codeload, extrai no `%TEMP%` e
copia por cima da pasta. **Nunca inclua no pacote arquivos do usuário**
(`chave-api.txt`, `data/progresso.db`, `.venv/`): é o `.gitignore` que
garante que a atualização não apague o progresso de quem usa o app. Se o
branch ou o repositório mudarem, atualize as variáveis no topo do script.

## Convenções

- Interface, mensagens de erro, README e comentários em **português do
  Brasil**; nomes de função e variável também (`proxima_revisao`, `rodada`).
- Sem dependências novas, sem CDN no front-end.
- Toda mudança de comportamento vem com teste em `tests/`.
