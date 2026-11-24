"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import { LINKS, MARCA } from "@/lib/marca";
import { useSessao } from "@/lib/session";
import { Brasao, LogoGovBr, LogoProduto, LosangoGov } from "./Marcas";

function BarraGov() {
  return (
    <div className="gov-barra">
      <div className="gov-barra-esq">
        <a href={LINKS.govbr} target="_blank" rel="noopener noreferrer" className="gov-barra-logo"><LosangoGov /><span>gov.br</span></a>
        <span className="gov-sep" />
        <span className="so-md">{MARCA.orgaoMinisterio} • {MARCA.orgaoSecretaria}</span>
      </div>
      <nav className="gov-barra-dir" aria-label="Links institucionais">
        <Link href="/conhecer" className="so-sm">Acesso à Informação</Link>
        <Link href="/conhecer" className="so-md">Legislação</Link>
        <a href={LINKS.portariasSenatran} target="_blank" rel="noopener noreferrer" className="dourado">Portarias {MARCA.orgaoSigla} ↗</a>
        <a href={LINKS.orgaosGoverno} target="_blank" rel="noopener noreferrer" className="so-lg">Órgãos do Governo</a>
      </nav>
    </div>
  );
}

function Cabecalho({ aoMenu }: { aoMenu: () => void }) {
  return (
    <header className="cabecalho">
      <div className="cab-esq">
        <button className="btn-menu" onClick={aoMenu} aria-label="Abrir menu lateral">☰</button>
        <Link href="/compreender" className="cab-marca"><LogoGovBr /><span className="gov-sep escuro so-sm" /><span className="cab-lema so-xl">{MARCA.lema}</span></Link>
      </div>
      <div className="cab-dir">
        <div className="cab-inst so-md">
          <div><div className="cab-min">{MARCA.orgaoMinisterio}</div><div className="cab-sec">{MARCA.orgaoSigla} • {MARCA.orgaoSecretaria}</div></div>
          <Brasao />
        </div>
        <span className="gov-sep escuro so-md" style={{ height: 36 }} />
        <div className="cab-produto">
          <span className="cab-logo-caixa"><LogoProduto /></span>
          <div>
            <div className="cab-produto-nome">{MARCA.nome}<span className="selo">{MARCA.orgaoSigla}</span></div>
            <p className="cab-produto-ext">{MARCA.extenso}</p>
          </div>
        </div>
      </div>
    </header>
  );
}

function Lateral({ aberta, fechar }: { aberta: boolean; fechar: () => void }) {
  const caminho = usePathname();
  const router = useRouter();
  const params = useSearchParams();
  const { me, usuarios, login, trocarUsuario, conversas, excluirConversa, pendentes } = useSessao();
  const [histAberto, setHistAberto] = useState(true);
  const ativa = caminho.startsWith("/compreender") ? params.get("c") : null;

  const ir = (href: string) => { fechar(); router.push(href); };
  const novaConsulta = () => ir(`/compreender?nova=${Date.now()}`);
  const excluir = async (id: string, titulo: string) => {
    if (!window.confirm(`Excluir a conversa “${titulo}”? Esta ação não pode ser desfeita.`)) return;
    await excluirConversa(id);
    if (ativa === id) ir(`/compreender?nova=${Date.now()}`);
  };
  const item = (href: string, rotulo: string, sub: string, selo?: ReactNode) => (
    <Link href={href} onClick={fechar} className={`nav-item${caminho.startsWith(href) ? " ativo-leve" : ""}`}>
      <span><b>{rotulo}</b><small>{sub}</small></span>{selo}
    </Link>
  );

  return (
    <>
      {aberta && <div className="lateral-fundo" onClick={fechar} />}
      <aside className={`menu${aberta ? " aberto" : ""}`}>
        <div className="menu-corpo">
          <div className="menu-secao">Atendimento Normativo</div>
          <button className="nav-principal" onClick={novaConsulta}>
            <span className="barra-dourada" />
            <span>💬 Nova Consulta (Chat)</span>
          </button>

          <button className="nav-item" onClick={() => setHistAberto(v => !v)} aria-expanded={histAberto}>
            <span><b>🕘 Histórico de Pesquisas</b><small>{conversas.length} conversa(s) — só você vê</small></span>
            <span className={`chevron${histAberto ? "" : " fechado"}`}>⌄</span>
          </button>
          {histAberto && (
            <div className="hist-lista">
              {conversas.length === 0 && <div className="hist-vazio">Nenhuma pesquisa ainda.</div>}
              {conversas.map(c => (
                <div key={c.id} className={`hist-item${ativa === c.id ? " ativo" : ""}`}>
                  <button className="hist-abrir" onClick={() => ir(`/compreender?c=${c.id}`)} title={c.titulo}>
                    <span className="hist-ponto" /><span className="hist-titulo">{c.titulo}</span>
                  </button>
                  <button className="hist-excluir" aria-label={`Excluir conversa ${c.titulo}`} onClick={() => excluir(c.id, c.titulo)}>✕</button>
                </div>
              ))}
            </div>
          )}

          <div className="menu-secao">Acervo & Minutas Oficiais</div>
          {item("/conhecer", "Biblioteca Normativa", "CONHECER — documentos, vigência, grafo", pendentes > 0 ? <span className="selo-ouro">{pendentes} pend.</span> : <span className="selo-ouro">Acervo</span>)}
          {item("/produzir", "Minutas", "PRODUZIR — editar e exportar DOCX/PDF")}
        </div>

        <div className="menu-rodape">
          {usuarios.length > 0 && (
            <label className="menu-dev">Usuário (desenvolvimento)
              <select value={login} onChange={e => trocarUsuario(e.target.value)}>
                {usuarios.map(u => <option key={u.login} value={u.login}>{u.orgao} · {u.nome}</option>)}
              </select>
            </label>
          )}
          <div className="menu-org"><span className="ponto-ouro" />{me ? `${me.orgao.sigla} · ${me.perfil.replace("_", " ").toLowerCase()}` : "…"}</div>
          <p className="menu-ia">
            {me ? (me.llm.generativo ? `IA: ${me.llm.provider} (${me.llm.modelo})` : "IA: modo extrativo (sem LLM)") : ""}
            {me?.busca.vetorial ? " · busca vetorial ativa" : " · busca lexical"}
          </p>
          {usuarios.length > 0 && <p className="menu-ia">Identidade simulada (login gov.br ainda não integrado). Dados de demonstração são sintéticos.</p>}
        </div>
      </aside>
    </>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const [menu, setMenu] = useState(false);
  return (
    <div className="shell">
      <BarraGov />
      <Cabecalho aoMenu={() => setMenu(v => !v)} />
      <div className="shell-corpo">
        <Lateral aberta={menu} fechar={() => setMenu(false)} />
        <main className="principal">{children}</main>
      </div>
    </div>
  );
}
