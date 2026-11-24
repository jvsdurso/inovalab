"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { useSessao } from "@/lib/session";
import type { DocumentoResumo } from "@/lib/types";
import { TagEscopo, TagSituacao, Tag } from "./Tags";

interface Props { docId: string | null; aoAbrir: (id: string) => void; aoImportar: () => void }

export function Biblioteca({ docId, aoAbrir, aoImportar }: Props) {
  const { versao, avisar } = useSessao();
  const [q, setQ] = useState("");
  const [docs, setDocs] = useState<DocumentoResumo[] | null>(null);

  useEffect(() => {
    let vivo = true;
    const t = setTimeout(async () => {
      try {
        const r = await getJSON<{ documentos: DocumentoResumo[] }>("/documentos" + (q.trim() ? "?q=" + encodeURIComponent(q.trim()) : ""));
        if (vivo) setDocs(r.documentos);
      } catch (e) { if (vivo) avisar(e instanceof Error ? e.message : "Falha ao listar documentos", true); }
    }, q ? 250 : 0);
    return () => { vivo = false; clearTimeout(t); };
  }, [q, versao, avisar]);

  const classe = (e: string) => (e === "NACIONAL" ? "nac" : e === "INSTITUCIONAL_RESTRITO" ? "res" : "comp");

  return (
    <aside className="lateral">
      <div className="linha">
        <input type="search" placeholder="Filtrar por título ou ementa…" value={q} onChange={e => setQ(e.target.value)} />
        <button className="primario" onClick={aoImportar}>Importar</button>
      </div>
      <div className="lista">
        {docs === null && <div className="vazio">Carregando…</div>}
        {docs?.length === 0 && <div className="vazio">Nenhum documento visível para o seu órgão.</div>}
        {docs?.map(d => (
          <div key={d.id} className={`item ${classe(d.escopo)}${d.id === docId ? " ativo" : ""}`} onClick={() => aoAbrir(d.id)}>
            <b>{d.titulo}</b>
            <div className="em">{d.ementa || "(sem ementa identificada)"}</div>
            <div>
              <TagEscopo escopo={d.escopo} /><TagSituacao situacao={d.situacao} />
              {d.sintetico ? <Tag>Sintético</Tag> : null}<Tag>{d.orgao}</Tag>
              <small>{d.n_dispositivos} disp. · v{d.versao_atual}</small>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
