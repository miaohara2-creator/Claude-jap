# 日本語 — aprendizado incremental de japonês

Aplicativo de estudo em que **cada frase traz exatamente uma palavra que você
ainda não conhece**. A frase aparece em português, você a traduz para o
japonês, e a palavra-chave da rodada fica destacada. O agendamento das
revisões usa o algoritmo **FSRS-5**: cada acerto empurra a palavra para mais
longe no tempo; cada erro a traz de volta.

```
┌──────────────────────────────────────────────────────────────┐
│  palavra nova   N5 · presente polido (〜ます)   frase: claude │
│                                                              │
│  Todos os dias eu ⟦bebo⟧ água no trabalho.                   │
│                                                              │
│  palavra nova desta rodada:  飲みます (のみます)               │
│                                                              │
│  sua tradução → 毎日、仕事で水を飲みます。                      │
│  ✓ correto · próxima revisão em 4 dias                       │
└──────────────────────────────────────────────────────────────┘
```

## Como funciona

**Uma palavra nova por frase.** Cada rodada escolhe uma palavra-chave e pede à
Claude uma frase em português cuja tradução japonesa use *somente* aquela
palavra, as palavras que você já estudou e palavras funcionais (partículas,
copula, demonstrativos, numerais). A frase devolvida passa por um validador
que não depende do que o modelo diz ter usado: ele varre a tradução japonesa
procurando grafias de itens do vocabulário que ainda não foram apresentados.
Se achar alguma, a frase é rejeitada e o erro volta para a Claude na tentativa
seguinte ("a frase usa palavra(s) que o aluno ainda não aprendeu: お茶").

**Cada forma verbal é uma palavra-chave.** `飲む` não é um item só: são 22
(`飲みます`, `飲みません`, `飲んで`, `飲んでいます`, `飲まない`, `飲めば`,
`飲ませられる`…). Cada uma tem cartão FSRS próprio, entra na ordem pedagógica e
só é liberada depois que alguma forma anterior do mesmo verbo apareceu.
Adjetivos-i e adjetivos-na também se desdobram em formas.

**A frase em português tem de exigir aquela forma.** O prompt obriga que o
tempo, a polidez, a negação e o aspecto fiquem explícitos em português —
"ontem", "ainda não", "todos os dias", "eu quero", "fui obrigado a" — para que
dê para escolher a forma japonesa certa sem adivinhação.

**Níveis do N5 ao N1.** As palavras entram na ordem N5 → N4 → N3 → N2 → N1. O
nível seguinte é liberado quando uma fração configurável do nível atual já foi
introduzida (padrão 80%), e a partir da metade do nível atual já aparecem
palavras do próximo de vez em quando. A dificuldade da *forma* também conta:
`飲みます` é N5, mas `飲ませる` (causativa) só aparece no N3, mesmo sendo o
mesmo verbo.

**Palavra nova é ensinada, não cobrada.** Numa rodada de apresentação a grafia
e a leitura aparecem na tela — você não teria como adivinhá-las. Por isso a
nota máxima nessa rodada é "bom". Nas revisões seguintes a palavra fica
escondida e você precisa lembrar.

## Instalação

### Windows — duplo clique

Dê um **duplo clique em `iniciar.bat`**. Na primeira vez ele prepara tudo
sozinho (cerca de um minuto): cria um ambiente Python próprio na pasta
`.venv`, instala a biblioteca da Claude e pergunta a sua chave da API. Depois
disso, cada clique sobe o aplicativo em poucos segundos e abre o navegador.

O único pré-requisito é o **Python 3.9 ou mais novo** — mas para a Claude
escrever as frases é preciso **3.10 ou mais novo**, porque é o que o pacote
`anthropic` exige. Com 3.9 o aplicativo funciona normalmente, só que com o
gerador local; o atalho avisa quando é esse o caso. Se não tiver, o
atalho avisa e manda o link: baixe em <https://www.python.org/downloads/> e
marque **"Add python.exe to PATH"** na tela de instalação.

Para fechar o aplicativo, feche a janela preta que fica aberta.

### Atualizar

Quando sair uma versão nova, dê um **duplo clique em `atualizar.bat`**: ele
baixa a versão atual, substitui os arquivos do aplicativo e já abre o app.

**O seu progresso (`data\progresso.db`) e a sua chave (`chave-api.txt`) não
são tocados** — esses arquivos não fazem parte do pacote. O ambiente `.venv`
também é reaproveitado, então a atualização leva poucos segundos.

Se preferir a linha de comando e tiver clonado o repositório, `git pull` faz
o mesmo.

