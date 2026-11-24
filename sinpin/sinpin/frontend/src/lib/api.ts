// Cliente HTTP. O navegador fala com /api/v1 (mesma origem); o Next encaminha ao backend (ver next.config.mjs).
// Autenticação de DESENVOLVIMENTO: cabeçalho X-Dev-User. Será substituída pelo login gov.br (OIDC) depois.

const BASE = "/api/v1";
const CHAVE_USUARIO = "sinpin_user";

export function usuarioSalvo(): string {
  try { return localStorage.getItem(CHAVE_USUARIO) || "senatran.servidor"; } catch { return "senatran.servidor"; }
}
export function salvarUsuario(login: string): void {
  try { localStorage.setItem(CHAVE_USUARIO, login); } catch { /* armazenamento indisponível */ }
}

let usuarioAtual = "senatran.servidor";
export function definirUsuario(login: string): void { usuarioAtual = login; }

export class ErroApi extends Error {
  constructor(msg: string, public status: number) { super(msg); }
}

interface Opcoes { method?: string; body?: unknown; form?: FormData }

export async function api(path: string, { method = "GET", body, form }: Opcoes = {}): Promise<Response> {
  const headers: Record<string, string> = { "X-Dev-User": usuarioAtual };
  let corpo: BodyInit | undefined;
  if (body !== undefined) { headers["Content-Type"] = "application/json"; corpo = JSON.stringify(body); }
  if (form) corpo = form;
  const r = await fetch(BASE + path, { method, headers, body: corpo, cache: "no-store" });
  if (!r.ok) {
    let msg = r.statusText || `Erro ${r.status}`;
    try {
      const j = (await r.json()) as { erro?: { mensagem?: string; detalhes?: { campo: string; erro: string }[] } };
      msg = j.erro?.mensagem || msg;
      if (j.erro?.detalhes) msg += " " + j.erro.detalhes.map(d => `${d.campo}: ${d.erro}`).join("; ");
    } catch { /* resposta sem JSON */ }
    throw new ErroApi(msg, r.status);
  }
  return r;
}

export async function getJSON<T>(path: string, opt?: Opcoes): Promise<T> {
  return (await api(path, opt)).json() as Promise<T>;
}
