"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { COR_REL, NOME_REL } from "@/lib/format";
import { useSessao } from "@/lib/session";
import type { Escopo, Grafo } from "@/lib/types";

const FAIXAS: Record<Escopo, number> = { NACIONAL: 190, INSTITUCIONAL_COMPARTILHADO: 300, INSTITUCIONAL_RESTRITO: 400 };
const curto = (t: string) => t.replace("Resolução", "Res.").replace("Instrução Normativa", "IN").replace("Portaria", "Port.").replace(/\s?(CONTRAN|SENATRAN|DETRAN-XX)/, "").replace(/ nº /, " ");

export function GrafoView({ aoAbrirDoc }: { aoAbrirDoc: (id: string) => void }) {
  const { versao, avisar } = useSessao();
  const [g, setG] = useState<Grafo | null>(null);

  useEffect(() => {
    let vivo = true;
    getJSON<Grafo>("/grafo").then(x => { if (vivo) setG(x); })
      .catch(e => avisar(e instanceof Error ? e.message : "Falha ao carregar o grafo", true));
    return () => { vivo = false; };
  }, [versao, avisar]);

  if (!g) return <div className="vazio">Carregando…</div>;
  const nos = g.nos;
  const W = Math.max(900, nos.length * 150 + 120);
  const H = 450;
  const pos: Record<string, { x: number; y: number }> = {};
  nos.forEach((n, i) => { pos[n.id] = { x: 90 + i * ((W - 180) / Math.max(1, nos.length - 1)), y: FAIXAS[n.escopo] }; });
  if (nos.length === 1) pos[nos[0].id].x = W / 2;
  const tipos = Array.from(new Set(g.arestas.map(a => a.tipo)));
  const cont: Record<string, number> = {};

  return (
    <>
      <div className="aviso info">Cada nó é um ato; cada seta, uma relação extraída do <b>texto</b> da norma (tracejada = pendente de validação). Clique em um ato para abrir.</div>
      <div className="grafo-wrap">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          <defs>
            {tipos.map(t => (
              <marker key={t} id={`m-${t}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0L10 5L0 10z" fill={COR_REL[t] || "#555"} />
              </marker>
            ))}
          </defs>
          <line x1="0" x2={W} y1="245" y2="245" stroke="#e6e9ee" /><line x1="0" x2={W} y1="350" y2="350" stroke="#e6e9ee" />
          {([["NACIONAL", 20], ["COMPARTILHADO", 262], ["RESTRITO DO ÓRGÃO", 367]] as const).map(([t, y]) => (
            <text key={t} x="8" y={y} fontSize="10.5" fill="#8a93a3" fontWeight="700" letterSpacing="1">{t}</text>
          ))}
          {g.arestas.map((a, idx) => {
            const o = pos[a.origem], d = pos[a.destino];
            if (!o || !d) return null;
            const par = [a.origem, a.destino].sort().join("|");
            const k = (cont[par] = (cont[par] || 0) + 1);
            const y1 = o.y + (d.y > o.y ? 24 : -24), y2 = d.y + (o.y > d.y ? 24 : -24);
            const x1 = o.x + (k - 1) * 12, x2 = d.x + (k - 1) * 12;
            let path: string;
            if (o.y === d.y) {
              const cy = o.y - 24 - Math.min(120, 36 + Math.abs(x2 - x1) / 4) - (k - 1) * 14;
              path = `M${x1} ${o.y - 24} Q${(x1 + x2) / 2} ${cy} ${x2} ${d.y - 24}`;
            } else {
              const my = (y1 + y2) / 2;
              path = `M${x1} ${y1} C${x1} ${my} ${x2} ${my} ${x2} ${y2}`;
            }
            const tip = `${NOME_REL[a.tipo]} (${a.qtd})${a.dispositivos.length ? " — " + a.dispositivos.join(", ") : ""}${a.pendentes ? ` · ${a.pendentes} pendente(s)` : ""}`;
            return (
              <path key={idx} d={path} fill="none" stroke={COR_REL[a.tipo] || "#555"} strokeWidth={2.2}
                strokeDasharray={a.pendentes ? "6 4" : undefined} markerEnd={`url(#m-${a.tipo})`}><title>{tip}</title></path>
            );
          })}
          {nos.map(n => {
            const p = pos[n.id];
            const rev = n.situacao === "REVOGADA";
            return (
              <g key={n.id} style={{ cursor: "pointer" }} transform={`translate(${p.x - 66},${p.y - 24})`} onClick={() => aoAbrirDoc(n.id)}>
                <title>{n.titulo}</title>
                <rect width="132" height="48" rx="9" fill={n.escopo === "NACIONAL" ? "#eef4fe" : "#fff7ec"} stroke={rev ? "#c8321b" : "#1351b4"}
                  strokeWidth={rev ? 2 : 1.4} strokeDasharray={rev ? "4 3" : undefined} />
                <text x="66" y="21" textAnchor="middle" fontSize="12.5" fontWeight="700" fill="#0c326f">{curto(n.titulo)}</text>
                <text x="66" y="38" textAnchor="middle" fontSize="10.5" fill={rev ? "#c8321b" : "#5b6472"}>{rev ? "REVOGADA" : n.orgao}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="legenda">
        {Object.keys(COR_REL).map(t => <span key={t}><i style={{ background: COR_REL[t] }} />{NOME_REL[t]}</span>)}
      </div>
    </>
  );
}
