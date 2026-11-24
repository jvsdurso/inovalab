"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getJSON } from "@/lib/api";
import { fmtData, hoje } from "@/lib/format";
import { useComCarga, useSessao } from "@/lib/session";
import type { Minuta, MinutaResumo, SecaoMinuta, TipoMinuta } from "@/lib/types";

export default function Produzir() {
  const { versao, avisar, ultimaPesquisa, assuntoMinuta, definirAssuntoMinuta } = useSessao();
  const gerar = useComCarga();
  const [tipos, setTipos] = useState<TipoMinuta[]>([]);
  const [tipo, setTipo] = useState("");
  const [assunto, setAssunto] = useState("");
  const [instr, setInstr] = useState("");
  const [ctx, setCtx] = useState("");
  const [data, setData] = useState(hoje());
  const [usarFontes, setUsarFontes] = useState(true);
  const [lista, setLista] = useState<MinutaResumo[] | null>(null);
  const [minuta, setMinuta] = useState<Minuta | null>(null);

  const temFontes = !!ultimaPesquisa?.fontes?.length;

  useEffect(() => {
    getJSON<{ tipos: TipoMinuta[] }>("/modelos")
      .then(r => { setTipos(r.tipos); setTipo(t => t || r.tipos[0]?.tipo || ""); })
      .catch(e => avisar(e instanceof Error ? e.message : "Falha ao carregar modelos", true));
  }, [avisar, versao]);

  // Assunto vindo de COMPREENDER (consumido uma vez).
  useEffect(() => {
    if (!assuntoMinuta) return;
    setAssunto(assuntoMinuta.assunto);
    setData(assuntoMinuta.data);
    definirAssuntoMinuta(null);
  }, [assuntoMinuta, definirAssuntoMinuta]);

  const carregarLista = useCallback(async () => {
    try { setLista((await getJSON<{ minutas: MinutaResumo[] }>("/minutas")).minutas); }
    catch (e) { avisar(e instanceof Error ? e.message : "Falha ao listar minutas", true); }
  }, [avisar]);
  useEffect(() => { void carregarLista(); }, [carregarLista, versao]);
  useEffect(() => { setMinuta(null); }, [versao]);

  const abrir = async (id: string) => {
    try { setMinuta(await getJSON<Minuta>(`/minutas/${id}`)); }
    catch (e) { avisar(e instanceof Error ? e.message : "Falha ao abrir a minuta", true); }
  };

  const criar = () => gerar.executar(async () => {
    if (!assunto.trim()) { avisar("Informe o assunto.", true); return; }
    const body: Record<string, unknown> = { tipo, assunto: assunto.trim(), instrucoes: instr, contexto: ctx, data: data || hoje() };
    if (temFontes && usarFontes) body.fonte_ids = ultimaPesquisa?.fontes.map(f => f.redacao_id);
    const m = await getJSON<Minuta>("/minutas", { method: "POST", body });
    avisar("Minuta gerada (rascunho)");
    setMinuta(m);
    await carregarLista();
  });

  return (
    <div className="pagina">
    <section className="vista">
      <aside className="lateral">
        <div className="cartao">
          <h3>Nova minuta</h3>
          <label>Tipo<select value={tipo} onChange={e => setTipo(e.target.value)}>{tipos.map(t => <option key={t.tipo} value={t.tipo}>{t.nome}</option>)}</select></label>
          <label>Assunto<input value={assunto} onChange={e => setAssunto(e.target.value)} placeholder="Ex.: Prazo para transferência de propriedade" /></label>
          <label>Instruções para a redação<textarea rows={3} value={instr} onChange={e => setInstr(e.target.value)} placeholder="O que a minuta deve concluir/recomendar…" /></label>
          <label>Fatos do caso (só o que for informado aqui será afirmado)<textarea rows={3} value={ctx} onChange={e => setCtx(e.target.value)} placeholder="Partes, datas, número do processo…" /></label>
          <label>Vigência em<input type="date" value={data} onChange={e => setData(e.target.value)} /></label>
          {temFontes && (
            <label className="check"><input type="checkbox" checked={usarFontes} onChange={e => setUsarFontes(e.target.checked)} /> Usar as fontes da última pesquisa</label>
          )}
          <button className="primario" style={{ marginTop: 12 }} disabled={gerar.ocupado} onClick={criar}>{gerar.ocupado && <span className="spin" />}Gerar minuta</button>
        </div>
        <h4 className="tit">Minutas do órgão</h4>
        <div className="lista">
          {lista === null && <div className="vazio">Carregando…</div>}
          {lista?.length === 0 && <div className="vazio">Nenhuma minuta ainda.</div>}
          {lista?.map(m => (
            <div key={m.id} className={`item${m.id === minuta?.id ? " ativo" : ""}`} onClick={() => abrir(m.id)}>
              <b>{m.titulo}</b><small>{m.status} · {m.autor} · {m.atualizado_em.slice(0, 10)}</small>
            </div>
          ))}
        </div>
      </aside>
      <div className="conteudo">
        {minuta
          ? <Editor key={minuta.id} minuta={minuta} aoSalvar={carregarLista} />
          : <div className="vazio">Gere ou selecione uma minuta para editar.</div>}
      </div>
    </section>
    </div>
  );
}

