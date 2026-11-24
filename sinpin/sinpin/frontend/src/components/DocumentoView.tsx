"use client";

import { Fragment, useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { dataHora, fmtData, hoje, NOME_REL } from "@/lib/format";
import { useComCarga, useSessao } from "@/lib/session";
import type { DispositivoCompilado, DocumentoResposta, Relacao, StatusValidacao } from "@/lib/types";
import { Ligacao, Tag, TagEscopo, TagObtencao, TagSituacao, TagStatusRelacao, TagValidacao } from "./Tags";

const STATUS_VAL: StatusValidacao[] = ["PENDENTE", "CONFIRMADO", "CONTROVERTIDO", "REJEITADO"];

function nota(x: DispositivoCompilado): string | null {
  if (x.tipo_redacao === "ALTERACAO" && x.situacao === "VIGENTE") return `Redação dada por ${x.redacao_dada_por || "ato modificador"}, vigente desde ${fmtData(x.valido_de)}.`;
  if (x.situacao === "REVOGADO") return `Revogado em ${fmtData(x.valido_ate)}${x.encerrada_por ? " por " + x.encerrada_por : ""}.`;
  if (x.situacao === "SUBSTITUIDO") return `Redação substituída em ${fmtData(x.valido_ate)}${x.encerrada_por ? " por " + x.encerrada_por : ""}.`;
  if (x.situacao === "NAO_INICIADA") return `Passa a vigorar em ${fmtData(x.valido_de)}.`;
  return null;
}

interface Props { docId: string; data: string; aoMudarData: (d: string) => void; aoVerHistorico: (dispId: string) => void }

export function DocumentoView({ docId, data, aoMudarData, aoVerHistorico }: Props) {
  const { me, versao, avisar, recarregar } = useSessao();
  const { ocupado, executar } = useComCarga();
  const [r, setR] = useState<DocumentoResposta | null>(null);
  const [validacao, setValidacao] = useState<StatusValidacao>("PENDENTE");

  useEffect(() => {
    let vivo = true;
    setR(null);
    getJSON<DocumentoResposta>(`/documentos/${docId}?data=${data}`)
      .then(x => { if (vivo) { setR(x); setValidacao(x.documento.status_validacao); } })
      .catch(e => avisar(e instanceof Error ? e.message : "Falha ao abrir o documento", true));
    return () => { vivo = false; };
  }, [docId, data, versao, avisar]);

  if (!r) return <div className="vazio">Carregando…</div>;
  const { documento: d, compilado: comp, relacoes } = r;
  const podeValidar = !!me && (d.escopo === "NACIONAL" ? me.perfil === "CURADOR_NACIONAL" : d.org_id === me.orgao.id);
  const v0 = d.versoes[0];

  const registrarValidacao = () => executar(async () => {
    await getJSON(`/documentos/${docId}/validacao`, { method: "POST", body: { status: validacao } });
    avisar("Validação registrada");
    recarregar();
  });

  let ultimoGrupo: string | null = null;

  return (
    <>
      <div className="cartao cab">
        <h2>{d.titulo}</h2>
        <div>
          <TagEscopo escopo={d.escopo} /><TagSituacao situacao={comp.situacao} />
          {d.sintetico ? <Tag>SINTÉTICO — não é norma real</Tag> : null}<Tag>{d.orgao ?? ""}</Tag>
        </div>
        <div className="em">{d.ementa || ""}</div>
        <div className="meta">
          <span>Publicação: <b>{fmtData(d.data_publicacao)}</b></span>
          <span>Início da vigência: <b>{fmtData(d.vigencia_inicio)}</b></span>
          <span>Término: <b>{fmtData(d.vigencia_fim)}</b></span>
          <span>Versão: <b>{d.versao_atual}</b> de {d.versoes.length}</span>
        </div>

        <div className="origem">
          <h5>Origem e rastreabilidade</h5>
          <div className="grade">
            <span>Link do documento</span><b><Ligacao url={d.fonte_url} texto="abrir documento" /></b>
            <span>Página de origem</span><b><Ligacao url={d.url_origem} texto="abrir página" /></b>
            <span>Publicação no DOU</span><b><Ligacao url={d.url_publicacao_dou} texto="abrir edição do DOU" /></b>
            <span>Assinatura</span><b>{fmtData(d.data_assinatura)}</b>
            <span>Formato original</span><b>{d.formato_original || "—"}</b>
            <span>Capturado em</span><b>{dataHora(v0?.capturado_em)}</b>
            <span>SHA-256 (v{v0?.versao ?? ""})</span><b className="hash" title={v0?.hash || ""}>{(v0?.hash || "").slice(0, 16)}…</b>
            <span>Situação</span><b><TagObtencao status={d.status_obtencao} /><TagValidacao status={d.status_validacao} /></b>
          </div>
          {podeValidar && (
            <div className="linha">
              <label className="sel">Validação jurídica humana
                <select value={validacao} onChange={e => setValidacao(e.target.value as StatusValidacao)}>
                  {STATUS_VAL.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <button disabled={ocupado} onClick={registrarValidacao}>{ocupado && <span className="spin" />}Registrar validação</button>
            </div>
          )}
        </div>

        {d.alertas.map((a, i) => <div className="aviso" key={i}>{a}</div>)}

        <div className="barra-data">
          <b>Texto compilado em</b>
          <input type="date" value={data} onChange={e => aoMudarData(e.target.value || hoje())} />
          <button onClick={() => aoMudarData(hoje())}>Hoje</button>
          <span style={{ color: "#5b6472" }}>Veja a redação que vigorava em qualquer data. Clique no rótulo do dispositivo para ver todas as redações.</span>
        </div>

        {comp.dispositivos.map(x => {
          const mostrarGrupo = !!x.grupo && x.grupo !== ultimoGrupo;
          if (x.grupo) ultimoGrupo = x.grupo;
          const prof = Math.min(3, x.caminho.split(".").length - 1);
          const n = nota(x);
          return (
            <Fragment key={x.dispositivo_id}>
              {mostrarGrupo && <div className="grupo">{x.grupo}</div>}
              <div className={`disp ind${prof} ${x.situacao}`}>
                <div className="rot" title="Ver histórico de redações" onClick={() => aoVerHistorico(x.dispositivo_id)}>
                  {x.rotulo}{x.n_redacoes > 1 && <> <Tag cor="lar">{x.n_redacoes} redações</Tag></>}
                </div>
                <div><div className="tx">{x.texto}</div>{n && <div className="nota">{n}</div>}</div>
              </div>
            </Fragment>
          );
        })}
      </div>

      <div className="cartao" style={{ marginTop: 14 }}>
        <h4>Relações normativas deste ato</h4>
        {relacoes.length ? <TabelaRelacoes docId={d.id} relacoes={relacoes} /> : <div className="vazio">Nenhuma relação identificada.</div>}
      </div>
    </>
  );
}

function TabelaRelacoes({ docId, relacoes }: { docId: string; relacoes: Relacao[] }) {
  return (
    <table className="t">
      <thead><tr><th>Relação</th><th>Dispositivo</th><th>Outro ato</th><th>Status</th><th>Efeito</th></tr></thead>
      <tbody>
        {relacoes.map(x => {
          const souOrigem = x.origem_documento_id === docId;
          return (
            <tr key={x.id}>
              <td>{souOrigem ? <>Este ato <b>{NOME_REL[x.tipo]}</b></> : <><b>{x.origem_titulo}</b> {NOME_REL[x.tipo]} este ato</>}</td>
              <td>{x.destino_rotulo || "ato inteiro"}</td>
              <td>{souOrigem ? x.destino_titulo || `${x.destino_ref} (não encontrado)` : x.origem_rotulo || "—"}</td>
              <td><TagStatusRelacao status={x.status} /></td>
              <td style={{ fontSize: 12, color: "#5b6472" }}>{x.nota_efeito || ""}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
