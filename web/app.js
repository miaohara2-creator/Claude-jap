"use strict";

const NOTAS = { 1: "errei", 2: "difícil", 3: "bom", 4: "fácil" };
const $ = (id) => document.getElementById(id);

let rodada = null;        // rodada atual (resposta de /api/rodada)
let correcao = null;      // resultado de /api/corrigir
let usouDica = false;
let revelou = false;
let ocupado = false;

async function api(rota, corpo) {
  const opcoes = corpo
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }
    : { method: "GET" };
  const resp = await fetch(rota, opcoes);
  const dados = await resp.json().catch(() => ({ erro: "resposta inválida do servidor" }));
  if (!resp.ok) throw new Error(dados.erro || `HTTP ${resp.status}`);
  return dados;
}

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto == null ? "" : String(texto);
  return div.innerHTML;
}

/* Destaca na frase em português o trecho correspondente à palavra-chave. */
function destacar(frase, chave) {
  if (!chave) return escapar(frase);
  const idx = frase.toLowerCase().indexOf(chave.toLowerCase());
  if (idx < 0) return escapar(frase);
  const fim = idx + chave.length;
  return escapar(frase.slice(0, idx)) + "<mark>" + escapar(frase.slice(idx, fim)) +
         "</mark>" + escapar(frase.slice(fim));
}

/* ---------- estatísticas ---------- */

function pintarEstatisticas(s) {
  if (!s) return;
  $("badge-nivel").textContent = s.nivel_atual;
  const pct = s.progresso ? s.progresso[s.nivel_atual] : 0;
  $("barra-nivel").style.width = `${Math.min(100, pct)}%`;
  $("texto-progresso").textContent =
    `${s.introduzidos[s.nivel_atual]} de ${s.totais[s.nivel_atual]} formas do ${s.nivel_atual} (${pct}%)`;

  const chips = [
    ["a revisar", s.revisoes_pendentes],
    ["novas hoje", `${s.novas_hoje}/${s.limite_novas}`],
    ["aprendidas", s.palavras_aprendidas],
    ["consolidadas", s.palavras_consolidadas],
    ["acerto", `${s.acerto_percentual}%`],
    ["frases", s.frases_no_banco],
    ["dias", s.dias_estudados],
  ];
  $("chips").innerHTML = chips
    .map(([r, v]) => `<span class="chip"><b>${escapar(v)}</b> ${escapar(r)}</span>`)
    .join("");
  $("pe-gerador").textContent = `gerador de frases: ${s.gerador}`;
  const t = s.tokens || { entrada: 0, saida: 0 };
  $("pe-tokens").textContent = t.entrada
    ? `tokens usados — entrada ${t.entrada.toLocaleString("pt-BR")} · saída ${t.saida.toLocaleString("pt-BR")}`
    : "";
}

/* ---------- rodada ---------- */

