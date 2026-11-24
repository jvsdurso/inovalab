"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Auditoria } from "@/components/Auditoria";
import { Biblioteca } from "@/components/Biblioteca";
import { Catalogo } from "@/components/Catalogo";
import { DocumentoView } from "@/components/DocumentoView";
import { GrafoView } from "@/components/GrafoView";
import { HistoricoDialog } from "@/components/HistoricoDispositivo";
import { ImportarDialog } from "@/components/ImportarDialog";
import { Pendentes } from "@/components/Pendentes";
import { getJSON } from "@/lib/api";
import { hoje } from "@/lib/format";
import { useSessao } from "@/lib/session";
import type { DocumentoResumo } from "@/lib/types";

type Aba = "doc" | "pend" | "cat" | "grafo" | "aud";
const ABAS: [Aba, string][] = [["doc", "Documento"], ["pend", "Relações pendentes"], ["cat", "Catálogo do acervo"], ["grafo", "Grafo normativo"], ["aud", "Auditoria"]];
const ALIAS: Record<string, Aba> = { doc: "doc", pend: "pend", pendentes: "pend", cat: "cat", catalogo: "cat", grafo: "grafo", aud: "aud", auditoria: "aud" };

/** Deep links: /conhecer?aba=grafo|pendentes|catalogo|auditoria, /conhecer?doc=<id>&data=AAAA-MM-DD, /conhecer?busca=<título>. */
export default function Conhecer() {
  const params = useSearchParams();
  const router = useRouter();
  const { pendentes, avisar } = useSessao();
  const [aba, setAba] = useState<Aba>(ALIAS[params.get("aba") ?? ""] ?? "doc");
  const [docId, setDocId] = useState<string | null>(params.get("doc"));
  const [data, setData] = useState(params.get("data") || hoje());
  const [importar, setImportar] = useState(false);
  const [histId, setHistId] = useState<string | null>(null);

  // Mudança de parâmetros (ex.: vindo de COMPREENDER) atualiza o estado.
  const chave = params.toString();
  useEffect(() => {
    const p = new URLSearchParams(chave);
    const a = ALIAS[p.get("aba") ?? ""];
    if (p.get("doc")) { setDocId(p.get("doc")); setAba("doc"); }
    else if (a) setAba(a);
    if (p.get("data")) setData(p.get("data") as string);
  }, [chave]);

  // ?busca= abre o primeiro documento cujo título/ementa contém o termo.
  useEffect(() => {
    const termo = new URLSearchParams(chave).get("busca");
    if (!termo) return;
    getJSON<{ documentos: DocumentoResumo[] }>("/documentos?q=" + encodeURIComponent(termo))
      .then(r => { if (r.documentos[0]) { setDocId(r.documentos[0].id); setAba("doc"); } })
      .catch(e => avisar(e instanceof Error ? e.message : "Falha na busca", true));
  }, [chave, avisar]);

  const fecharHistorico = useCallback(() => setHistId(null), []);
  const abrirDoc = useCallback((id: string, d?: string) => {
    setDocId(id); setAba("doc"); setData(d || hoje());
    router.replace("/conhecer");
  }, [router]);

  return (
    <section className="vista">
      <Biblioteca docId={docId} aoAbrir={id => abrirDoc(id)} aoImportar={() => setImportar(true)} />
      <div className="conteudo">
        <div className="abas">
          {ABAS.map(([k, t]) => (
            <button key={k} className={aba === k ? "ativo" : ""} onClick={() => setAba(k)}>
              {t}{k === "pend" && pendentes > 0 && <span className="badge">{pendentes}</span>}
            </button>
          ))}
        </div>
        {aba === "doc" && (docId
          ? <DocumentoView docId={docId} data={data} aoMudarData={setData} aoVerHistorico={setHistId} />
          : <div className="vazio">Selecione um documento na biblioteca ou importe uma norma.</div>)}
        {aba === "pend" && <Pendentes />}
        {aba === "cat" && <Catalogo aoAbrirDoc={id => abrirDoc(id)} />}
        {aba === "grafo" && <GrafoView aoAbrirDoc={id => abrirDoc(id)} />}
        {aba === "aud" && <Auditoria />}
      </div>
      <ImportarDialog aberto={importar} aoFechar={() => setImportar(false)} aoImportado={id => abrirDoc(id)} />
      <HistoricoDialog dispId={histId} aoFechar={fecharHistorico} />
    </section>
  );
}
