"use client";

import { LINKS } from "@/lib/marca";
import { fmtData } from "@/lib/format";
import type { Pesquisa } from "@/lib/types";
import { Dialogo } from "../Dialogo";
import { Ligacao, Tag, TagSituacao, TagValidacao } from "../Tags";

/** Vigência das fontes DESTA resposta, exatamente como o sistema calculou (nada é "conferido" por este diálogo). */
export function ModalVigencia({ pesquisa, aoFechar }: { pesquisa: Pesquisa | null; aoFechar: () => void }) {
  return (
    <Dialogo aberto={!!pesquisa} aoFechar={aoFechar}>
      {pesquisa && (
        <div className="modal">
          <div className="modal-cab">
            <div><h2>Vigência das fontes desta resposta</h2><p>Situação em {fmtData(pesquisa.data)}, calculada pelo sistema a partir do acervo carregado</p></div>
            <button className="modal-x" onClick={aoFechar} aria-label="Fechar">✕</button>
          </div>
          <div className="modal-corpo">
            <div className="aviso info">
              Isto <b>não é uma consulta ao DOU</b>: mostra o que o acervo e as relações confirmadas indicam. Fontes sem validação jurídica humana
              devem ser conferidas no texto oficial antes do uso.
            </div>
            {pesquisa.fontes.length === 0 && <div className="vazio">Nenhuma fonte recuperada.</div>}
            {pesquisa.fontes.map(f => (
              <div className="vig-item" key={f.n}>
                <div className="vig-topo"><b>[{f.n}] {f.rotulo} — {f.ato}</b><TagSituacao situacao={f.situacao} /></div>
                <div><TagValidacao status={f.status_validacao} />{f.sintetico ? <Tag>Sintético</Tag> : null}<small> versão {f.versao_documento} do documento</small></div>
                <small className="muted">
                  Redação válida de {fmtData(f.valido_de)} {f.valido_ate ? `até ${fmtData(f.valido_ate)}` : "— em vigor"}
                  {f.redacao_dada_por ? ` · redação dada por ${f.redacao_dada_por}` : ""}{f.encerrada_por ? ` · encerrada por ${f.encerrada_por}` : ""}
                </small>
                <div><small>Documento: <Ligacao url={f.fonte_url} texto="abrir" /> · DOU: <Ligacao url={f.url_publicacao_dou} texto="abrir" /></small></div>
              </div>
            ))}
            {pesquisa.alertas.map((a, i) => <div className={`aviso${a.nivel === "info" ? " info" : ""}`} key={i}>{a.mensagem}</div>)}
          </div>
          <div className="modal-rodape">
            <a href={LINKS.portariasSenatran} target="_blank" rel="noopener noreferrer">Conferir no portal oficial de Portarias ↗</a>
            <button className="primario" onClick={aoFechar}>Concluir</button>
          </div>
        </div>
      )}
    </Dialogo>
  );
}