async function novaRodada(modo) {
  if (ocupado) return;
  ocupado = true;
  usouDica = false; revelou = false; correcao = null;
  $("feedback").classList.add("escondido");
  $("dica-caixa").classList.add("escondido");
  $("acoes").classList.remove("escondido");
  $("resposta").value = "";
  $("resposta").disabled = false;
  $("frase").textContent = "gerando a frase…";
  $("significado").textContent = "";
  $("ensino").classList.add("escondido");
  $("avisos").classList.add("escondido");
  try {
    rodada = await api("/api/rodada", { modo: modo || null });
    const f = rodada.frase, p = rodada.palavra;
    $("badge-modo").textContent = rodada.modo === "nova" ? "palavra nova" : "revisão";
    $("badge-forma").textContent = `${p.nivel} · ${p.forma}`;
    $("badge-origem").textContent = `frase: ${rodada.origem}`;
    $("pendentes").textContent = `${rodada.revisoes_pendentes} revisão(ões) pendente(s)`;
    $("frase").innerHTML = destacar(f.pt, f.keyword_pt);
    $("significado").textContent = p.dica_forma
      ? `a palavra destacada é ${p.significado} — ${p.forma} (${p.dica_forma})`
      : `a palavra destacada é ${p.significado} — ${p.forma}`;

    if (rodada.modo === "nova" && p.grafia) {
      $("ensino-grafia").textContent = p.grafia;
      $("ensino-leitura").textContent = p.leitura;
      $("ensino-detalhe").textContent =
        `${p.significado} · ${p.forma} · lema ${p.lema} · nível ${p.nivel}`;
      $("ensino").classList.remove("escondido");
    }
    if (rodada.avisos && rodada.avisos.length) {
      $("avisos").innerHTML = rodada.avisos.map((a) => `! ${escapar(a)}`).join("<br>");
      $("avisos").classList.remove("escondido");
    }
    pintarEstatisticas(rodada.estatisticas);
    $("resposta").focus();
    carregarPainel(abaAtiva());
  } catch (erro) {
    $("frase").textContent = "";
    $("avisos").innerHTML = escapar(erro.message);
    $("avisos").classList.remove("escondido");
  } finally {
    ocupado = false;
  }
}

async function verificar() {
  if (!rodada || ocupado || correcao) return;
  ocupado = true;
  try {
    correcao = await api("/api/corrigir", {
      item_id: rodada.palavra.item_id,
      sentence_id: rodada.frase.id,
      resposta: $("resposta").value,
      dica: usouDica,
      revelou: revelou,
    });
    pintarCorrecao(correcao);
  } catch (erro) {
    alert(erro.message);
  } finally {
    ocupado = false;
  }
}

