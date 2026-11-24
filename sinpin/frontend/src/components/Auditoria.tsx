"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { useSessao } from "@/lib/session";
import type { EventoAuditoria } from "@/lib/types";

export function Auditoria() {
  const { versao, avisar } = useSessao();
  const [ev, setEv] = useState<EventoAuditoria[] | null>(null);
  useEffect(() => {
    let vivo = true;
    getJSON<{ eventos: EventoAuditoria[] }>("/auditoria").then(r => { if (vivo) setEv(r.eventos); })
      .catch(e => avisar(e instanceof Error ? e.message : "Falha ao carregar a auditoria", true));
    return () => { vivo = false; };
  }, [versao, avisar]);
  if (!ev) return <div className="vazio">Carregando…</div>;
  return (
    <div className="cartao">
      <h4>Trilha de auditoria do seu órgão</h4>
      <table className="t">
        <thead><tr><th>Quando (UTC)</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr></thead>
        <tbody>
          {ev.map((e, i) => (
            <tr key={i}>
              <td>{e.em.replace("T", " ").slice(0, 19)}</td><td>{e.login || "—"}</td><td><b>{e.acao}</b></td>
              <td style={{ fontSize: 12 }}>{JSON.stringify(e.detalhes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