### Qualquer sistema — linha de comando

```bash
pip install anthropic                  # opcional, mas recomendado
export ANTHROPIC_API_KEY=sk-ant-...    # ou: ant auth login
python3 app.py
```

Abra <http://127.0.0.1:8765>. Sem chave de API o aplicativo continua
funcionando com o gerador local (ver *Limitações*).

### Credencial da Claude

Na primeira execução o `iniciar.bat` pergunta como a Claude vai escrever as
frases:

Já instalado e quer **trocar a chave pela conta**? Duplo clique em
**`conectar-conta.bat`**: ele faz o login e oferece desativar o
`chave-api.txt` — enquanto esse arquivo existir, a chave tem precedência e a
conta não é usada.

**1. Entrar com a sua conta Claude (recomendado).** Abre o navegador, você
entra na conta e pronto — **nenhuma chave para gerenciar**. O login é feito
pelo utilitário oficial `ant`, da Anthropic, que o atalho baixa para a pasta
`.ferramentas` se você autorizar. Ele grava um perfil em
`%APPDATA%\Anthropic` que o pacote `anthropic` encontra sozinho. Para trocar
de conta depois: `.ferramentas\ant.exe auth login`; para sair:
`.ferramentas\ant.exe auth logout`.

**2. Colar uma chave de API.** Fica num arquivo `chave-api.txt` na pasta do
projeto, uma linha, com `#` para comentários. Está no `.gitignore`.

**3. Nenhuma das duas.** O app funciona com o gerador local de frases, que é
bem mais limitado.

A ordem de precedência é a mesma do SDK oficial: variável de ambiente
`ANTHROPIC_API_KEY` → `chave-api.txt` → conta conectada. O rodapé do app
mostra qual delas está em uso, então nada é decidido em silêncio — e se a
credencial for recusada, o app avisa em bom português, passa para o gerador
local e para de tentar até você corrigir e reiniciar.

```bash
python3 app.py --porta 9000            # outra porta
python3 app.py --banco ~/japones.db    # outro banco
python3 app.py --modelo claude-sonnet-5-5
python3 app.py --cli                   # estudar pelo terminal
python3 app.py --sem-navegador         # não abrir o navegador sozinho
```

No Windows, dá para passar as mesmas opções pelo atalho: crie um atalho do
`iniciar.bat` e acrescente os argumentos no campo *Destino*.

O modelo padrão é `claude-opus-5-5`. Cada frase custa poucos centavos de
milésimo: o prompt de sistema é marcado para cache e as frases ficam salvas no
banco, então as revisões reaproveitam o que já foi gerado em vez de gerar de
novo.

## Usando

O ciclo é o de um baralho de memorização: você **lê a frase em português,
traduz de cabeça** (mentalmente, em voz alta ou no papel), **revela a
resposta** e **diz se acertou**. Não é preciso digitar nada — escrever
japonês exigiria um teclado com IME instalado.

| Ação | Atalho |
|---|---|
| Mostrar a resposta | `espaço` ou `Enter` |
| Dizer como foi | `1` errei · `2` difícil · `3` bom · `4` fácil |
| Próxima frase | `espaço` ou `Enter` |

- **Dica** mostra o significado, a forma pedida, a primeira sílaba e o tamanho
  da leitura, antes de revelar.
- Ao revelar, aparecem a tradução de referência, a leitura em kana, a
  palavra-chave em destaque, uma nota gramatical e a decomposição da frase
  palavra por palavra.
- Numa palavra **nova** a nota máxima é "bom": a grafia estava na tela.

### Prefere digitar?

Quem tem teclado japonês pode usar o modo antigo no terminal, em que o app
corrige a palavra-chave sozinho:

```bash
python3 app.py --cli --digitar
```

### Como a resposta é corrigida (modo `--digitar`)

No fluxo padrão quem avalia é você. No modo digitado, o que decide acerto ou
erro é a **palavra-chave**, não a frase inteira:

- aceita kanji, a leitura só em kana e grafias alternativas (`椅子` ou `いす`);
- ignora pontuação, espaços e largura de caractere, e trata katakana e
  hiragana como equivalentes;
- uma troca de caractere em palavras de três ou mais caracteres conta como
  "quase" (nota máxima "difícil"); em palavras de um ou dois caracteres não há
  tolerância, porque `私` e `水` seriam "quase" um do outro;
- uma forma diferente do mesmo verbo é **erro**: `飲みました` não vale por
  `飲みませんでした`, que é outra palavra-chave;
- romaji é recusado com um aviso em vez de ser corrigido.

