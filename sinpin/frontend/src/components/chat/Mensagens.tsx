"use client";

import Link from "next/link";
import { useState } from "react";
import { fmtData, hoje } from "@/lib/format";
import { Markdown } from "@/lib/markdown";
import { copiar } from "@/lib/sei";
import { markdownParaTexto } from "@/lib/markdown";
import { useSessao } from "@/lib/session";
import type { Pesquisa } from "@/lib/types";
import { Ligacao, Tag, TagSituacao, TagValidacao } from "../Tags";

const hora = (iso: string) => {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

export function MensagemUsuario({ texto, data, quando }: { texto: string; data: string; quando: string }) {
  const { me } = useSessao();
  return (
    <div className="msg msg-usuario">
      <div className="bolha-usuario">
        <div className="bolha-cab"><span>Consulta Normativa • {me?.orgao.sigla ?? ""}</span><span>{hora(quando)}</span></div>
        <p>{texto}</p>
        <div className="bolha-rod">Vigência considerada: {fmtData(data)}</div>
      </div>
      <div className="avatar-col">
        <div className="avatar avatar-usuario">👤</div>
        <span className="avatar-rotulo">Servidor Público</span>
      </div>
    </div>
  );
}

export function Carregando() {
  return (
    <div className="msg">
      <div className="avatar avatar-sistema">⚖</div>
      <div className="bolha-carregando">
        <span className="pontos"><i /><i /><i /></span>
        <b>Pesquisando no acervo normativo…</b>
      </div>
    </div>
  );
}

export function MensagemErro({ texto }: { texto: string }) {
  return <div className="msg"><div className="avatar avatar-sistema">⚖</div><div className="aviso erro" style={{ flex: 1 }}>{texto}</div></div>;
}

interface PropsAssistente {
  idMsg: string;
  pesquisa: Pesquisa;
  quando: string;
  aoVigencia: (p: Pesquisa) => void;
  aoSei: (p: Pesquisa) => void;
  aoMinuta: (p: Pesquisa) => void;
  aoRepetir: (p: Pesquisa) => void;
}

export function MensagemAssistente({ idMsg, pesquisa: r, quando, aoVigencia, aoSei, aoMinuta, aoRepetir }: PropsAssistente) {
  const { avisar } = useSessao();
  const [destaque, setDestaque] = useState<number | null>(null);
  const v = r.verificacao ?? {};
  const antiga = r.data !== hoje() || quando.slice(0, 10) !== new Date().toISOString().slice(0, 10);

  const citar = (n: number) => {
    document.getElementById(`${idMsg}-f${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setDestaque(n);
    setTimeout(() => setDestaque(null), 1800);
  };

  return (
    <div className="msg">
      <div className="avatar avatar-sistema">⚖</div>
      <div className="msg-corpo">
        <div className="cartao-chat">
          <div className="cartao-chat-cab">
            <h2>1. Auxílio na montagem da resposta (minuta de resposta)</h2>
            <span className="selo-verde">{r.modo === "extrativo" ? "Modo extrativo (sem LLM)" : `Rascunho assistido • ${r.modelo}`}</span>
          </div>
          {v.citacoes_invalidas?.length ? <div className="aviso erro">A resposta citou fontes inexistentes: [{v.citacoes_invalidas.join("], [")}]. Desconsidere essas citações.</div> : null}
          {v.trechos_literais_nao_verificados?.length
            ? <div className="aviso erro">Trechos entre aspas que <b>não constam das fontes</b> recuperadas: {v.trechos_literais_nao_verificados.map(t => `«${t}…»`).join("; ")}</div> : null}
          {v.sem_citacoes ? <div className="aviso erro">A resposta não traz citações às fontes. Não a utilize sem conferência.</div> : null}
          <div className="resposta"><Markdown texto={r.resposta} aoCitar={citar} /></div>
          <div className="dica">Auxílio à pesquisa, não parecer. Interpretação e conclusão jurídica cabem ao servidor responsável.</div>
        </div>

        {r.alertas.length > 0 && (
          <div className="cartao-chat">
            <div className="cartao-chat-cab"><h2>Alertas de vigência e relações</h2></div>
            {r.alertas.map((a, i) => <div className={`aviso${a.nivel === "info" ? " info" : ""}`} key={i}>{a.mensagem}</div>)}
          </div>
        )}

        <div className="cartao-base">
          <div className="cartao-chat-cab"><h2>⚖ Base legal aplicada ({r.fontes.length})</h2><span className="muted">vigência em {fmtData(r.data)}</span></div>
          {r.fontes.length === 0 && <div className="vazio">Nenhuma fonte encontrada para esta pergunta no acervo visível ao seu órgão.</div>}
          <ul className="base-lista">
            {r.fontes.map(f => (
              <li key={f.n} id={`${idMsg}-f${f.n}`} className={destaque === f.n ? "alvo" : ""}>
                <span className="cite" role="button" tabIndex={0} onClick={() => citar(f.n)}>{f.n}</span>
                <div>
                  <strong>{f.rotulo} — {f.ato}</strong> <TagSituacao situacao={f.situacao} /><TagValidacao status={f.status_validacao} />
                  {f.sintetico ? <Tag>Sintético</Tag> : null}
                  <div className="muted">versão {f.versao_documento} · redação válida de {fmtData(f.valido_de)} {f.valido_ate ? `até ${fmtData(f.valido_ate)}` : "— em vigor"}{f.redacao_dada_por ? ` · dada por ${f.redacao_dada_por}` : ""}</div>
                  <details><summary>ver texto da redação</summary><blockquote>{f.texto}</blockquote></details>
                  <small>
                    <Link href={`/conhecer?doc=${encodeURIComponent(f.documento_id)}&data=${encodeURIComponent(r.data)}`}>abrir na biblioteca</Link>
                    {f.fonte_url && <> · <Ligacao url={f.fonte_url} texto="documento oficial" /></>}
                    {f.url_publicacao_dou && <> · <Ligacao url={f.url_publicacao_dou} texto="DOU" /></>}
                  </small>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="acoes-chat">
          <button className="pilula verde" onClick={async () => avisar((await copiar(markdownParaTexto(r.resposta))) ? "Minuta copiada para a área de transferência" : "Não foi possível copiar", false)}>Copiar minuta de resposta</button>
          <button className="pilula azul" onClick={() => aoVigencia(r)}>Verificar vigência das fontes</button>
          <button className="pilula azul-medio" onClick={() => aoSei(r)}>Exportar para o SEI!</button>
          <button className="pilula contorno" onClick={() => aoMinuta(r)}>Gerar minuta (PRODUZIR) →</button>
          {antiga && <button className="pilula contorno" onClick={() => aoRepetir(r)} title="Refaz a mesma pergunta com a vigência de hoje, nesta conversa">Repetir com a vigência de hoje</button>}
        </div>
        <div className="muted msg-hora">Resposta registrada em {hora(quando)} · {antiga ? "a norma pode ter mudado desde então" : "agora"}</div>
      </div>
    </div>
  );
}
