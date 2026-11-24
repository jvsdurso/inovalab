"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getJSON } from "@/lib/api";
import { COR_REL, NOME_REL } from "@/lib/format";
import { useComCarga, useSessao } from "@/lib/session";
import type { Relacao } from "@/lib/types";

export function Pendentes() {
  const { versao, avisar, recarregar } = useSessao();
  const { ocupado, executar } = useComCarga();
  const [rels, setRels] = useState<Relacao[] | null>(null);

  const carregar = useCallback(async () => {
    try { setRels((await getJSON<{ relacoes: Relacao[] }>("/relacoes?status=SUGERIDA")).relacoes); }
    catch (e) { avisar(e instanceof Error ? e.message : "Falha ao listar relações", true); }
  }, [avisar]);
  useEffect(() => { void carregar(); }, [carregar, versao]);

  const validar = (id: string, acao: "CONFIRMAR" | "REJEITAR") => executar(async () => {
    await api(`/relacoes/${id}/validar`, { method: "POST", body: { acao, motivo: "Validação humana na interface" } });
    avisar(`Relação ${acao === "CONFIRMAR" ? "confirmada" : "rejeitada"}; vigência recalculada.`);
    recarregar();
  });

  if (!rels) return <div className="vazio">Carregando…</div>;
  return (
    <>
      {rels.length
        ? <div className="aviso info">Relações sugeridas <b>não alteram a vigência</b> até serem confirmadas. Confirme ou rejeite após conferir a evidência.</div>
        : <div className="vazio">Nenhuma relação aguardando validação.</div>}
      {rels.map(x => (
        <div className="rel SUGERIDA" key={x.id}>
          <div>
            <b>{x.origem_titulo}</b>{x.origem_rotulo ? ` (${x.origem_rotulo})` : ""}{" "}
            <b style={{ color: COR_REL[x.tipo] }}>{NOME_REL[x.tipo]}</b>{" "}
            <b>{x.destino_titulo || x.destino_ref}</b>{x.destino_rotulo ? ` — ${x.destino_rotulo}` : ""}{" "}
            <small>· confiança {Math.round(x.confianca * 100)}%</small>
          </div>
          <div className="evid">{x.evidencia}</div>
          <div style={{ fontSize: 13, color: "#8a4504" }}>{x.nota_efeito || ""}</div>
          <div className="acoes" style={{ marginTop: 8 }}>
            <button className="ok" disabled={ocupado} onClick={() => validar(x.id, "CONFIRMAR")}>Confirmar</button>
            <button className="perigo" disabled={ocupado} onClick={() => validar(x.id, "REJEITAR")}>Rejeitar</button>
          </div>
        </div>
      ))}
    </>
  );
}
