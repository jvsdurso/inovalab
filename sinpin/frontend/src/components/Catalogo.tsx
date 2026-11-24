"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getJSON } from "@/lib/api";
import { NOME_REL, NOME_TIPO, RES_CONF } from "@/lib/format";
import { useComCarga, useSessao } from "@/lib/session";
import type { Fonte, ItemCatalogo, ItemPendencia, RelatorioCatalogo, ResultadoLote } from "@/lib/types";
import { Ligacao, Tag, TagObtencao, TagValidacao } from "./Tags";

function Kpi({ n, t, cls = "" }: { n: number; t: string; cls?: string }) {
  return <div className={`kpi ${cls}`}><b>{n}</b><span>{t}</span></div>;
}

function Lista({ itens, vazio }: { itens: ItemPendencia[]; vazio: string }) {
  if (!itens.length) return <small>{vazio}</small>;
  return (
    <ul>
      {itens.map((x, i) => (
        <li key={i}>{x.titulo}{x.observacao ? <small> — {x.observacao}</small> : null}{x.faltando ? <small> (falta: {x.faltando.join(", ")})</small> : null}</li>
      ))}
    </ul>
  );
}

export function Catalogo({ aoAbrirDoc }: { aoAbrirDoc: (id: string) => void }) {
  const { me, versao, avisar, recarregar } = useSessao();
  const { ocupado, executar } = useComCarga();
  const [dados, setDados] = useState<{ fontes: Fonte[]; rel: RelatorioCatalogo; itens: ItemCatalogo[] } | null>(null);
  const [lote, setLote] = useState<ResultadoLote | null>(null);
  const arq = useRef<HTMLInputElement>(null);
  const curador = me?.perfil === "CURADOR_NACIONAL";

  const carregar = useCallback(async () => {
    try {
      const [f, rel, c] = await Promise.all([
        getJSON<{ fontes: Fonte[] }>("/fontes"),
        getJSON<RelatorioCatalogo>("/catalogo/relatorio"),
        getJSON<{ itens: ItemCatalogo[] }>("/catalogo"),
      ]);
      setDados({ fontes: f.fontes, rel, itens: c.itens });
    } catch (e) { avisar(e instanceof Error ? e.message : "Falha ao carregar o catálogo", true); }
  }, [avisar]);
  useEffect(() => { void carregar(); }, [carregar, versao]);

  const importar = () => executar(async () => {
    const f = arq.current?.files?.[0];
    if (!f) { avisar("Escolha o arquivo .zip", true); return; }
    const fd = new FormData();
    fd.append("pacote", f);
    setLote(await getJSON<ResultadoLote>("/catalogo/importar", { method: "POST", form: fd }));
    recarregar();
  });

  if (!dados) return <div className="vazio">Carregando…</div>;
  const { fontes, rel, itens } = dados;
  const ausentes = rel.por_obtencao.APENAS_INDICE + rel.por_obtencao.PENDENTE + rel.por_obtencao.FALHA;

  return (
    <div className="cat">
      <div className="aviso info">
        O catálogo mostra o que <b>se sabe que existe</b>, inclusive o que ainda não foi obtido. Item “apenas referência do índice” não tem texto
        nem efeito jurídico; relações vindas de índice são <b>hipóteses</b> até serem conferidas no texto do ato e no DOU.
      </div>
      <div className="kpis">
        <Kpi n={rel.total_itens} t="itens no catálogo" />
        <Kpi n={rel.por_obtencao.OBTIDO} t="documentos obtidos" cls="ok" />
        <Kpi n={ausentes} t="ausentes / pendentes" cls="alerta" />
        <Kpi n={rel.por_validacao.PENDENTE} t="sem validação humana" cls="alerta" />
        <Kpi n={rel.divergencias_do_indice.length} t="divergências índice × texto" cls={rel.divergencias_do_indice.length ? "erro" : ""} />
      </div>

      {curador && (
        <div className="cartao" style={{ marginTop: 12 }}>
          <h4>Importar lote (.zip com manifesto.json)</h4>
          <div className="linha">
            <input type="file" accept=".zip" ref={arq} />
            <button className="primario" disabled={ocupado} onClick={importar}>{ocupado && <span className="spin" />}Importar lote</button>
          </div>
          {lote && (
            <>
              <div className="aviso ok">{lote.total} item(ns): {lote.obtidos} obtido(s), {lote.apenas_referencia} só referência, {lote.duplicados} duplicado(s), {lote.falhas} falha(s).</div>
              {lote.resultados.filter(x => x.erro).map((x, i) => <div className="aviso erro" key={i}>{x.ref}: {x.erro}</div>)}
            </>
          )}
        </div>
      )}

      <div className="cartao" style={{ marginTop: 12 }}>
        <h4>Itens do catálogo</h4>
        {itens.length ? (
          <table className="t">
            <thead><tr><th>Ato</th><th>Endereços</th><th>Relações informadas pelo índice × texto</th></tr></thead>
            <tbody>
              {itens.map(i => (
                <tr key={i.id}>
                  <td>
                    <b>{i.titulo}</b>
                    <div><TagObtencao status={i.status_obtencao} /><TagValidacao status={i.status_validacao} /></div>
                    {i.observacao && <small>{i.observacao}</small>}
                    {i.documento_id && <div><a href="#" onClick={e => { e.preventDefault(); aoAbrirDoc(i.documento_id as string); }}>abrir na biblioteca</a></div>}
                  </td>
                  <td className="lk">
                    <div>Documento: <Ligacao url={i.url_documento} texto="link" /></div>
                    <div>Origem: <Ligacao url={i.url_origem} texto="link" /></div>
                    <div>DOU: <Ligacao url={i.url_publicacao_dou} texto="link" /></div>
                  </td>
                  <td>
                    {i.relacoes_indice.length ? i.conferencia.map((h, k) => {
                      const [cor, txt] = RES_CONF[h.resultado] ?? ["", h.resultado];
                      const alvo = h.numero ? `${NOME_TIPO[h.alvo_tipo ?? ""] || "ato"} ${h.numero}${h.ano ? "/" + h.ano : ""}` : "(alvo não especificado)";
                      return (
                        <div className="hip" key={k}>
                          Índice informa: <b>{NOME_REL[h.tipo] || h.tipo}</b> {alvo} <Tag cor={cor}>{txt}</Tag>
                          {h.observacao && <small> — {h.observacao}</small>}
                        </div>
                      );
                    }) : <small className="falta">sem relações informadas</small>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <div className="vazio">Catálogo vazio.</div>}
      </div>

      <div className="cartao" style={{ marginTop: 12 }}>
        <h4>Relatório de pendências</h4>
        <h5>Ausentes ou pendentes de obtenção</h5><Lista itens={rel.ausentes_ou_pendentes} vazio="Nenhum." />
        <h5>Obtidos sem link do documento</h5><Lista itens={rel.obtidos_sem_link_documento} vazio="Nenhum." />
        <h5>Obtidos sem link da publicação no DOU</h5><Lista itens={rel.obtidos_sem_link_dou} vazio="Nenhum." />
        <h5>Documentos da biblioteca com origem incompleta</h5><Lista itens={rel.documentos_sem_origem_completa} vazio="Nenhum." />
      </div>

      <div className="cartao" style={{ marginTop: 12 }}>
        <h4>Fontes oficiais monitoradas</h4>
        <table className="t">
          <thead><tr><th>Fonte</th><th>Função</th><th>Utilização</th></tr></thead>
          <tbody>
            {fontes.map((f, i) => (
              <tr key={i}>
                <td><Ligacao url={f.url} texto={f.nome} />{f.nota && <div><small>{f.nota}</small></div>}</td>
                <td><Tag>{f.funcao}</Tag></td>
                <td>{f.utilizacao || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <small>Estas são páginas gerais: nunca são aceitas como link de documento individual.</small>
      </div>
    </div>
  );
}
