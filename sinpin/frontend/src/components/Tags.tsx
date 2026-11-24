import type { ReactNode } from "react";
import { urlSegura } from "@/lib/format";
import type { Escopo, StatusObtencao, StatusRelacao, StatusValidacao } from "@/lib/types";

export function Tag({ cor = "", children }: { cor?: string; children: ReactNode }) {
  return <span className={`tag ${cor}`.trim()}>{children}</span>;
}

export function TagEscopo({ escopo }: { escopo: Escopo }) {
  if (escopo === "NACIONAL") return <Tag cor="azul">Nacional</Tag>;
  if (escopo === "INSTITUCIONAL_RESTRITO") return <Tag cor="lar">Restrito</Tag>;
  if (escopo === "INSTITUCIONAL_COMPARTILHADO") return <Tag cor="verde">Compartilhado</Tag>;
  return null;
}

const SIT: Record<string, [string, string]> = {
  VIGENTE: ["verde", "Vigente"], REVOGADA: ["verm", "Revogada"], REVOGADO: ["verm", "Revogado"],
  SUBSTITUIDO: ["lar", "Redação substituída"], NAO_INICIADA: ["amar", "Ainda não vigente"],
};
export function TagSituacao({ situacao }: { situacao: string }) {
  const [cor, txt] = SIT[situacao] ?? ["", situacao];
  return <Tag cor={cor}>{txt}</Tag>;
}

const STATUS_REL: Record<StatusRelacao, [string, string]> = {
  CONFIRMADA: ["verde", "Confirmada"], SUGERIDA: ["lar", "Pendente de validação"], REJEITADA: ["verm", "Rejeitada"],
};
export function TagStatusRelacao({ status }: { status: StatusRelacao }) {
  const [cor, txt] = STATUS_REL[status];
  return <Tag cor={cor}>{txt}</Tag>;
}

const OBT: Record<StatusObtencao, [string, string]> = {
  OBTIDO: ["verde", "Documento obtido"], APENAS_INDICE: ["amar", "Apenas referência do índice"],
  PENDENTE: ["lar", "Obtenção pendente"], FALHA: ["verm", "Falha na obtenção"],
};
export function TagObtencao({ status }: { status: StatusObtencao }) {
  const v = OBT[status];
  return v ? <Tag cor={v[0]}>{v[1]}</Tag> : null;
}

const VAL: Record<StatusValidacao, [string, string]> = {
  CONFIRMADO: ["verde", "Validação: confirmado"], PENDENTE: ["lar", "Validação jurídica pendente"],
  CONTROVERTIDO: ["amar", "Controvertido"], REJEITADO: ["verm", "Rejeitado"],
};
export function TagValidacao({ status }: { status: StatusValidacao }) {
  const v = VAL[status];
  return v ? <Tag cor={v[0]}>{v[1]}</Tag> : null;
}

/** Link externo: só http(s). Qualquer outra coisa (inclusive javascript:) vira "não registrado". */
export function Ligacao({ url, texto }: { url: string | null | undefined; texto: string }) {
  if (!urlSegura(url)) return <span className="falta">não registrado</span>;
  return <a href={url} target="_blank" rel="noopener noreferrer">{texto}</a>;
}