function pintarCorrecao(c) {
  const classe = c.situacao === "acerto" ? "ok" : c.situacao === "quase" ? "quase" : "erro";
  $("status").className = `status ${classe}`;
  $("status").textContent = c.mensagem;
  $("ref-ja").textContent = c.referencia.ja;
  $("ref-kana").textContent = c.referencia.leitura;
  $("ref-nota").textContent = c.referencia.nota || "";
  $("ref-palavras").innerHTML = (c.referencia.palavras || [])
    .map((p) => `<span class="pal ${p.alvo ? "alvo" : ""}">
        <span class="pal-ja">${escapar(p.grafia)}</span>
        <small>${escapar(p.leitura)} · ${escapar(p.significado)}</small></span>`)
    .join("");

  $("notas-botoes").innerHTML = c.notas_permitidas
    .map((n) => `<button data-nota="${n}" class="${n === c.nota_sugerida ? "sugerida" : ""}">
        <b>${n}. ${NOTAS[n]}</b><span>volta em ${escapar(c.previsao[String(n)])}</span></button>`)
    .join("");
  for (const b of $("notas-botoes").querySelectorAll("button")) {
    b.onclick = () => responder(Number(b.dataset.nota));
  }
  $("agendado").classList.add("escondido");
  $("acoes").classList.add("escondido");
  $("resposta").disabled = true;
  $("feedback").classList.remove("escondido");
  $("feedback").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function responder(nota) {
  if (!rodada || !correcao || ocupado) return;
  ocupado = true;
  try {
    const r = await api("/api/responder", {
      item_id: rodada.palavra.item_id,
      sentence_id: rodada.frase.id,
      resposta: $("resposta").value,
      nota: nota,
      dica: usouDica,
      revelou: revelou,
    });
    const a = r.agendamento;
    $("agendado").innerHTML =
      `nota <b>${escapar(r.nota_label)}</b> registrada — próxima revisão em ` +
      `<b>${escapar(a.intervalo_texto)}</b> · estabilidade ${a.estabilidade} d · ` +
      `dificuldade ${a.dificuldade}/10 · estado ${escapar(a.estado)} · ` +
      `repetição nº ${a.repeticoes}`;
    $("agendado").classList.remove("escondido");
    $("notas-botoes").innerHTML = "";
    pintarEstatisticas(r.estatisticas);
    correcao = null;
    $("btn-proxima").focus();
    carregarPainel(abaAtiva());
  } catch (erro) {
    alert(erro.message);
  } finally {
    ocupado = false;
  }
}

async function pedirDica() {
  if (!rodada) return;
  usouDica = true;
  const d = await api("/api/dica", { item_id: rodada.palavra.item_id });
  $("dica-caixa").innerHTML =
    `significado: <b>${escapar(d.significado)}</b> · forma: ${escapar(d.forma)}` +
    (d.dica_forma ? ` (${escapar(d.dica_forma)})` : "") +
    `<br>leitura: começa com <b>${escapar(d.primeira_letra)}</b> e tem ` +
    `<b>${d.tamanho}</b> sílabas kana · lema lido <b>${escapar(d.lema_leitura)}</b>` +
    `<br><span class="dim pequeno">usar a dica limita a nota a “difícil”.</span>`;
  $("dica-caixa").classList.remove("escondido");
  $("resposta").focus();
}

function revelar() {
  revelou = true;
  $("resposta").value = "";
  verificar();
}

/* ---------- painéis ---------- */

function abaAtiva() {
  const b = document.querySelector(".aba.ativa");
  return b ? b.dataset.aba : "agenda";
}

async function carregarPainel(nome) {
  const alvo = $(`painel-${nome}`);
  if (!alvo) return;
  try {
    if (nome === "agenda") {
      const { agenda } = await api("/api/agenda?limite=60");
      alvo.innerHTML = agenda.length
        ? tabela(
            ["palavra", "leitura", "significado", "forma", "nível", "volta em", "estab.", "dific.", "erros"],
            agenda.map((c) => [c.surface, c.reading, c.pt, c.form_id, c.level,
                               c.vence_em, c.estabilidade + " d", c.dificuldade, c.lapses]))
        : `<p class="dim">nenhuma palavra agendada ainda.</p>`;
    } else if (nome === "historico") {
      const { historico } = await api("/api/historico?limite=30");
      alvo.innerHTML = historico.length
        ? tabela(
            ["quando", "palavra", "frase", "sua resposta", "nota", "acertou"],
            historico.map((h) => [
              (h.reviewed_at || "").slice(0, 16).replace("T", " "),
              h.surface || h.item_id, h.frase_pt || "—", h.answer || "—",
              NOTAS[h.rating] || h.rating, h.keyword_ok ? "sim" : "não"]))
        : `<p class="dim">nenhuma resposta registrada ainda.</p>`;
    } else if (nome === "frases") {
      const { frases } = await api("/api/frases?limite=40");
      alvo.innerHTML = frases.length
        ? tabela(
            ["frase (pt)", "destaque", "japonês", "origem", "mostrada"],
            frases.map((f) => [f.pt, f.keyword_pt, f.ja, f.source, f.times_shown]))
        : `<p class="dim">nenhuma frase salva ainda.</p>`;
    } else if (nome === "ajustes") {
      const { config } = await api("/api/estado");
      alvo.innerHTML = formularioAjustes(config);
      $("btn-salvar").onclick = salvarAjustes;
    }
  } catch (erro) {
    alvo.innerHTML = `<p class="dim">erro: ${escapar(erro.message)}</p>`;
  }
}

function tabela(colunas, linhas) {
  return `<table><thead><tr>${colunas.map((c) => `<th>${escapar(c)}</th>`).join("")}</tr></thead>
    <tbody>${linhas.map((l) => `<tr>${l.map((v) => `<td>${escapar(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

const CAMPOS_AJUSTE = [
  ["desired_retention", "Retenção desejada (FSRS)", "0.5 a 0.99 — quanto maior, revisões mais frequentes", 0.5, 0.99, 0.01],
  ["new_per_day", "Palavras novas por dia", "quantas palavras-chave inéditas podem ser introduzidas por dia", 1, 100, 1],
  ["advance_ratio", "Fração do nível antes de avançar", "porcentagem das formas do nível a introduzir antes de liberar o próximo", 0.1, 1, 0.05],
  ["mix_threshold", "Início da mistura de níveis", "a partir desta fração do nível atual, o próximo pode aparecer", 0.1, 1, 0.05],
  ["mix_probability", "Chance de palavra do nível seguinte", "0 a 1", 0, 1, 0.05],
  ["new_round_ratio", "Chance de rodada nova havendo revisões", "0 a 1 — menor valor prioriza revisões", 0, 1, 0.05],
  ["generation_attempts", "Tentativas de geração por rodada", "quantas vezes reenviar o pedido à Claude quando a frase é rejeitada", 1, 6, 1],
];

function formularioAjustes(config) {
  const campos = CAMPOS_AJUSTE.map(([chave, rotulo, ajuda, min, max, passo]) =>
    `<label for="cfg-${chave}">${escapar(rotulo)}</label>
     <input id="cfg-${chave}" data-chave="${chave}" type="number" min="${min}" max="${max}"
            step="${passo}" value="${config[chave]}">
     <p class="ajuda">${escapar(ajuda)}</p>`).join("");
  return `<div class="ajuste">${campos}
     <label for="cfg-reuse_sentences">Reaproveitar frases nas revisões</label>
     <select id="cfg-reuse_sentences" data-chave="reuse_sentences">
       <option value="true" ${config.reuse_sentences ? "selected" : ""}>sim</option>
       <option value="false" ${config.reuse_sentences ? "" : "selected"}>não</option>
     </select>
     <p class="ajuda">reusar a frase já salva economiza chamadas à API nas revisões</p>
     <button class="primario" id="btn-salvar">Salvar ajustes</button></div>`;
}

async function salvarAjustes() {
  const corpo = {};
  for (const el of document.querySelectorAll("[data-chave]")) {
    corpo[el.dataset.chave] = el.tagName === "SELECT" ? el.value === "true" : Number(el.value);
  }
  await api("/api/config", corpo);
  const { estatisticas } = await api("/api/estado");
  pintarEstatisticas(estatisticas);
  $("btn-salvar").textContent = "ajustes salvos ✓";
  setTimeout(() => ($("btn-salvar").textContent = "Salvar ajustes"), 1800);
}

/* ---------- eventos ---------- */

$("btn-verificar").onclick = verificar;
$("btn-dica").onclick = pedirDica;
$("btn-revelar").onclick = revelar;
$("btn-proxima").onclick = () => novaRodada();

for (const b of document.querySelectorAll(".aba")) {
  b.onclick = () => {
    document.querySelectorAll(".aba").forEach((x) => x.classList.remove("ativa"));
    document.querySelectorAll(".painel").forEach((x) => x.classList.remove("ativo"));
    b.classList.add("ativa");
    $(`painel-${b.dataset.aba}`).classList.add("ativo");
    carregarPainel(b.dataset.aba);
  };
}

document.addEventListener("keydown", (ev) => {
  const naCaixa = ev.target === $("resposta");
  if (naCaixa && (ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
    ev.preventDefault(); verificar(); return;
  }
  if (naCaixa) return;
  if (correcao && ["1", "2", "3", "4"].includes(ev.key)) {
    const n = Number(ev.key);
    if (correcao.notas_permitidas.includes(n)) { ev.preventDefault(); responder(n); }
  } else if (ev.key === "Enter" && !correcao && !$("feedback").classList.contains("escondido")) {
    ev.preventDefault(); novaRodada();
  }
});

(async function iniciar() {
  try {
    const estado = await api("/api/estado");
    pintarEstatisticas(estado.estatisticas);
  } catch (e) { /* o estado também vem com a rodada */ }
  await novaRodada();
  carregarPainel("agenda");
})();
