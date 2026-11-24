"use strict";
/* SINPIN — interface (sem build). Todo conteúdo vindo do servidor é tratado como NÃO CONFIÁVEL: sempre passa por esc(). */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hoje = () => new Date().toLocaleDateString("sv-SE");
const fmtData = d => d ? d.split("-").reverse().join("/") : "—";
const state = { me: null, docId: null, ultimaPesquisa: null, minutaId: null, aba: "doc" };
let USER = localStorage.getItem("sinpin_user") || "senatran.servidor";

function toast(msg, erro = false) {
  const d = document.createElement("div");
  d.textContent = msg; if (erro) d.className = "err";
  $("#toast").append(d); setTimeout(() => d.remove(), erro ? 7000 : 3500);
}
async function api(path, { method = "GET", body, form } = {}) {
  const opt = { method, headers: { "X-Dev-User": USER } };
  if (body) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  if (form) opt.body = form;
  const r = await fetch("/api/v1" + path, opt);
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = j.erro?.mensagem || msg; if (j.erro?.detalhes) msg += " " + j.erro.detalhes.map(d => `${d.campo}: ${d.erro}`).join("; "); } catch { }
    throw new Error(msg);
  }
  return r;
}
const getJSON = async (p, o) => (await api(p, o)).json();
const comLoading = async (btn, fn) => {
  const t = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span>${t}`;
  try { return await fn(); } catch (e) { toast(e.message, true); } finally { btn.disabled = false; btn.innerHTML = t; }
};

/* ------------------------------------------------------------ helpers de apresentação */
const tagEscopo = d => ({ NACIONAL: '<span class="tag azul">Nacional</span>', INSTITUCIONAL_RESTRITO: '<span class="tag lar">Restrito</span>', INSTITUCIONAL_COMPARTILHADO: '<span class="tag verde">Compartilhado</span>' }[d.escopo] || "");
const tagSit = s => ({ VIGENTE: '<span class="tag verde">Vigente</span>', REVOGADA: '<span class="tag verm">Revogada</span>', REVOGADO: '<span class="tag verm">Revogado</span>', SUBSTITUIDO: '<span class="tag lar">Redação substituída</span>', NAO_INICIADA: '<span class="tag amar">Ainda não vigente</span>' }[s] || `<span class="tag">${esc(s)}</span>`);
const tagStatus = s => ({ CONFIRMADA: '<span class="tag verde">Confirmada</span>', SUGERIDA: '<span class="tag lar">Pendente de validação</span>', REJEITADA: '<span class="tag verm">Rejeitada</span>' }[s] || "");
const tagObt = s => ({ OBTIDO: '<span class="tag verde">Documento obtido</span>', APENAS_INDICE: '<span class="tag amar">Apenas referência do índice</span>', PENDENTE: '<span class="tag lar">Obtenção pendente</span>', FALHA: '<span class="tag verm">Falha na obtenção</span>' }[s] || "");
const tagVal = s => ({ CONFIRMADO: '<span class="tag verde">Validação: confirmado</span>', PENDENTE: '<span class="tag lar">Validação jurídica pendente</span>', CONTROVERTIDO: '<span class="tag amar">Controvertido</span>', REJEITADO: '<span class="tag verm">Rejeitado</span>' }[s] || "");
const RES_CONF = { CONFIRMADA_NO_TEXTO: ["verde", "confirmada no texto"], DETECTADA_PENDENTE: ["lar", "detectada no texto, pendente"], NAO_ENCONTRADA_NO_TEXTO: ["verm", "NÃO encontrada no texto"], REJEITADA: ["verm", "rejeitada"], SEM_TEXTO: ["amar", "sem texto para conferir"], NAO_VERIFICAVEL: ["", "não verificável"] };
const link = (u, t) => u && /^https?:\/\//.test(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : `<span class="falta">não registrado</span>`;
const NOME_TIPO = { RESOLUCAO: "Resolução", LEI: "Lei", DECRETO: "Decreto", PORTARIA: "Portaria", INSTRUCAO_NORMATIVA: "Instrução Normativa", DELIBERACAO: "Deliberação" };
const NOME_REL = { ALTERA: "altera", REVOGA: "revoga", REVOGA_PARCIALMENTE: "revoga parcialmente", REGULAMENTA: "regulamenta", COMPLEMENTA: "complementa", CONSOLIDA: "consolida", SUSPENDE: "suspende", RESTABELECE: "restabelece" };
const COR_REL = { ALTERA: "#b45309", REVOGA: "#c8321b", REVOGA_PARCIALMENTE: "#e5702b", REGULAMENTA: "#1351b4", COMPLEMENTA: "#168821", CONSOLIDA: "#6b46c1", SUSPENDE: "#64748b", RESTABELECE: "#0e7490" };

function inline(s) { return s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[(\d+)\]/g, '<span class="cite" data-n="$1">$1</span>'); }
function md(t) { // markdown mínimo e seguro (escapa antes de formatar)
  let html = "", lista = false;
  for (const l of esc(t).split("\n")) {
    const fechar = () => { if (lista) { html += "</ul>"; lista = false; } };
    if (/^##\s+/.test(l)) { fechar(); html += `<h2>${inline(l.replace(/^##\s+/, ""))}</h2>`; }
    else if (/^\s*-\s+/.test(l)) { if (!lista) { html += "<ul>"; lista = true; } html += `<li>${inline(l.replace(/^\s*-\s+/, ""))}</li>`; }
    else if (!l.trim()) fechar();
    else { fechar(); html += `<p>${inline(l)}</p>`; }
  }
  return html + (lista ? "</ul>" : "");
}

/* ------------------------------------------------------------ navegação */
function irPara(v) {
  $$("#pilares button").forEach(b => b.classList.toggle("ativo", b.dataset.v === v));
  $$(".vista").forEach(s => s.hidden = s.id !== "v-" + v);
  if (v === "produzir") { carregarMinutas(); atualizarUsarFontes(); }
}
$("#pilares").addEventListener("click", e => { const b = e.target.closest("button"); if (b) irPara(b.dataset.v); });
$("#abasConhecer").addEventListener("click", e => { const b = e.target.closest("button"); if (b) abrirAba(b.dataset.a); });
function abrirAba(a) {
  state.aba = a;
  $$("#abasConhecer button").forEach(b => b.classList.toggle("ativo", b.dataset.a === a));
  $$(".aba").forEach(x => x.hidden = x.id !== "a-" + a);
  if (a === "pend") carregarPendentes(); if (a === "cat") carregarCatalogo(); if (a === "grafo") carregarGrafo(); if (a === "aud") carregarAuditoria();
}

/* ------------------------------------------------------------ sessão / usuário */
async function iniciar() {
  const { usuarios } = await (await fetch("/api/v1/dev/usuarios")).json().catch(() => ({ usuarios: [] }));
  if (usuarios.length) {
    $("#devbar").hidden = false;
    $("#usuario").innerHTML = usuarios.map(u => `<option value="${esc(u.login)}">${esc(u.orgao)} · ${esc(u.nome)}</option>`).join("");
    if (!usuarios.some(u => u.login === USER)) USER = usuarios[0].login;
    $("#usuario").value = USER;
  }
  $("#usuario").onchange = e => { USER = e.target.value; localStorage.setItem("sinpin_user", USER); state.docId = null; state.minutaId = null; state.ultimaPesquisa = null; $("#resultado").innerHTML = ""; recarregarTudo(); };
  await recarregarTudo();
  $("#dataRef").value = hoje(); $("#mData").value = hoje();
  const m = await getJSON("/modelos");
  $("#mTipo").innerHTML = m.tipos.map(t => `<option value="${t.tipo}">${esc(t.nome)}</option>`).join("");
  montarExemplos();
}
async function recarregarTudo() {
  try { state.me = await getJSON("/me"); } catch (e) { toast(e.message, true); return; }
  $("#chipOrgao").textContent = state.me.orgao.sigla + " · " + state.me.perfil.replace("_", " ").toLowerCase();
  const ia = state.me.llm;
  $("#chipIA").textContent = ia.generativo ? `IA: ${ia.provider} (${ia.modelo})` : "IA: modo extrativo (sem LLM)";
  const nac = $("#selEscopo option[value=NACIONAL]");
  nac.disabled = state.me.perfil !== "CURADOR_NACIONAL";
  $("#selEscopo").value = state.me.perfil === "CURADOR_NACIONAL" ? "NACIONAL" : "INSTITUCIONAL_RESTRITO";
  await carregarDocs();
  $("#a-doc").innerHTML = '<div class="vazio">Selecione um documento na biblioteca ou importe uma norma.</div>';
  atualizarBadgePend();
  if (state.aba !== "doc") abrirAba(state.aba);
}

/* ------------------------------------------------------------ CONHECER: biblioteca */
async function carregarDocs() {
  const q = $("#filtroDocs").value.trim();
  const { documentos } = await getJSON("/documentos" + (q ? "?q=" + encodeURIComponent(q) : ""));
  $("#listaDocs").innerHTML = documentos.length ? documentos.map(d => `
    <div class="item ${d.escopo === "NACIONAL" ? "nac" : d.escopo === "INSTITUCIONAL_RESTRITO" ? "res" : "comp"} ${d.id === state.docId ? "ativo" : ""}" data-id="${d.id}">
      <b>${esc(d.titulo)}</b>
      <div class="em">${esc(d.ementa || "(sem ementa identificada)")}</div>
      <div>${tagEscopo(d)}${tagSit(d.situacao)}${d.sintetico ? '<span class="tag">Sintético</span>' : ""}<span class="tag">${esc(d.orgao)}</span>
        <small>${d.n_dispositivos} disp. · v${d.versao_atual}</small></div>
    </div>`).join("") : '<div class="vazio">Nenhum documento visível para o seu órgão.</div>';
}
$("#filtroDocs").addEventListener("input", () => { clearTimeout(window._t); window._t = setTimeout(carregarDocs, 250); });
$("#listaDocs").addEventListener("click", e => { const i = e.target.closest(".item"); if (i) abrirDoc(i.dataset.id); });

const podeValidar = d => state.me && (d.escopo === "NACIONAL" ? state.me.perfil === "CURADOR_NACIONAL" : d.org_id === state.me.orgao.id);
async function abrirDoc(id, data) {
  state.docId = id; abrirAba("doc");
  $$("#listaDocs .item").forEach(i => i.classList.toggle("ativo", i.dataset.id === id));
  data = data || hoje();
  let r;
  try { r = await getJSON(`/documentos/${id}?data=${data}`); } catch (e) { toast(e.message, true); return; }
  const d = r.documento, comp = r.compilado;
  const avisos = (d.alertas || []).map(a => `<div class="aviso">${esc(a)}</div>`).join("");
  const linhas = comp.dispositivos.map(x => {
    const prof = Math.min(3, x.caminho.split(".").length - 1);
    let nota = "";
    if (x.tipo_redacao === "ALTERACAO" && x.situacao === "VIGENTE") nota = `Redação dada por <b>${esc(x.redacao_dada_por || "ato modificador")}</b>, vigente desde ${fmtData(x.valido_de)}.`;
    if (x.situacao === "REVOGADO") nota = `Revogado em ${fmtData(x.valido_ate)}${x.encerrada_por ? " por <b>" + esc(x.encerrada_por) + "</b>" : ""}.`;
    if (x.situacao === "SUBSTITUIDO") nota = `Redação substituída em ${fmtData(x.valido_ate)}${x.encerrada_por ? " por <b>" + esc(x.encerrada_por) + "</b>" : ""}.`;
    if (x.situacao === "NAO_INICIADA") nota = `Passa a vigorar em ${fmtData(x.valido_de)}.`;
    return `<div class="disp ind${prof} ${x.situacao}"><div class="rot" data-disp="${x.dispositivo_id}" title="Ver histórico de redações">${esc(x.rotulo)}${x.n_redacoes > 1 ? ` <span class="tag lar">${x.n_redacoes} redações</span>` : ""}</div>
      <div><div class="tx">${esc(x.texto)}</div>${nota ? `<div class="nota">${nota}</div>` : ""}</div></div>`;
  });
  let ultimoGrupo = null, corpo = "";
  comp.dispositivos.forEach((x, i) => { if (x.grupo && x.grupo !== ultimoGrupo) { corpo += `<div class="grupo">${esc(x.grupo)}</div>`; ultimoGrupo = x.grupo; } corpo += linhas[i]; });
  const rels = r.relacoes.map(x => {
    const sou_origem = x.origem_documento_id === d.id;
    return `<tr><td>${sou_origem ? "Este ato <b>" + NOME_REL[x.tipo] + "</b>" : "<b>" + esc(x.origem_titulo) + "</b> " + NOME_REL[x.tipo] + " este ato"}</td>
      <td>${esc((sou_origem ? x.destino_rotulo : x.destino_rotulo) || "ato inteiro")}</td>
      <td>${sou_origem ? esc(x.destino_titulo || x.destino_ref + " (não encontrado)") : esc(x.origem_rotulo || "—")}</td>
      <td>${tagStatus(x.status)}</td><td style="font-size:12px;color:#5b6472">${esc(x.nota_efeito || "")}</td></tr>`;
  }).join("");
  $("#a-doc").innerHTML = `
    <div class="cartao cab">
      <h2>${esc(d.titulo)}</h2>
      <div>${tagEscopo(d)}${tagSit(r.compilado.situacao)}${d.sintetico ? '<span class="tag">SINTÉTICO — não é norma real</span>' : ""}<span class="tag">${esc(d.orgao)}</span></div>
      <div class="em">${esc(d.ementa || "")}</div>
      <div class="meta"><span>Publicação: <b>${fmtData(d.data_publicacao)}</b></span><span>Início da vigência: <b>${fmtData(d.vigencia_inicio)}</b></span>
        <span>Término: <b>${fmtData(d.vigencia_fim)}</b></span><span>Versão: <b>${d.versao_atual}</b> de ${d.versoes.length}</span>
</div>
      <div class="origem"><h5>Origem e rastreabilidade</h5>
        <div class="grade">
          <span>Link do documento</span><b>${link(d.fonte_url, "abrir documento")}</b>
          <span>Página de origem</span><b>${link(d.url_origem, "abrir página")}</b>
          <span>Publicação no DOU</span><b>${link(d.url_publicacao_dou, "abrir edição do DOU")}</b>
          <span>Assinatura</span><b>${fmtData(d.data_assinatura)}</b>
          <span>Formato original</span><b>${esc(d.formato_original || "—")}</b>
          <span>Capturado em</span><b>${esc((d.versoes[0]?.capturado_em || "—").replace("T", " ").slice(0, 19))}</b>
          <span>SHA-256 (v${d.versoes[0]?.versao ?? ""})</span><b class="hash" title="${esc(d.versoes[0]?.hash || "")}">${esc((d.versoes[0]?.hash || "").slice(0, 16))}…</b>
          <span>Situação</span><b>${tagObt(d.status_obtencao)}${tagVal(d.status_validacao)}</b>
        </div>
        ${podeValidar(d) ? `<div class="linha"><label class="sel">Validação jurídica humana
          <select id="selValidacao">${["PENDENTE", "CONFIRMADO", "CONTROVERTIDO", "REJEITADO"].map(v => `<option ${v === d.status_validacao ? "selected" : ""}>${v}</option>`).join("")}</select></label>
          <button id="btnValidar">Registrar validação</button></div>` : ""}
      </div>
      ${avisos}
      <div class="barra-data"><b>Texto compilado em</b><input type="date" id="dataComp" value="${esc(data)}"><button id="btnHoje">Hoje</button>
        <span style="color:#5b6472">Veja a redação que vigorava em qualquer data. Clique no rótulo do dispositivo para ver todas as redações.</span></div>
      ${corpo}
    </div>
    <div class="cartao" style="margin-top:14px"><h4>Relações normativas deste ato</h4>
      ${rels ? `<table class="t"><tr><th>Relação</th><th>Dispositivo</th><th>Outro ato</th><th>Status</th><th>Efeito</th></tr>${rels}</table>` : '<div class="vazio">Nenhuma relação identificada.</div>'}</div>`;
  if ($("#btnValidar")) $("#btnValidar").onclick = () => comLoading($("#btnValidar"), async () => {
    await getJSON(`/documentos/${id}/validacao`, { method: "POST", body: { status: $("#selValidacao").value } });
    toast("Validação registrada"); await abrirDoc(id, data);
  });
  $("#dataComp").onchange = e => abrirDoc(id, e.target.value || hoje());
  $("#btnHoje").onclick = () => abrirDoc(id, hoje());
  $$("#a-doc .rot").forEach(el => el.onclick = () => abrirHistorico(el.dataset.disp));
}
async function abrirHistorico(id) {
  const h = await getJSON(`/dispositivos/${id}/historico`);
  $("#corpoHist").innerHTML = `<h3>${esc(h.rotulo)} — histórico de redações</h3><div class="linha-tempo">` + h.redacoes.map(r => `
    <div class="ev"><b>${r.tipo === "ORIGINAL" ? "Redação original" : "Redação dada por " + esc(r.redacao_dada_por || "ato modificador")}</b>
      ${r.registrado_ate ? '<span class="tag">substituída por nova versão do documento</span>' : ""}<br>
      <small>Válida de ${fmtData(r.valido_de)} ${r.valido_ate ? "até " + fmtData(r.valido_ate) + " (" + esc(r.motivo_fim || "") + ")" : "— em vigor"} · registrada em ${esc((r.registrado_em || "").slice(0, 10))}</small>
      <div class="disp" style="grid-template-columns:1fr;padding:6px 0"><div class="tx">${esc(r.texto)}</div></div></div>`).join("") +
    `</div><div class="linha fim"><button onclick="document.getElementById('dlgHist').close()">Fechar</button></div>`;
  $("#dlgHist").showModal();
}

/* ------------------------------------------------------------ CONHECER: importação */
$("#btnImportar").onclick = () => { $("#msgImp").innerHTML = ""; $("#dlgImportar").showModal(); };
$("#cancelImp").onclick = () => $("#dlgImportar").close();
$("#formImportar").addEventListener("submit", async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  if (!fd.get("arquivo")?.size) fd.delete("arquivo");
  await comLoading($("#okImp"), async () => {
    const res = await (await api("/documentos", { method: "POST", form: fd })).json();
    if (res.duplicado) { $("#msgImp").innerHTML = `<div class="aviso info">Este documento já existe com o mesmo conteúdo (${esc(res.titulo)}).</div>`; return; }
    $("#msgImp").innerHTML = `<div class="aviso ok"><b>${esc(res.titulo)}</b> ${res.nova_versao ? "(nova versão " + res.versao + ")" : "importado"}: ${res.dispositivos} dispositivos, ${res.relacoes_detectadas} relação(ões) detectada(s), ${res.relacoes_pendentes} pendente(s) de validação.</div>` +
      res.alertas.map(a => `<div class="aviso">${esc(a)}</div>`).join("");
    toast("Documento importado");
    await carregarDocs(); atualizarBadgePend(); abrirDoc(res.documento_id);
  });
});

/* ------------------------------------------------------------ CONHECER: catálogo do acervo */
async function carregarCatalogo() {
  const alvo = $("#a-cat"); alvo.innerHTML = '<div class="vazio">Carregando…</div>';
  let fontes, rel, itens;
  try { [{ fontes }, rel, { itens }] = await Promise.all([getJSON("/fontes"), getJSON("/catalogo/relatorio"), getJSON("/catalogo")]); } catch (e) { toast(e.message, true); return; }
  const curador = state.me.perfil === "CURADOR_NACIONAL";
  const kpi = (n, t, cls = "") => `<div class="kpi ${cls}"><b>${n}</b><span>${t}</span></div>`;
  const hip = i => i.relacoes_indice.length ? i.conferencia.map(h => {
    const [cor, txt] = RES_CONF[h.resultado] || ["", h.resultado];
    const alvo = h.numero ? `${NOME_TIPO[h.alvo_tipo] || "ato"} ${h.numero}${h.ano ? "/" + h.ano : ""}` : "(alvo não especificado)";
    return `<div class="hip">Índice informa: <b>${NOME_REL[h.tipo] || h.tipo}</b> ${esc(alvo)} <span class="tag ${cor}">${txt}</span>${h.observacao ? `<small> — ${esc(h.observacao)}</small>` : ""}</div>`;
  }).join("") : '<small class="falta">sem relações informadas</small>';
  const linhas = itens.map(i => `<tr>
    <td><b>${esc(i.titulo)}</b><div>${tagObt(i.status_obtencao)}${tagVal(i.status_validacao)}</div>${i.observacao ? `<small>${esc(i.observacao)}</small>` : ""}
      ${i.documento_id ? `<div><a href="#" data-doc="${i.documento_id}">abrir na biblioteca</a></div>` : ""}</td>
    <td class="lk"><div>Documento: ${link(i.url_documento, "link")}</div><div>Origem: ${link(i.url_origem, "link")}</div><div>DOU: ${link(i.url_publicacao_dou, "link")}</div></td>
    <td>${hip(i)}</td></tr>`).join("");
  const lista = (arr, vazio) => arr.length ? `<ul>${arr.map(x => `<li>${esc(x.titulo)}${x.observacao ? ` <small>— ${esc(x.observacao)}</small>` : ""}${x.faltando ? ` <small>(falta: ${esc(x.faltando.join(", "))})</small>` : ""}</li>`).join("")}</ul>` : `<small>${vazio}</small>`;
  alvo.innerHTML = `
    <div class="aviso info">O catálogo mostra o que <b>se sabe que existe</b>, inclusive o que ainda não foi obtido. Item “apenas referência do índice” não tem texto nem efeito jurídico; relações vindas de índice são <b>hipóteses</b> até serem conferidas no texto do ato e no DOU.</div>
    <div class="kpis">${kpi(rel.total_itens, "itens no catálogo")}${kpi(rel.por_obtencao.OBTIDO, "documentos obtidos", "ok")}${kpi(rel.por_obtencao.APENAS_INDICE + rel.por_obtencao.PENDENTE + rel.por_obtencao.FALHA, "ausentes / pendentes", "alerta")}
      ${kpi(rel.por_validacao.PENDENTE, "sem validação humana", "alerta")}${kpi(rel.divergencias_do_indice.length, "divergências índice × texto", rel.divergencias_do_indice.length ? "erro" : "")}</div>
    ${curador ? `<div class="cartao" style="margin-top:12px"><h4>Importar lote (.zip com manifesto.json)</h4><div class="linha"><input type="file" id="arqLote" accept=".zip"><button class="primario" id="btnLote">Importar lote</button></div><div id="msgLote"></div></div>` : ""}
    <div class="cartao" style="margin-top:12px"><h4>Itens do catálogo</h4>
      ${itens.length ? `<table class="t"><tr><th>Ato</th><th>Endereços</th><th>Relações informadas pelo índice × texto</th></tr>${linhas}</table>` : '<div class="vazio">Catálogo vazio.</div>'}</div>
    <div class="cartao" style="margin-top:12px"><h4>Relatório de pendências</h4>
      <h5>Ausentes ou pendentes de obtenção</h5>${lista(rel.ausentes_ou_pendentes, "Nenhum.")}
      <h5>Obtidos sem link do documento</h5>${lista(rel.obtidos_sem_link_documento, "Nenhum.")}
      <h5>Obtidos sem link da publicação no DOU</h5>${lista(rel.obtidos_sem_link_dou, "Nenhum.")}
      <h5>Documentos da biblioteca com origem incompleta</h5>${lista(rel.documentos_sem_origem_completa, "Nenhum.")}</div>
    <div class="cartao" style="margin-top:12px"><h4>Fontes oficiais monitoradas</h4>
      <table class="t"><tr><th>Fonte</th><th>Função</th><th>Utilização</th></tr>${fontes.map(f => `<tr><td>${link(f.url, f.nome)}${f.nota ? `<div><small>${esc(f.nota)}</small></div>` : ""}</td><td><span class="tag">${esc(f.funcao)}</span></td><td>${esc(f.utilizacao || "")}</td></tr>`).join("")}</table>
      <small>Estas são páginas gerais: nunca são aceitas como link de documento individual.</small></div>`;
  $$("#a-cat a[data-doc]").forEach(a => a.onclick = ev => { ev.preventDefault(); abrirDoc(a.dataset.doc); });
  if ($("#btnLote")) $("#btnLote").onclick = () => comLoading($("#btnLote"), async () => {
    const f = $("#arqLote").files[0]; if (!f) { toast("Escolha o arquivo .zip", true); return; }
    const fd = new FormData(); fd.append("pacote", f);
    const r = await (await api("/catalogo/importar", { method: "POST", form: fd })).json();
    $("#msgLote").innerHTML = `<div class="aviso ok">${r.total} item(ns): ${r.obtidos} obtido(s), ${r.apenas_referencia} só referência, ${r.duplicados} duplicado(s), ${r.falhas} falha(s).</div>` +
      r.resultados.filter(x => x.erro).map(x => `<div class="aviso erro">${esc(x.ref)}: ${esc(x.erro)}</div>`).join("");
    await carregarDocs(); atualizarBadgePend(); setTimeout(carregarCatalogo, 1500);
  });
}

/* ------------------------------------------------------------ CONHECER: relações pendentes / grafo / auditoria */
async function atualizarBadgePend() {
  try { const { relacoes } = await getJSON("/relacoes?status=SUGERIDA"); const b = $("#nPend"); b.textContent = relacoes.length; b.dataset.n = relacoes.length; } catch { }
}
async function carregarPendentes() {
  const { relacoes } = await getJSON("/relacoes?status=SUGERIDA");
  $("#a-pend").innerHTML = (relacoes.length ? '<div class="aviso info">Relações sugeridas <b>não alteram a vigência</b> até serem confirmadas. Confirme ou rejeite após conferir a evidência.</div>' : '<div class="vazio">Nenhuma relação aguardando validação.</div>') +
    relacoes.map(x => `<div class="rel SUGERIDA"><div><b>${esc(x.origem_titulo)}</b>${x.origem_rotulo ? " (" + esc(x.origem_rotulo) + ")" : ""} <b style="color:${COR_REL[x.tipo]}">${NOME_REL[x.tipo]}</b>
      <b>${esc(x.destino_titulo || x.destino_ref)}</b>${x.destino_rotulo ? " — " + esc(x.destino_rotulo) : ""} <small>· confiança ${Math.round(x.confianca * 100)}%</small></div>
      <div class="evid">${esc(x.evidencia)}</div>
      <div style="font-size:13px;color:#8a4504">${esc(x.nota_efeito || "")}</div>
      <div class="acoes" style="margin-top:8px"><button class="ok" data-id="${x.id}" data-ac="CONFIRMAR">Confirmar</button><button class="perigo" data-id="${x.id}" data-ac="REJEITAR">Rejeitar</button></div></div>`).join("");
}
$("#a-pend").addEventListener("click", async e => {
  const b = e.target.closest("button[data-ac]"); if (!b) return;
  await comLoading(b, async () => {
    await api(`/relacoes/${b.dataset.id}/validar`, { method: "POST", body: { acao: b.dataset.ac, motivo: "Validação humana na interface" } });
    toast("Relação " + (b.dataset.ac === "CONFIRMAR" ? "confirmada" : "rejeitada") + "; vigência recalculada."); carregarPendentes(); atualizarBadgePend(); carregarDocs();
  });
});

async function carregarGrafo() {
  const g = await getJSON("/grafo");
  const lanes = { NACIONAL: 190, INSTITUCIONAL_COMPARTILHADO: 300, INSTITUCIONAL_RESTRITO: 400 };
  const nos = g.nos, W = Math.max(900, nos.length * 150 + 120), H = 450, pos = {};
  nos.forEach((n, i) => pos[n.id] = { x: 90 + i * ((W - 180) / Math.max(1, nos.length - 1 || 1)), y: lanes[n.escopo] });
  if (nos.length === 1) pos[nos[0].id].x = W / 2;
  const curto = t => t.replace("Resolução", "Res.").replace("Instrução Normativa", "IN").replace("Portaria", "Port.").replace(/\s?(CONTRAN|SENATRAN|DETRAN-XX)/, "");
  const tipos = [...new Set(g.arestas.map(a => a.tipo))];
  const defs = tipos.map(t => `<marker id="m-${t}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${COR_REL[t] || "#555"}"/></marker>`).join("");
  const cont = {};
  const arestas = g.arestas.map(a => {
    const o = pos[a.origem], d = pos[a.destino]; if (!o || !d) return "";
    const par = [a.origem, a.destino].sort().join("|"); const k = cont[par] = (cont[par] || 0) + 1;
    const y1 = o.y + (d.y > o.y ? 24 : -24), y2 = d.y + (o.y > d.y ? 24 : -24);
    const x1 = o.x + (k - 1) * 12, x2 = d.x + (k - 1) * 12;
    let path;
    if (o.y === d.y) { const cy = o.y - 24 - Math.min(120, 36 + Math.abs(x2 - x1) / 4) - (k - 1) * 14; path = `M${x1} ${o.y - 24} Q${(x1 + x2) / 2} ${cy} ${x2} ${d.y - 24}`; }
    else { const my = (y1 + y2) / 2; path = `M${x1} ${y1} C${x1} ${my} ${x2} ${my} ${x2} ${y2}`; }
    const tip = `${NOME_REL[a.tipo]} (${a.qtd})${a.dispositivos.length ? " — " + a.dispositivos.join(", ") : ""}${a.pendentes ? " · " + a.pendentes + " pendente(s)" : ""}`;
    return `<path d="${path}" fill="none" stroke="${COR_REL[a.tipo] || "#555"}" stroke-width="2.2" ${a.pendentes ? 'stroke-dasharray="6 4"' : ""} marker-end="url(#m-${a.tipo})"><title>${esc(tip)}</title></path>`;
  }).join("");
  const nodos = nos.map(n => { const p = pos[n.id]; const rev = n.situacao === "REVOGADA";
    return `<g class="no" data-id="${n.id}" style="cursor:pointer" transform="translate(${p.x - 66},${p.y - 24})"><title>${esc(n.titulo)}</title>
      <rect width="132" height="48" rx="9" fill="${n.escopo === "NACIONAL" ? "#eef4fe" : "#fff7ec"}" stroke="${rev ? "#c8321b" : "#1351b4"}" stroke-width="${rev ? 2 : 1.4}" ${rev ? 'stroke-dasharray="4 3"' : ""}/>
      <text x="66" y="21" text-anchor="middle" font-size="12.5" font-weight="700" fill="#0c326f">${esc(curto(n.titulo).replace(/ nº /, " "))}</text>
      <text x="66" y="38" text-anchor="middle" font-size="10.5" fill="${rev ? "#c8321b" : "#5b6472"}">${rev ? "REVOGADA" : esc(n.orgao)}</text></g>`; }).join("");
  const rot = (txt, y) => `<text x="8" y="${y}" font-size="10.5" fill="#8a93a3" font-weight="700" letter-spacing="1">${txt}</text>`;
  $("#a-grafo").innerHTML = `<div class="aviso info">Cada nó é um ato; cada seta, uma relação extraída do <b>texto</b> da norma (tracejada = pendente de validação). Clique em um ato para abrir.</div>
    <div class="grafo-wrap"><svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs>${defs}</defs>
      <line x1="0" x2="${W}" y1="245" y2="245" stroke="#e6e9ee"/><line x1="0" x2="${W}" y1="350" y2="350" stroke="#e6e9ee"/>
      ${rot("NACIONAL", 20)}${rot("COMPARTILHADO", 262)}${rot("RESTRITO DO ÓRGÃO", 367)}${arestas}${nodos}</svg></div>
    <div class="legenda">${Object.keys(COR_REL).map(t => `<span><i style="background:${COR_REL[t]}"></i>${NOME_REL[t]}</span>`).join("")}</div>`;
  $$("#a-grafo .no").forEach(el => el.onclick = () => abrirDoc(el.dataset.id));
}
async function carregarAuditoria() {
  const { eventos } = await getJSON("/auditoria");
  $("#a-aud").innerHTML = `<div class="cartao"><h4>Trilha de auditoria do seu órgão</h4><table class="t"><tr><th>Quando (UTC)</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr>` +
    eventos.map(e => `<tr><td>${esc(e.em.replace("T", " ").slice(0, 19))}</td><td>${esc(e.login || "—")}</td><td><b>${esc(e.acao)}</b></td><td style="font-size:12px">${esc(JSON.stringify(e.detalhes))}</td></tr>`).join("") + "</table></div>";
}

/* ------------------------------------------------------------ COMPREENDER */
const EXEMPLOS = [
  ["Qual o prazo para o adquirente requerer a transferência de propriedade do veículo?", null],
  ["Mesma pergunta, como era em 01/01/2019", "2019-01-01"],
  ["O que acontece com o adquirente que descumpre o prazo?", null],
  ["Quais documentos instruem o requerimento de transferência?", null],
  ["Como a SENATRAN trata indício de fraude documental?", null],
];
function montarExemplos() {
  $("#exemplos").innerHTML = EXEMPLOS.map((e, i) => `<button data-i="${i}">${esc(e[0])}</button>`).join("");
  $("#exemplos").onclick = ev => { const b = ev.target.closest("button"); if (!b) return; const [q, d] = EXEMPLOS[b.dataset.i];
    $("#pergunta").value = d ? "Qual o prazo para o adquirente requerer a transferência de propriedade do veículo?" : q; $("#dataRef").value = d || hoje(); $("#btnPesquisar").click(); };
}
$("#btnPesquisar").onclick = () => comLoading($("#btnPesquisar"), async () => {
  const pergunta = $("#pergunta").value.trim(); if (pergunta.length < 3) { toast("Digite a pergunta.", true); return; }
  const r = await getJSON("/pesquisa", { method: "POST", body: { pergunta, data: $("#dataRef").value || hoje() } });
  state.ultimaPesquisa = r; renderResultado(r);
});
$("#pergunta").addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("#btnPesquisar").click(); });
function renderResultado(r) {
  const v = r.verificacao || {};
  const avisosV = [];
  if (v.citacoes_invalidas?.length) avisosV.push(`<div class="aviso erro">A resposta citou fontes inexistentes: [${v.citacoes_invalidas.join("], [")}]. Desconsidere essas citações.</div>`);
  if (v.trechos_literais_nao_verificados?.length) avisosV.push(`<div class="aviso erro">Trechos entre aspas que <b>não constam das fontes</b> recuperadas: ${v.trechos_literais_nao_verificados.map(t => "«" + esc(t) + "…»").join("; ")}</div>`);
  if (v.sem_citacoes) avisosV.push('<div class="aviso erro">A resposta não traz citações às fontes. Não a utilize sem conferência.</div>');
  $("#resultado").innerHTML = `
    <div class="cartao"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><h3 style="margin:0">Resposta fundamentada</h3>
      <div><span class="tag azul">Vigência em ${fmtData(r.data)}</span><span class="tag">${r.modo === "extrativo" ? "Modo extrativo (sem LLM)" : "Modelo: " + esc(r.modelo)}</span></div></div>
      ${avisosV.join("")}<div class="resposta" id="respTxt">${md(r.resposta)}</div>
      <div class="linha fim"><button class="primario" id="btnMinuta">Gerar minuta a partir desta pesquisa →</button></div>
      <div class="dica" style="font-size:12px;color:#5b6472">Auxílio à pesquisa. Interpretação e conclusão jurídica cabem ao servidor responsável.</div></div>
    ${r.alertas.length ? `<div class="cartao"><h4>Alertas de vigência e relações</h4>${r.alertas.map(a => `<div class="aviso ${a.nivel === "info" ? "info" : ""}">${esc(a.mensagem)}</div>`).join("")}</div>` : ""}
    <div class="cartao"><h4>Fontes (${r.fontes.length})</h4>${r.fontes.map(f => `
      <div class="fonte ${f.situacao !== "VIGENTE" ? "nv" : ""}" id="fonte-${f.n}"><h5><span class="cite">${f.n}</span> ${esc(f.rotulo)} — ${esc(f.ato)} ${tagSit(f.situacao)}${f.sintetico ? '<span class="tag">Sintético</span>' : ""}</h5>
        <div>${tagVal(f.status_validacao)}<small style="color:#5b6472"> versão ${f.versao_documento} do documento${f.fonte_url ? "" : " · sem link do documento registrado"}</small></div>
        <small style="color:#5b6472">Vigência da redação: ${fmtData(f.valido_de)} → ${f.valido_ate ? fmtData(f.valido_ate) : "atual"}${f.redacao_dada_por ? " · redação dada por " + esc(f.redacao_dada_por) : ""}${f.encerrada_por ? " · encerrada por " + esc(f.encerrada_por) : ""}</small>
        <blockquote>${esc(f.texto)}</blockquote>
        <div style="margin-top:6px"><a href="#" data-abrir="${f.documento_id}">Abrir o ato na biblioteca</a>${f.fonte_url ? " · " + link(f.fonte_url, "fonte oficial (documento)") : ""}${f.url_publicacao_dou ? " · " + link(f.url_publicacao_dou, "publicação no DOU") : ""}</div></div>`).join("") || '<div class="vazio">Nenhuma fonte encontrada.</div>'}</div>`;
  $("#btnMinuta").onclick = () => { $("#mAssunto").value = r.pergunta.slice(0, 200); $("#mData").value = r.data; irPara("produzir"); };
  $("#resultado").onclick = ev => {
    const c = ev.target.closest(".cite[data-n]"); if (c) { const el = document.getElementById("fonte-" + c.dataset.n); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("alvo"); setTimeout(() => el.classList.remove("alvo"), 1800); } }
    const a = ev.target.closest("a[data-abrir]"); if (a) { ev.preventDefault(); irPara("conhecer"); abrirDoc(a.dataset.abrir, r.data); }
  };
}

