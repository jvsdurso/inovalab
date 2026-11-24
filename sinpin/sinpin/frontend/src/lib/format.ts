export const hoje = (): string => new Date().toLocaleDateString("sv-SE");
export const fmtData = (d: string | null | undefined): string => (d ? d.split("-").reverse().join("/") : "—");
export const dataHora = (s: string | null | undefined): string => (s ? s.replace("T", " ").slice(0, 19) : "—");
export const urlSegura = (u: string | null | undefined): u is string => !!u && /^https?:\/\//i.test(u);

export const NOME_TIPO: Record<string, string> = {
  RESOLUCAO: "Resolução", LEI: "Lei", DECRETO: "Decreto", PORTARIA: "Portaria",
  INSTRUCAO_NORMATIVA: "Instrução Normativa", DELIBERACAO: "Deliberação",
};
export const NOME_REL: Record<string, string> = {
  ALTERA: "altera", REVOGA: "revoga", REVOGA_PARCIALMENTE: "revoga parcialmente", REGULAMENTA: "regulamenta",
  COMPLEMENTA: "complementa", CONSOLIDA: "consolida", SUSPENDE: "suspende", RESTABELECE: "restabelece",
};
export const COR_REL: Record<string, string> = {
  ALTERA: "#b45309", REVOGA: "#c8321b", REVOGA_PARCIALMENTE: "#e5702b", REGULAMENTA: "#1351b4",
  COMPLEMENTA: "#168821", CONSOLIDA: "#6b46c1", SUSPENDE: "#64748b", RESTABELECE: "#0e7490",
};
export const RES_CONF: Record<string, [string, string]> = {
  CONFIRMADA_NO_TEXTO: ["verde", "confirmada no texto"],
  DETECTADA_PENDENTE: ["lar", "detectada no texto, pendente"],
  NAO_ENCONTRADA_NO_TEXTO: ["verm", "NÃO encontrada no texto"],
  REJEITADA: ["verm", "rejeitada"],
  SEM_TEXTO: ["amar", "sem texto para conferir"],
  NAO_VERIFICAVEL: ["", "não verificável"],
};
