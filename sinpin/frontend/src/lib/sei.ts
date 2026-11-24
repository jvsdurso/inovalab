import { fmtData } from "./format";
import { escHtml, markdownParaHtml, markdownParaTexto } from "./markdown";
import type { FonteResposta } from "./types";

export interface DadosSei {
  unidade: string;
  tipo: string;
  processo: string;
  assunto: string;
  resposta: string;
  fontes: FonteResposta[];
  dataVigencia: string;
}

const PLACEHOLDER_PROCESSO = "[Nº DO PROCESSO SEI! A INFORMAR]";
const AVISO = "Rascunho gerado com apoio do SINPIN, sujeito a revisão e validação jurídica humana antes de qualquer assinatura.";

const linhaFonte = (f: FonteResposta) =>
  `[${f.n}] ${f.rotulo} — ${f.ato} (${f.situacao === "VIGENTE" ? "vigente" : f.situacao.toLowerCase()} em ${"%DATA%"}; versão ${f.versao_documento} do documento; validação jurídica: ${f.status_validacao.toLowerCase()})`;

const hojeExtenso = () => new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
const processo = (d: DadosSei) => d.processo.trim() || PLACEHOLDER_PROCESSO;

export function seiTexto(d: DadosSei): string {
  const base = d.fontes.map(f => "- " + linhaFonte(f).replace("%DATA%", fmtData(d.dataVigencia))).join("\n") || "- (nenhuma fonte recuperada)";
  return [
    "MINISTÉRIO DOS TRANSPORTES", "SECRETARIA NACIONAL DE TRÂNSITO (SENATRAN)", `UNIDADE: ${d.unidade}`, "",
    `${d.tipo.toUpperCase()} — PROCESSO SEI Nº ${processo(d)}`, `Assunto: ${d.assunto}`, `Brasília/DF, ${hojeExtenso()}.`, "",
    `1. ANÁLISE E FUNDAMENTAÇÃO NORMATIVA (vigência considerada: ${fmtData(d.dataVigencia)})`, markdownParaTexto(d.resposta), "",
    "2. BASE NORMATIVA CONSULTADA", base, "", AVISO,
  ].join("\n");
}

export function seiHtmlCorpo(d: DadosSei): string {
  const base = d.fontes.map(f => `<li>${escHtml(linhaFonte(f).replace("%DATA%", fmtData(d.dataVigencia)))}</li>`).join("") || "<li>(nenhuma fonte recuperada)</li>";
  return `
    <div style="text-align:center;border-bottom:1px solid #cbd5e1;padding-bottom:12px;margin-bottom:16px">
      <div style="font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase">República Federativa do Brasil</div>
      <div style="font-weight:700;font-size:16px;text-transform:uppercase">Ministério dos Transportes</div>
      <div style="font-weight:700;font-size:12px;text-transform:uppercase">Secretaria Nacional de Trânsito — ${escHtml(d.unidade)}</div>
    </div>
    <div style="font-size:12px;margin-bottom:12px">
      <div><b>Tipo de Documento:</b> ${escHtml(d.tipo)}</div>
      <div><b>Processo SEI nº:</b> ${escHtml(processo(d))}</div>
      <div><b>Assunto:</b> ${escHtml(d.assunto)}</div>
      <div style="text-align:right;font-style:italic">Brasília/DF, ${escHtml(hojeExtenso())}.</div>
    </div>
    <p style="font-weight:700;font-size:12px;text-transform:uppercase">1. Análise e Fundamentação Normativa (vigência considerada: ${escHtml(fmtData(d.dataVigencia))})</p>
    <div style="text-align:justify">${markdownParaHtml(d.resposta)}</div>
    <p style="font-weight:700;font-size:12px;text-transform:uppercase">2. Base Normativa Consultada</p>
    <ul style="font-size:12px">${base}</ul>
    <div style="margin-top:24px;padding-top:10px;border-top:1px solid #e2e8f0;text-align:center;font-size:11px;color:#64748b">${escHtml(AVISO)}</div>`;
}

export function seiHtmlCompleto(d: DadosSei): string {
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>${escHtml(d.tipo)} - SENATRAN</title>` +
    `<style>body{font-family:'Times New Roman',serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6;color:#111}</style></head><body>${seiHtmlCorpo(d)}</body></html>`;
}

export function baixar(conteudo: string, tipoMime: string, nome: string): void {
  const url = URL.createObjectURL(new Blob([conteudo], { type: `${tipoMime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url; a.download = nome;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function copiar(texto: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(texto); return true; } catch { /* tenta o método antigo */ }
  const t = document.createElement("textarea");
  t.value = texto; t.style.position = "fixed"; t.style.left = "-9999px";
  document.body.appendChild(t); t.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  document.body.removeChild(t);
  return ok;
}
