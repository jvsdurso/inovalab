"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSessao } from "@/lib/session";

const PILARES = [
  { href: "/conhecer", n: 1, nome: "CONHECER", sub: "Biblioteca, versões e grafo" },
  { href: "/compreender", n: 2, nome: "COMPREENDER", sub: "Pesquisa fundamentada" },
  { href: "/produzir", n: 3, nome: "PRODUZIR", sub: "Minutas e exportação" },
];

export function Topo() {
  const caminho = usePathname();
  const { me, usuarios, login, trocarUsuario } = useSessao();
  return (
    <>
      {usuarios.length > 0 && (
        <div className="devbar">
          Modo desenvolvimento: identidade simulada (login gov.br ainda não integrado). Dados de demonstração são <b>sintéticos</b>.
        </div>
      )}
      <header className="topo">
        <div className="marca">
          <div className="logo">SINPIN</div>
          <div className="sub">Sistema Nacional de Pesquisa<br />e Inteligência Normativa</div>
        </div>
        <nav className="pilares">
          {PILARES.map(p => (
            <Link key={p.href} href={p.href} className={`pilar${caminho.startsWith(p.href) ? " ativo" : ""}`}>
              <span className="n">{p.n}</span>
              <span><b>{p.nome}</b><small>{p.sub}</small></span>
            </Link>
          ))}
        </nav>
        <div className="usuario">
          {usuarios.length > 0 && (
            <label className="sel">Usuário{" "}
              <select value={login} onChange={e => trocarUsuario(e.target.value)}>
                {usuarios.map(u => <option key={u.login} value={u.login}>{u.orgao} · {u.nome}</option>)}
              </select>
            </label>
          )}
          <div className="chips">
            <span className="chip">{me ? `${me.orgao.sigla} · ${me.perfil.replace("_", " ").toLowerCase()}` : "…"}</span>
            <span className="chip">
              {me ? (me.llm.generativo ? `IA: ${me.llm.provider} (${me.llm.modelo})` : "IA: modo extrativo (sem LLM)") : "…"}
            </span>
            {me?.busca.vetorial && <span className="chip">Busca híbrida (vetorial)</span>}
          </div>
        </div>
      </header>
    </>
  );
}