Nesse modo, errar a palavra-chave aplica "errei" no FSRS mesmo que você
clique em outra nota — ali o app viu o que aconteceu. Na autoavaliação não há
o que contradizer: a sua nota é o dado. Nos dois casos o app mostra quando a
palavra volta em cada nota antes de você escolher.

## Ajustes (aba *Ajustes*)

| Ajuste | Padrão | O que faz |
|---|---|---|
| `desired_retention` | 0.9 | alvo de retenção do FSRS; maior = revisões mais frequentes |
| `new_per_day` | 10 | palavras novas por dia |
| `advance_ratio` | 0.8 | fração do nível a introduzir antes de liberar o próximo |
| `mix_threshold` | 0.5 | a partir daqui o nível seguinte pode aparecer |
| `mix_probability` | 0.15 | chance de puxar palavra do nível seguinte |
| `new_round_ratio` | 0.25 | chance de rodada nova quando há revisões pendentes |
| `generation_attempts` | 3 | tentativas de geração por rodada antes de desistir |
| `reuse_sentences` | sim | reaproveitar frases salvas nas revisões |

## Estrutura

```
iniciar.bat             atalho de duplo clique para Windows
atualizar.bat           baixa a versão mais recente e reabre o app
conectar-conta.bat      entra com a sua conta Claude (dispensa a chave de API)
.ferramentas/           utilitário de login `ant` (criada só se você usar a conta)
app.py                  ponto de entrada (servidor web ou --cli)
nihongo/
  fsrs.py               FSRS-5: estabilidade, dificuldade, agendamento
  conjugation.py        conjugação de verbos (godan/ichidan/する/来る/ある) e adjetivos
  vocab.py              expande o vocabulário em itens (lema × forma)
  db.py                 SQLite: cartões, frases, histórico, ajustes
  generator.py          prompt da Claude + validação das frases
  claude_client.py      chamada à Messages API com saída estruturada
  templates.py          gerador local de reserva (corpus + moldes)
  grading.py            correção da resposta
  engine.py             seleção da rodada e aplicação do FSRS
  config.py             lê a chave da API de chave-api.txt
  server.py / cli.py    interface web e interface de terminal
data/
  vocab_n5…n1.json      641 lemas → 5.754 formas estudáveis
  corpus.json           frases escritas à mão para o modo sem API
  progresso.db          seu progresso (criado na primeira execução)
web/                    interface (HTML/CSS/JS, sem dependências)
tests/                  73 testes
```

### Banco de dados

| Tabela | Conteúdo |
|---|---|
| `cards` | um por forma estudada: estabilidade, dificuldade, vencimento, estado, repetições, lapsos |
| `sentences` | toda frase gerada, com português, japonês, leitura, destaque, origem e quantas vezes foi mostrada |
| `reviews` | cada resposta: o que você escreveu, se acertou a palavra-chave, nota, intervalo e retrievabilidade no momento |
| `settings` | ajustes e contadores de tokens |

O arquivo é SQLite comum — dá para abrir com `sqlite3 data/progresso.db` e
consultar o próprio progresso.

## Testes

```bash
python3 -m unittest discover -s tests
```

Cobrem as fórmulas do FSRS, a conjugação (incluindo irregulares como
`行って`, `できる`, `こない`, `ない` de `ある`), a correção, a validação de
frases, o laço de geração com reenvio do erro ao modelo, uma sessão simulada
de 120 rodadas verificando a invariante de uma palavra nova por frase, e as
rotas HTTP. O cliente da API é testado contra um servidor que imita
`POST /v1/messages`, conferindo o schema enviado, o cache do prompt e a
leitura da resposta.

## Limitações conhecidas

- **Sem `ANTHROPIC_API_KEY` o app é bem mais pobre.** O gerador local cobre
  substantivos, adjetivos e sete formas verbais (`ます`, `ません`, `ました`,
  `ませんでした`, `ています`, `たい`, `ましょう`, potencial) com moldes fixos, mais
  30 frases escritas à mão. Formas sem molde são adiadas para quando a API
  estiver configurada, e as frases locais têm bem menos contexto.
- O vocabulário é uma seleção curada (641 lemas), não as listas JLPT
  completas. Acrescentar palavras é editar `data/vocab_n*.json`.
- A validação detecta palavras desconhecidas que estejam no vocabulário do
  app; uma palavra comum que não esteja em nenhuma lista (`ところ`, `とき`)
  pode escapar. O prompt proíbe explicitamente usá-las.
- O app não corrige a frase inteira, só a palavra-chave — o resto da tradução
  aparece ao lado da referência para você comparar.
