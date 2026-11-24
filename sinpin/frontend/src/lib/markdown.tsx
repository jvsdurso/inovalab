import { Fragment, type ReactNode } from "react";

/** Markdown mínimo e seguro: nunca injeta HTML (tudo vira elementos React). Suporta ## títulos, listas "-", **negrito** e citações [n]. */
function inline(s: string, aoCitar?: (n: number) => void): ReactNode[] {
  const partes: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|\[(\d+)\]/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(s)) !== null) {
    if (m.index > ultimo) partes.push(s.slice(ultimo, m.index));
    if (m[1] !== undefined) partes.push(<b key={i++}>{m[1]}</b>);
    else {
      const n = Number(m[2]);
      partes.push(<span key={i++} className="cite" role="button" tabIndex={0} onClick={() => aoCitar?.(n)}
        onKeyDown={e => { if (e.key === "Enter") aoCitar?.(n); }}>{n}</span>);
    }
    ultimo = m.index + m[0].length;
  }
  if (ultimo < s.length) partes.push(s.slice(ultimo));
  return partes;
}

export function Markdown({ texto, aoCitar }: { texto: string; aoCitar?: (n: number) => void }) {
  const blocos: ReactNode[] = [];
  let itens: string[] = [];
  const fechar = () => {
    if (itens.length) {
      const copia = itens;
      blocos.push(<ul key={`u${blocos.length}`}>{copia.map((t, i) => <li key={i}>{inline(t, aoCitar)}</li>)}</ul>);
      itens = [];
    }
  };
  for (const l of texto.split("\n")) {
    if (/^##\s+/.test(l)) { fechar(); blocos.push(<h2 key={`h${blocos.length}`}>{inline(l.replace(/^##\s+/, ""), aoCitar)}</h2>); }
    else if (/^\s*-\s+/.test(l)) itens.push(l.replace(/^\s*-\s+/, ""));
    else if (!l.trim()) fechar();
    else { fechar(); blocos.push(<p key={`p${blocos.length}`}>{inline(l, aoCitar)}</p>); }
  }
  fechar();
  return <Fragment>{blocos}</Fragment>;
}

const escHtml = (s: string) => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));

/** Mesma gramática de <Markdown>, mas como STRING HTML (já escapada) — usado na exportação .html para o SEI!. */
export function markdownParaHtml(texto: string): string {
  const inl = (s: string) => escHtml(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  let html = "", lista = false;
  const fechar = () => { if (lista) { html += "</ul>"; lista = false; } };
  for (const l of texto.split("\n")) {
    if (/^##\s+/.test(l)) { fechar(); html += `<h3>${inl(l.replace(/^##\s+/, ""))}</h3>`; }
    else if (/^\s*-\s+/.test(l)) { if (!lista) { html += "<ul>"; lista = true; } html += `<li>${inl(l.replace(/^\s*-\s+/, ""))}</li>`; }
    else if (!l.trim()) fechar();
    else { fechar(); html += `<p>${inl(l)}</p>`; }
  }
  fechar();
  return html;
}

/** Texto puro (sem marcação) para colar no editor do SEI!. */
export function markdownParaTexto(texto: string): string {
  return texto.replace(/^##\s+/gm, "").replace(/\*\*(.+?)\*\*/g, "$1");
}

export { escHtml };
