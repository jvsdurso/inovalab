"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Carregando, MensagemAssistente, MensagemErro, MensagemUsuario } from "@/components/chat/Mensagens";
import { ModalSei } from "@/components/chat/ModalSei";
import { ModalVigencia } from "@/components/chat/ModalVigencia";
import { getJSON } from "@/lib/api";
import { hoje } from "@/lib/format";
import { MARCA, PERGUNTAS_EXEMPLO } from "@/lib/marca";
import { useSessao } from "@/lib/session";
import type { Conversa, Pesquisa } from "@/lib/types";

type Item =
  | { tipo: "usuario"; id: string; texto: string; data: string; quando: string }
  | { tipo: "assistente"; id: string; pesquisa: Pesquisa; quando: string }
  | { tipo: "erro"; id: string; texto: string };

let contador = 0;
const novoId = () => `m${++contador}`;

function converter(cv: Conversa): Item[] {
  return cv.mensagens.map((m): Item => {
    if (m.papel === "usuario") {
      const c = m.conteudo as { texto: string; data: string };
      return { tipo: "usuario", id: m.id, texto: c.texto, data: c.data, quando: m.criado_em };
    }
    return { tipo: "assistente", id: m.id, pesquisa: m.conteudo as Pesquisa, quando: m.criado_em };
  });
}

/**
 * Chat do COMPREENDER. A URL manda: /compreender?c=<id> abre a conversa COMPLETA (do servidor, como no ChatGPT);
 * /compreender (ou ?nova=...) é uma conversa em branco. Cada pergunta é uma pesquisa independente (sem memória entre perguntas).
 * Deep link: /compreender?q=...&data=AAAA-MM-DD executa a pergunta ao abrir.
 */