function Editor({ minuta: m, aoSalvar }: { minuta: Minuta; aoSalvar: () => Promise<void> }) {
  const { avisar } = useSessao();
  const { ocupado, executar } = useComCarga();
  const [titulo, setTitulo] = useState(m.titulo);
  const [status, setStatus] = useState(m.status);
  const [secoes, setSecoes] = useState<SecaoMinuta[]>(m.secoes);
  const v = m.verificacao;

  const salvarAgora = async () => {
    await api(`/minutas/${m.id}`, { method: "PUT", body: { titulo, status, secoes: secoes.map(s => ({ id: s.id, texto: s.texto })) } });
  };
  const salvar = () => executar(async () => { await salvarAgora(); avisar("Minuta salva"); await aoSalvar(); });
  const exportar = (fmt: "docx" | "pdf") => executar(async () => {
    await salvarAgora(); // exporta sempre o que está na tela
    const blob = await (await api(`/minutas/${m.id}/exportar?formato=${fmt}`)).blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `minuta_${m.id.slice(0, 8)}.${fmt}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });

  return (
    <div className="cartao">
      <div className="ed-top">
        <input value={titulo} onChange={e => setTitulo(e.target.value)} />
        <select style={{ width: "auto" }} value={status} onChange={e => setStatus(e.target.value)}>
          {["RASCUNHO", "EM_REVISAO", "APROVADA"].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="primario" disabled={ocupado} onClick={salvar}>Salvar</button>
        <button disabled={ocupado} onClick={() => exportar("docx")}>Exportar DOCX</button>
        <button disabled={ocupado} onClick={() => exportar("pdf")}>Exportar PDF</button>
      </div>
      <div className="aviso info" style={{ marginTop: 10 }}>
        Minuta gerada em modo <b>{m.modo_geracao}</b> para a vigência em {fmtData(m.data_referencia)}. Rascunho assistido por IA: a análise e a aprovação são do servidor responsável.
      </div>
      {v?.citacoes_invalidas?.length ? <div className="aviso erro">O modelo citou fontes inexistentes: [{v.citacoes_invalidas.join("], [")}]. Revise a fundamentação.</div> : null}
      {v?.trechos_literais_nao_verificados?.length ? <div className="aviso erro">Há trechos entre aspas que não constam das fontes. Confira antes de usar.</div> : null}
      {secoes.map((s, i) => (
        <div className="ed-sec" key={s.id}>
          <label>{s.titulo}</label>
          <textarea value={s.texto} ref={el => { if (el) { el.style.height = "auto"; el.style.height = `${Math.max(90, el.scrollHeight + 4)}px`; } }}
            onChange={e => setSecoes(x => x.map((y, k) => (k === i ? { ...y, texto: e.target.value } : y)))} />
        </div>
      ))}
    </div>
  );
}
