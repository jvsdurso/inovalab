"use client";

import { useEffect, useState } from "react";
import { MARCA, TIPOS_DOC_SEI, UNIDADES_SEI } from "@/lib/marca";
import { baixar, copiar, seiHtmlCompleto, seiHtmlCorpo, seiTexto, type DadosSei } from "@/lib/sei";
import { useSessao } from "@/lib/session";
import type { Pesquisa } from "@/lib/types";
import { Dialogo } from "../Dialogo";

export function ModalSei({ pesquisa, aoFechar }: { pesquisa: Pesquisa | null; aoFechar: () => void }) {
  const { avisar } = useSessao();
  const [unidade, setUnidade] = useState(UNIDADES_SEI[0]);
  const [tipo, setTipo] = useState(TIPOS_DOC_SEI[0]);
  const [processo, setProcesso] = useState("");
  const [assunto, setAssunto] = useState("");

  useEffect(() => { if (pesquisa) setAssunto(`Análise normativa — ${pesquisa.pergunta.slice(0, 120)}`); }, [pesquisa]);
  if (!pesquisa) return <Dialogo aberto={false} aoFechar={aoFechar}>{null}</Dialogo>;

  const dados: DadosSei = { unidade, tipo, processo, assunto, resposta: pesquisa.resposta, fontes: pesquisa.fontes, dataVigencia: pesquisa.data };
  const nome = `SEI_${tipo.toLowerCase().replace(/\s+/g, "_")}_${MARCA.orgaoSigla}`;

  return (
    <Dialogo aberto aoFechar={aoFechar}>
      <div className="modal modal-largo">
        <div className="modal-cab">
          <div><h2><span className="selo-ouro">SEI!</span> Exportar minuta para o SEI!</h2><p>Escolha a unidade, o tipo de documento e informe o número do processo</p></div>
          <button className="modal-x" onClick={aoFechar} aria-label="Fechar">✕</button>
        </div>
        <div className="sei-controles">
          <label>Unidade geradora<select value={unidade} onChange={e => setUnidade(e.target.value)}>{UNIDADES_SEI.map(u => <option key={u}>{u}</option>)}</select></label>
          <label>Tipo de documento<select value={tipo} onChange={e => setTipo(e.target.value)}>{TIPOS_DOC_SEI.map(u => <option key={u}>{u}</option>)}</select></label>
          <label>Nº do processo SEI!<input value={processo} onChange={e => setProcesso(e.target.value)} placeholder="00000.000000/0000-00" /></label>
          <label className="sei-assunto">Assunto<input value={assunto} onChange={e => setAssunto(e.target.value)} /></label>
        </div>
        {/* HTML montado só com texto escapado (escHtml / markdownParaHtml) */}
        <div className="sei-previa"><div className="sei-papel" dangerouslySetInnerHTML={{ __html: seiHtmlCorpo(dados) }} /></div>
        <div className="modal-rodape">
          <div className="grupo-botoes">
            <button onClick={() => { baixar(seiTexto(dados), "text/plain", `${nome}.txt`); avisar("Arquivo .TXT baixado"); }}>Baixar .TXT</button>
            <button onClick={() => { baixar(seiHtmlCompleto(dados), "text/html", `${nome}.html`); avisar("Arquivo .HTML baixado"); }}>Baixar .HTML</button>
          </div>
          <div className="grupo-botoes">
            <button onClick={aoFechar}>Fechar</button>
            <button className="verde" onClick={async () => avisar((await copiar(seiTexto(dados))) ? "Texto copiado. Cole no editor do SEI!" : "Não foi possível copiar", false)}>Copiar texto para o SEI!</button>
          </div>
        </div>
      </div>
    </Dialogo>
  );
}
