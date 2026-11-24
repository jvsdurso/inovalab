"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { fmtData } from "@/lib/format";
import { useSessao } from "@/lib/session";
import type { HistoricoDispositivo } from "@/lib/types";
import { Dialogo } from "./Dialogo";
import { Tag } from "./Tags";

export function HistoricoDialog({ dispId, aoFechar }: { dispId: string | null; aoFechar: () => void }) {
  const { avisar } = useSessao();
  const [h, setH] = useState<HistoricoDispositivo | null>(null);

  useEffect(() => {
    if (!dispId) { setH(null); return; }
    let vivo = true;
    getJSON<HistoricoDispositivo>(`/dispositivos/${dispId}/historico`)
      .then(r => { if (vivo) setH(r); })
      .catch(e => { avisar(e instanceof Error ? e.message : "Falha ao carregar o histórico", true); aoFechar(); });
    return () => { vivo = false; };
  }, [dispId, avisar, aoFechar]);

  return (
    <Dialogo aberto={!!dispId && !!h} aoFechar={aoFechar}>
      <div className="dlg">
        {h && (
          <>
            <h3>{h.rotulo} — histórico de redações</h3>
            <div className="linha-tempo">
              {h.redacoes.map(r => (
                <div className="ev" key={r.id}>
                  <b>{r.tipo === "ORIGINAL" ? "Redação original" : `Redação dada por ${r.redacao_dada_por || "ato modificador"}`}</b>{" "}
                  {r.registrado_ate && <Tag>substituída por nova versão do documento</Tag>}<br />
                  <small>
                    Válida de {fmtData(r.valido_de)} {r.valido_ate ? `até ${fmtData(r.valido_ate)} (${r.motivo_fim || ""})` : "— em vigor"}
                    {" "}· registrada em {(r.registrado_em || "").slice(0, 10)}
                  </small>
                  <div className="disp" style={{ gridTemplateColumns: "1fr", padding: "6px 0" }}><div className="tx">{r.texto}</div></div>
                </div>
              ))}
            </div>
            <div className="linha fim"><button onClick={aoFechar}>Fechar</button></div>
          </>
        )}
      </div>
    </Dialogo>
  );
}