export default function Compreender() {
  const params = useSearchParams();
  const router = useRouter();
  const { me, versao, avisar, recarregarConversas, definirUltimaPesquisa, definirAssuntoMinuta } = useSessao();
  const [itens, setItens] = useState<Item[]>([]);
  const [conversaId, setConversaId] = useState<string | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [abrindo, setAbrindo] = useState(false);
  const [texto, setTexto] = useState("");
  const [data, setData] = useState(hoje());
  const [modalVig, setModalVig] = useState<Pesquisa | null>(null);
  const [modalSei, setModalSei] = useState<Pesquisa | null>(null);
  const pularCarga = useRef<string | null>(null);
  const executouQuery = useRef(false);
  const fim = useRef<HTMLDivElement>(null);

  const chave = params.toString();
  useEffect(() => {
    const id = new URLSearchParams(chave).get("c");
    if (!id) { setItens([]); setConversaId(null); return; }
    if (pularCarga.current === id) { pularCarga.current = null; return; } // conversa que acabamos de criar: já está na tela
    if (!me) return;
    let vivo = true;
    setAbrindo(true);
    getJSON<Conversa>(`/conversas/${id}`)
      .then(cv => { if (vivo) { setConversaId(cv.id); setItens(converter(cv)); } })
      .catch(e => { if (vivo) { avisar(e instanceof Error ? e.message : "Conversa não encontrada", true); router.replace("/compreender"); } })
      .finally(() => { if (vivo) setAbrindo(false); });
    return () => { vivo = false; };
  }, [chave, me, versao, avisar, router]);

  useEffect(() => { fim.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [itens, buscando]);

  const enviar = useCallback(async (pergunta: string, dataRef: string, conversa: string | null) => {
    const q = pergunta.trim();
    if (q.length < 3) { avisar("Digite uma dúvida normativa ou caso prático para consultar.", true); return; }
    setTexto("");
    setItens(x => [...x, { tipo: "usuario", id: novoId(), texto: q, data: dataRef, quando: new Date().toISOString() }]);
    setBuscando(true);
    try {
      const r = await getJSON<Pesquisa>("/pesquisa", { method: "POST", body: { pergunta: q, data: dataRef || hoje(), conversa_id: conversa ?? undefined } });
      setItens(x => [...x, { tipo: "assistente", id: novoId(), pesquisa: r, quando: new Date().toISOString() }]);
      definirUltimaPesquisa(r);
      if (r.conversa_id && r.conversa_id !== conversa) {
        pularCarga.current = r.conversa_id;
        setConversaId(r.conversa_id);
        router.replace(`/compreender?c=${r.conversa_id}`);
      }
      void recarregarConversas();
    } catch (e) {
      setItens(x => [...x, { tipo: "erro", id: novoId(), texto: e instanceof Error ? e.message : "Falha na pesquisa" }]);
    } finally {
      setBuscando(false);
    }
  }, [avisar, definirUltimaPesquisa, recarregarConversas, router]);

  useEffect(() => {
    const p = new URLSearchParams(chave);
    if (executouQuery.current || !p.get("q") || !me) return;
    executouQuery.current = true;
    void enviar(p.get("q") as string, p.get("data") || hoje(), null);
  }, [chave, me, enviar]);

  const aoEnviar = (e: FormEvent) => { e.preventDefault(); void enviar(texto, data, conversaId); };
  const aoMinuta = (p: Pesquisa) => { definirUltimaPesquisa(p); definirAssuntoMinuta({ assunto: p.pergunta.slice(0, 200), data: p.data }); router.push("/produzir"); };
  const vazio = itens.length === 0 && !buscando && !abrindo;

  return (
    <div className="chat">
      <div className="chat-subcab">
        <h1>Fundamentação de Pareceres • {me?.orgao.sigla ?? MARCA.orgaoSigla}</h1>
        <div className="chat-subcab-dir">
          <span className="selo-azul">Base: acervo normativo do seu órgão</span>
          <button className="primario-leve" onClick={() => router.push(`/compreender?nova=${Date.now()}`)}>🗑 Nova Consulta</button>
        </div>
      </div>

      <div className="chat-mensagens">
        {abrindo && <div className="vazio">Abrindo conversa…</div>}
        {vazio && (
          <div className="chat-boas-vindas">
            <div className="chat-boas-icone">⚖</div>
            <span className="selo-azul">{MARCA.orgaoMinisterio} • {MARCA.orgaoSigla}</span>
            <h2>Nova Consulta Normativa de Trânsito</h2>
            <p>Digite sua dúvida jurídica ou caso administrativo. A resposta é montada <b>somente</b> com trechos do acervo carregado, com citação, versão e vigência na data escolhida — ou diz que não encontrou.</p>
          </div>
        )}
        {itens.map(i => i.tipo === "usuario"
          ? <MensagemUsuario key={i.id} texto={i.texto} data={i.data} quando={i.quando} />
          : i.tipo === "erro"
            ? <MensagemErro key={i.id} texto={i.texto} />
            : <MensagemAssistente key={i.id} idMsg={i.id} pesquisa={i.pesquisa} quando={i.quando}
                aoVigencia={setModalVig} aoSei={setModalSei} aoMinuta={aoMinuta}
                aoRepetir={p => void enviar(p.pergunta, hoje(), conversaId)} />)}
        {buscando && <Carregando />}
        <div ref={fim} />
      </div>

      <div className="chat-entrada">
        <div className="chips-tema">
          <span>Exemplos:</span>
          {PERGUNTAS_EXEMPLO.map(p => <button key={p.rotulo} type="button" onClick={() => setTexto(p.pergunta)}>{p.rotulo}</button>)}
        </div>
        <form className="chat-form" onSubmit={aoEnviar}>
          <input className="chat-input" value={texto} onChange={e => setTexto(e.target.value)} autoComplete="off"
            placeholder="Digite sua dúvida normativa ou caso prático…" />
          <label className="chat-data" title="Data de vigência considerada na resposta">Vigência em
            <input type="date" value={data} onChange={e => setData(e.target.value || hoje())} />
          </label>
          <button className="chat-enviar" type="submit" disabled={buscando}>{buscando ? "Consultando…" : `Consultar ${MARCA.nome}`}</button>
        </form>
      </div>

      <ModalVigencia pesquisa={modalVig} aoFechar={() => setModalVig(null)} />
      <ModalSei pesquisa={modalSei} aoFechar={() => setModalSei(null)} />
    </div>
  );
}
