"use client";

import { useState, type FormEvent } from "react";
import { getJSON } from "@/lib/api";
import { useComCarga, useSessao } from "@/lib/session";
import type { ResultadoImportacao } from "@/lib/types";
import { Dialogo } from "./Dialogo";

export function ImportarDialog({ aberto, aoFechar, aoImportado }: { aberto: boolean; aoFechar: () => void; aoImportado: (docId: string) => void }) {
  const { me, avisar, recarregar } = useSessao();
  const { ocupado, executar } = useComCarga();
  const [res, setRes] = useState<ResultadoImportacao | null>(null);
  const curador = me?.perfil === "CURADOR_NACIONAL";

  const enviar = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const arq = fd.get("arquivo");
    if (arq instanceof File && arq.size === 0) fd.delete("arquivo");
    void executar(async () => {
      const r = await getJSON<ResultadoImportacao>("/documentos", { method: "POST", form: fd });
      setRes(r);
      if (r.duplicado) return;
      avisar("Documento importado");
      recarregar();
      aoImportado(r.documento_id);
    });
  };

  return (
    <Dialogo aberto={aberto} aoFechar={() => { setRes(null); aoFechar(); }}>
      <form className="dlg" onSubmit={enviar}>
        <h3>Importar norma ou documento</h3>
        <label>Arquivo (TXT, HTML, PDF ou DOCX)<input type="file" name="arquivo" accept=".txt,.md,.html,.htm,.pdf,.docx" /></label>
        <label>…ou cole o texto<textarea name="texto" rows={6} placeholder={"RESOLUÇÃO Nº …, DE … DE … DE …\n\nArt. 1º …"} /></label>
        <label>Escopo
          <select name="escopo" defaultValue={curador ? "NACIONAL" : "INSTITUCIONAL_RESTRITO"} key={curador ? "c" : "n"}>
            <option value="INSTITUCIONAL_RESTRITO">Institucional restrito (somente o meu órgão)</option>
            <option value="INSTITUCIONAL_COMPARTILHADO">Institucional compartilhado</option>
            <option value="NACIONAL" disabled={!curador}>Nacional (curadoria)</option>
          </select>
        </label>
        <label>Link do documento (URL exata do ato — não use a página de índice)<input name="fonte_url" type="url" placeholder="https://…" /></label>
        <label>Link da página de origem (onde o documento foi localizado)<input name="url_origem" type="url" placeholder="https://…" /></label>
        <label>Link da publicação no DOU<input name="url_publicacao_dou" type="url" placeholder="https://www.in.gov.br/web/dou/…" /></label>
        <label>Data de assinatura<input name="data_assinatura" type="date" /></label>
        <p className="dica">O sistema extrai metadados, estrutura (art., §, incisos, alíneas), vigência e relações com outros atos. Não envie documentos sigilosos em ambiente de desenvolvimento.</p>
        <div className="linha fim">
          <button type="button" onClick={() => { setRes(null); aoFechar(); }}>Cancelar</button>
          <button className="primario" type="submit" disabled={ocupado}>{ocupado && <span className="spin" />}Importar</button>
        </div>
        {res && (res.duplicado
          ? <div className="aviso info">Este documento já existe com o mesmo conteúdo ({res.titulo}).</div>
          : <>
              <div className="aviso ok">
                <b>{res.titulo}</b> {res.nova_versao ? `(nova versão ${res.versao})` : "importado"}: {res.dispositivos} dispositivos,{" "}
                {res.relacoes_detectadas} relação(ões) detectada(s), {res.relacoes_pendentes} pendente(s) de validação.
              </div>
              {res.alertas.map((a, i) => <div className="aviso" key={i}>{a}</div>)}
            </>)}
      </form>
    </Dialogo>
  );
}