/* ------------------------------------------------------------ PRODUZIR */
function atualizarUsarFontes() { $("#lblUsarFontes").hidden = !state.ultimaPesquisa?.fontes?.length; }
async function carregarMinutas() {
  const { minutas } = await getJSON("/minutas");
  $("#listaMinutas").innerHTML = minutas.length ? minutas.map(m => `<div class="item ${m.id === state.minutaId ? "ativo" : ""}" data-id="${m.id}"><b>${esc(m.titulo)}</b>
    <small>${esc(m.status)} · ${esc(m.autor)} · ${esc(m.atualizado_em.slice(0, 10))}</small></div>`).join("") : '<div class="vazio">Nenhuma minuta ainda.</div>';
}
$("#listaMinutas").onclick = e => { const i = e.target.closest(".item"); if (i) abrirMinuta(i.dataset.id); };
$("#btnGerar").onclick = () => comLoading($("#btnGerar"), async () => {
  const body = { tipo: $("#mTipo").value, assunto: $("#mAssunto").value.trim(), instrucoes: $("#mInstr").value, contexto: $("#mCtx").value, data: $("#mData").value || hoje() };
  if (!body.assunto) { toast("Informe o assunto.", true); return; }
  if (state.ultimaPesquisa?.fontes?.length && $("#mUsarFontes").checked) { body.fonte_ids = state.ultimaPesquisa.fontes.map(f => f.redacao_id); }
  const m = await getJSON("/minutas", { method: "POST", body });
  toast("Minuta gerada (rascunho)"); state.minutaId = m.id; await carregarMinutas(); renderEditor(m);
});
async function abrirMinuta(id) { state.minutaId = id; const m = await getJSON("/minutas/" + id); carregarMinutas(); renderEditor(m); }
function renderEditor(m) {
  const v = m.verificacao;
  const av = [];
  if (v?.citacoes_invalidas?.length) av.push(`<div class="aviso erro">O modelo citou fontes inexistentes: [${v.citacoes_invalidas.join("], [")}]. Revise a fundamentação.</div>`);
  if (v?.trechos_literais_nao_verificados?.length) av.push('<div class="aviso erro">Há trechos entre aspas que não constam das fontes. Confira antes de usar.</div>');
  $("#editor").innerHTML = `<div class="cartao">
    <div class="ed-top"><input id="edTitulo" value="${esc(m.titulo)}"><select id="edStatus" style="width:auto">${["RASCUNHO", "EM_REVISAO", "APROVADA"].map(s => `<option ${s === m.status ? "selected" : ""}>${s}</option>`).join("")}</select>
      <button class="primario" id="edSalvar">Salvar</button><button id="edDocx">Exportar DOCX</button><button id="edPdf">Exportar PDF</button></div>
    <div class="aviso info" style="margin-top:10px">Minuta gerada em modo <b>${esc(m.modo_geracao)}</b> para a vigência em ${fmtData(m.data_referencia)}. Rascunho assistido por IA: a análise e a aprovação são do servidor responsável.</div>${av.join("")}
    ${m.secoes.map(s => `<div class="ed-sec"><label>${esc(s.titulo)}</label><textarea data-id="${esc(s.id)}" ${s.id === "referencias" ? "" : ""}>${esc(s.texto)}</textarea></div>`).join("")}</div>`;
  const auto = t => { t.style.height = "auto"; t.style.height = Math.max(90, t.scrollHeight + 4) + "px"; };
  $$("#editor textarea").forEach(t => { auto(t); t.oninput = () => auto(t); });
  const coletar = () => ({ titulo: $("#edTitulo").value, status: $("#edStatus").value, secoes: $$("#editor textarea").map(t => ({ id: t.dataset.id, texto: t.value })) });
  $("#edSalvar").onclick = () => comLoading($("#edSalvar"), async () => { await api("/minutas/" + m.id, { method: "PUT", body: coletar() }); toast("Minuta salva"); carregarMinutas(); });
  const exportar = (fmt, btn) => comLoading(btn, async () => {
    await api("/minutas/" + m.id, { method: "PUT", body: coletar() });  // exporta sempre o que está na tela
    const r = await api(`/minutas/${m.id}/exportar?formato=${fmt}`); const blob = await r.blob();
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `minuta_${m.id.slice(0, 8)}.${fmt}`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });
  $("#edDocx").onclick = () => exportar("docx", $("#edDocx")); $("#edPdf").onclick = () => exportar("pdf", $("#edPdf"));
}

/* Deep links (úteis para demonstração): #conhecer, #grafo, #pendentes, #compreender?q=...&data=AAAA-MM-DD, #produzir */
async function rotaInicial() {
  const [rota, qs] = location.hash.slice(1).split("?"); const p = new URLSearchParams(qs || "");
  if (rota === "grafo" || rota === "pendentes" || rota === "catalogo") { irPara("conhecer"); abrirAba(rota === "grafo" ? "grafo" : rota === "catalogo" ? "cat" : "pend"); }
  else if (rota === "doc") { irPara("conhecer"); const d = (await getJSON("/documentos?q=" + encodeURIComponent(p.get("q") || ""))).documentos[0]; if (d) abrirDoc(d.id, p.get("data") || undefined); }
  else if (rota === "compreender") { irPara("compreender"); if (p.get("q")) { $("#pergunta").value = p.get("q"); if (p.get("data")) $("#dataRef").value = p.get("data"); $("#btnPesquisar").click(); } }
  else if (rota === "produzir") irPara("produzir");
}
iniciar().then(rotaInicial);
