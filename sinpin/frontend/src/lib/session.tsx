"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, definirUsuario, getJSON, salvarUsuario, usuarioSalvo } from "./api";
import type { ConversaResumo, Me, Pesquisa, Relacao, UsuarioDev } from "./types";

interface Aviso { id: number; texto: string; erro: boolean }

interface Sessao {
  me: Me | null;
  usuarios: UsuarioDev[];
  login: string;
  trocarUsuario: (login: string) => void;
  /** Incrementa a cada troca de usuário/importação: telas recarregam seus dados. */
  versao: number;
  recarregar: () => void;
  avisar: (texto: string, erro?: boolean) => void;
  pendentes: number;
  atualizarPendentes: () => Promise<void>;
  ultimaPesquisa: Pesquisa | null;
  definirUltimaPesquisa: (p: Pesquisa | null) => void;
  conversas: ConversaResumo[];
  recarregarConversas: () => Promise<void>;
  excluirConversa: (id: string) => Promise<void>;
  /** Assunto sugerido para a minuta (vindo da pesquisa). */
  assuntoMinuta: { assunto: string; data: string } | null;
  definirAssuntoMinuta: (a: { assunto: string; data: string } | null) => void;
}

const Ctx = createContext<Sessao | null>(null);

export function useSessao(): Sessao {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSessao fora do SessaoProvider");
  return v;
}

export function SessaoProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [usuarios, setUsuarios] = useState<UsuarioDev[]>([]);
  const [login, setLogin] = useState("senatran.servidor");
  const [versao, setVersao] = useState(0);
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const [pendentes, setPendentes] = useState(0);
  const [ultimaPesquisa, definirUltimaPesquisa] = useState<Pesquisa | null>(null);
  const [assuntoMinuta, definirAssuntoMinuta] = useState<{ assunto: string; data: string } | null>(null);
  const [conversas, setConversas] = useState<ConversaResumo[]>([]);
  const seq = useRef(0);

  const avisar = useCallback((texto: string, erro = false) => {
    const id = ++seq.current;
    setAvisos(a => [...a, { id, texto, erro }]);
    setTimeout(() => setAvisos(a => a.filter(x => x.id !== id)), erro ? 7000 : 3500);
  }, []);

  const atualizarPendentes = useCallback(async () => {
    try {
      const r = await getJSON<{ relacoes: Relacao[] }>("/relacoes?status=SUGERIDA");
      setPendentes(r.relacoes.length);
    } catch { /* o badge é só informativo */ }
  }, []);

  const recarregarConversas = useCallback(async () => {
    try { setConversas((await getJSON<{ conversas: ConversaResumo[] }>("/conversas")).conversas); }
    catch { /* a lista é auxiliar */ }
  }, []);

  const excluirConversa = useCallback(async (id: string) => {
    try {
      await api(`/conversas/${id}`, { method: "DELETE" });
      setConversas(c => c.filter(x => x.id !== id));
    } catch (e) { avisar(e instanceof Error ? e.message : "Falha ao excluir a conversa", true); }
  }, [avisar]);

  const carregarMe = useCallback(async () => {
    try {
      setMe(await getJSON<Me>("/me"));
      await atualizarPendentes();
    } catch (e) {
      avisar(e instanceof Error ? e.message : "Falha ao carregar o usuário", true);
    }
  }, [atualizarPendentes, avisar]);

  // Inicialização: lista de usuários de desenvolvimento + usuário salvo.
  useEffect(() => {
    let vivo = true;
    (async () => {
      let lista: UsuarioDev[] = [];
      try {
        const r = await fetch("/api/v1/dev/usuarios");
        if (r.ok) lista = ((await r.json()) as { usuarios: UsuarioDev[] }).usuarios;
      } catch { /* modo sem autenticação de desenvolvimento */ }
      if (!vivo) return;
      let atual = usuarioSalvo();
      if (lista.length && !lista.some(u => u.login === atual)) atual = lista[0].login;
      definirUsuario(atual);
      setUsuarios(lista);
      setLogin(atual);
      await carregarMe();
      setVersao(v => v + 1);
    })();
    return () => { vivo = false; };
  }, [carregarMe]);

  // O histórico pertence ao usuário: recarrega a cada troca de usuário/dados.
  useEffect(() => { if (versao > 0) void recarregarConversas(); }, [versao, recarregarConversas]);

  const trocarUsuario = useCallback((novo: string) => {
    definirUsuario(novo);
    salvarUsuario(novo);
    setLogin(novo);
    definirUltimaPesquisa(null);
    definirAssuntoMinuta(null);
    setConversas([]);
    void carregarMe().then(() => setVersao(v => v + 1));
  }, [carregarMe]);

  const recarregar = useCallback(() => { void atualizarPendentes(); setVersao(v => v + 1); }, [atualizarPendentes]);

  const valor = useMemo<Sessao>(() => ({
    me, usuarios, login, trocarUsuario, versao, recarregar, avisar, pendentes, atualizarPendentes,
    ultimaPesquisa, definirUltimaPesquisa, assuntoMinuta, definirAssuntoMinuta,
    conversas, recarregarConversas, excluirConversa,
  }), [me, usuarios, login, trocarUsuario, versao, recarregar, avisar, pendentes, atualizarPendentes, ultimaPesquisa, assuntoMinuta,
    conversas, recarregarConversas, excluirConversa]);

  return (
    <Ctx.Provider value={valor}>
      {children}
      <div className="toast" aria-live="polite">
        {avisos.map(a => <div key={a.id} className={a.erro ? "err" : undefined}>{a.texto}</div>)}
      </div>
    </Ctx.Provider>
  );
}

/** Executa `fn` desabilitando o botão; erros viram aviso (toast). */
export function useComCarga() {
  const { avisar } = useSessao();
  const [ocupado, setOcupado] = useState(false);
  const executar = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setOcupado(true);
    try { return await fn(); }
    catch (e) { avisar(e instanceof Error ? e.message : "Erro inesperado", true); return undefined; }
    finally { setOcupado(false); }
  }, [avisar]);
  return { ocupado, executar };
}

export { api };
