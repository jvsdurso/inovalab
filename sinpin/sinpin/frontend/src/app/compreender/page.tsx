"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Ligacao, Tag, TagSituacao, TagValidacao } from "@/components/Tags";
import { getJSON } from "@/lib/api";
import { fmtData, hoje } from "@/lib/format";
import { Markdown } from "@/lib/markdown";
import { useComCarga, useSessao } from "@/lib/session";
import type { Pesquisa } from "@/lib/types";

const BASE_Q = "Qual o prazo para o adquirente requerer a transferência de propriedade do veículo?";
const EXEMPLOS: [string, string | null][] = [
  [BASE_Q, null],
  ["Mesma pergunta, como era em 01/01/2019", "2019-01-01"],
  ["O que acontece com o adquirente que descumpre o prazo?", null],
  ["Quais documentos instruem o requerimento de transferência?", null],
  ["Como a SENATRAN trata indício de fraude documental?", null],
];

/** Deep link: /compreender?q=...&data=AAAA-MM-DD executa a pesquisa ao abrir. */
export default function Compreender() {
  const params = useSearchParams();
  const router = useRouter();
  const { ultimaPesquisa, definirUltimaPesquisa, definirAssuntoMinuta, avisar, me } = useSessao();
  const { ocupado, executar } = useComCarga();
  const [pergunta, setPergunta] = useState(params.get("q") ?? ultimaPesquisa?.pergunta ?? "");
  const [data, setData] = useState(params.get("data") ?? ultimaPesquisa?.data ?? hoje());
  const [destaque, setDestaque] = useState<number | null>(null);
  const jaExecutouQuery = useRef(false);

  const pesquisar = useCallback((q: string, d: string) => executar(async () => {
    if (q.trim().length < 3) { avisar("Digite a pergunta.", true); return; }
    definirUltimaPesquisa(await getJSON<Pesquisa>("/pesquisa", { method: "POST", body: { pergunta: q.trim(), data: d || hoje() } }));
  }), [executar, avisar, definirUltimaPesquisa]);

  useEffect(() => {
    if (jaExecutouQuery.current || !params.get("q") || !me) return;
    jaExecutouQuery.current = true;
    void pesquisar(params.get("q") as string, params.get("data") || hoje());
  }, [params, me, pesquisar]);

  const r = ultimaPesquisa;
  const citar = (n: number) => {
    document.getElementById(`fonte-${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setDestaque(n);
    setTimeout(() => setDestaque(null), 1800);
  };
  const v = r?.verificacao ?? {};

  return (
    <section className="vista una">
      <div className="coluna">
        <div className="cartao busca">
          <textarea rows={2} value={pergunta} onChange={e => setPergunta(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void pesquisar(pergunta, data); }}
            placeholder="Pergunte em linguagem natural. Ex.: Qual o prazo para o adquirente requerer a transferência de propriedade do veículo?" />
          <div className="linha">
            <label className="sel">Vigência em <input type="date" value={data} onChange={e => setData(e.target.value)} /></label>
            <button className="primario" disabled={ocupado} onClick={() => pesquisar(pergunta, data)}>{ocupado && <span className="spin" />}Pesquisar</button>
          </div>
          <div className="exemplos">
            {EXEMPLOS.map(([t, d], i) => (
              <button key={i} onClick={() => { const q = d ? BASE_Q : t; const dd = d || hoje(); setPergunta(q); setData(dd); void pesquisar(q, dd); }}>{t}</button>
            ))}
          </div>
        </div>

        {r && (
          <>
            <div className="cartao">
              <div className="fim-linha">
                <h3 style={{ margin: 0 }}>Resposta fundamentada</h3>
                <div>
                  <Tag cor="azul">Vigência em {fmtData(r.data)}</Tag>
                  <Tag>{r.modo === "extrativo" ? "Modo extrativo (sem LLM)" : `Modelo: ${r.modelo}`}</Tag>
                </div>
              </div>
              {v.citacoes_invalidas?.length ? <div className="aviso erro">A resposta citou fontes inexistentes: [{v.citacoes_invalidas.join("], [")}]. Desconsidere essas citações.</div> : null}
              {v.trechos_literais_nao_verificados?.length
                ? <div className="aviso erro">Trechos entre aspas que <b>não constam das fontes</b> recuperadas: {v.trechos_literais_nao_verificados.map(t => `«${t}…»`).join("; ")}</div> : null}
              {v.sem_citacoes ? <div className="aviso erro">A resposta não traz citações às fontes. Não a utilize sem conferência.</div> : null}
              <div className="resposta"><Markdown texto={r.resposta} aoCitar={citar} /></div>
              <div className="linha fim">
                <button className="primario" onClick={() => { definirAssuntoMinuta({ assunto: r.pergunta.slice(0, 200), data: r.data }); router.push("/produzir"); }}>
                  Gerar minuta a partir desta pesquisa →
                </button>
              </div>
              <div className="dica">Auxílio à pesquisa. Interpretação e conclusão jurídica cabem ao servidor responsável.</div>
            </div>

            {r.alertas.length > 0 && (
              <div className="cartao">
                <h4>Alertas de vigência e relações</h4>
                {r.alertas.map((a, i) => <div className={`aviso${a.nivel === "info" ? " info" : ""}`} key={i}>{a.mensagem}</div>)}
              </div>
            )}

            <div className="cartao">
              <h4>Fontes ({r.fontes.length})</h4>
              {r.fontes.length === 0 && <div className="vazio">Nenhuma fonte encontrada.</div>}
              {r.fontes.map(f => (
                <div key={f.n} id={`fonte-${f.n}`} className={`fonte${f.situacao !== "VIGENTE" ? " nv" : ""}${destaque === f.n ? " alvo" : ""}`}>
                  <h5><span className="cite">{f.n}</span> {f.rotulo} — {f.ato} <TagSituacao situacao={f.situacao} />{f.sintetico ? <Tag>Sintético</Tag> : null}</h5>
                  <div>
                    <TagValidacao status={f.status_validacao} />
                    <small style={{ color: "#5b6472" }}> versão {f.versao_documento} do documento{f.fonte_url ? "" : " · sem link do documento registrado"}</small>
                  </div>
                  <small style={{ color: "#5b6472" }}>
                    Vigência da redação: {fmtData(f.valido_de)} → {f.valido_ate ? fmtData(f.valido_ate) : "atual"}
                    {f.redacao_dada_por ? ` · redação dada por ${f.redacao_dada_por}` : ""}{f.encerrada_por ? ` · encerrada por ${f.encerrada_por}` : ""}
                  </small>
                  <blockquote>{f.texto}</blockquote>
                  <div style={{ marginTop: 6 }}>
                    <Link href={`/conhecer?doc=${encodeURIComponent(f.documento_id)}&data=${encodeURIComponent(r.data)}`}>Abrir o ato na biblioteca</Link>
                    {f.fonte_url && <> · <Ligacao url={f.fonte_url} texto="fonte oficial (documento)" /></>}
                    {f.url_publicacao_dou && <> · <Ligacao url={f.url_publicacao_dou} texto="publicação no DOU" /></>}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
