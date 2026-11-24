// Tipos dos contratos da API (backend FastAPI, prefixo /api/v1). Espelham os dicts retornados pelos serviços.

export type Escopo = "NACIONAL" | "INSTITUCIONAL_RESTRITO" | "INSTITUCIONAL_COMPARTILHADO";
export type StatusObtencao = "OBTIDO" | "APENAS_INDICE" | "PENDENTE" | "FALHA";
export type StatusValidacao = "CONFIRMADO" | "PENDENTE" | "CONTROVERTIDO" | "REJEITADO";
export type StatusRelacao = "CONFIRMADA" | "SUGERIDA" | "REJEITADA";
export type TipoRelacao =
  | "ALTERA" | "REVOGA" | "REVOGA_PARCIALMENTE" | "REGULAMENTA"
  | "COMPLEMENTA" | "CONSOLIDA" | "SUSPENDE" | "RESTABELECE";

export interface Orgao { id: string; sigla: string; nome?: string }

export interface Me {
  login: string;
  nome: string;
  perfil: string;
  orgao: Orgao;
  auth_mode: string;
  llm: { provider: string; modelo: string; generativo: boolean };
  busca: { vetorial: boolean; modelo_embeddings: string | null };
}

export interface UsuarioDev { login: string; nome: string; orgao: string; perfil?: string }

export interface DocumentoResumo {
  id: string;
  escopo: Escopo;
  org_id: string;
  orgao: string;
  tipo: string;
  numero: string | null;
  ano: number | null;
  titulo: string;
  ementa: string | null;
  situacao: string;
  sintetico: number | boolean;
  n_dispositivos: number;
  versao_atual: number;
}

export interface VersaoDocumento { versao: number; hash: string; capturado_em: string | null }

export interface DocumentoDetalhe {
  id: string;
  escopo: Escopo;
  org_id: string;
  orgao: string | null;
  titulo: string;
  ementa: string | null;
  sintetico: number | boolean;
  data_publicacao: string | null;
  vigencia_inicio: string | null;
  vigencia_fim: string | null;
  versao_atual: number;
  versoes: VersaoDocumento[];
  alertas: string[];
  fonte_url: string | null;
  url_origem: string | null;
  url_publicacao_dou: string | null;
  data_assinatura: string | null;
  formato_original: string | null;
  status_obtencao: StatusObtencao;
  status_validacao: StatusValidacao;
}

export interface DispositivoCompilado {
  dispositivo_id: string;
  caminho: string;
  rotulo: string;
  nivel: number;
  grupo: string | null;
  texto: string;
  situacao: string;
  tipo_redacao: string;
  valido_de: string;
  valido_ate: string | null;
  n_redacoes: number;
  redacao_dada_por: string | null;
  encerrada_por: string | null;
}

export interface Compilado { data: string; situacao: string; dispositivos: DispositivoCompilado[] }

export interface Relacao {
  id: string;
  tipo: TipoRelacao;
  status: StatusRelacao;
  confianca: number;
  evidencia: string;
  nota_efeito: string | null;
  origem_documento_id: string;
  destino_documento_id: string | null;
  destino_ref: string | null;
  origem_titulo: string;
  destino_titulo: string | null;
  origem_rotulo: string | null;
  destino_rotulo: string | null;
}

export interface DocumentoResposta { documento: DocumentoDetalhe; compilado: Compilado; relacoes: Relacao[] }

export interface Redacao {
  id: string;
  tipo: string;
  texto: string;
  valido_de: string;
  valido_ate: string | null;
  motivo_fim: string | null;
  registrado_em: string | null;
  registrado_ate: string | null;
  redacao_dada_por: string | null;
}
export interface HistoricoDispositivo { rotulo: string; redacoes: Redacao[] }

export interface ResultadoImportacao {
  duplicado?: boolean;
  titulo: string;
  documento_id: string;
  nova_versao?: boolean;
  versao?: number;
  dispositivos: number;
  relacoes_detectadas: number;
  relacoes_pendentes: number;
  alertas: string[];
}

export interface Fonte { nome: string; url: string; funcao: string; utilizacao?: string | null; nota?: string | null }

export interface Hipotese {
  tipo: string;
  alvo_tipo?: string | null;
  numero?: string | null;
  ano?: number | string | null;
  resultado: string;
  observacao?: string | null;
}
export interface ItemCatalogo {
  id: string;
  titulo: string;
  status_obtencao: StatusObtencao;
  status_validacao: StatusValidacao;
  observacao: string | null;
  documento_id: string | null;
  url_documento: string | null;
  url_origem: string | null;
  url_publicacao_dou: string | null;
  relacoes_indice: unknown[];
  conferencia: Hipotese[];
}
export interface ItemPendencia { titulo: string; observacao?: string | null; faltando?: string[] }
export interface RelatorioCatalogo {
  total_itens: number;
  por_obtencao: Record<StatusObtencao, number>;
  por_validacao: Record<StatusValidacao, number>;
  divergencias_do_indice: unknown[];
  ausentes_ou_pendentes: ItemPendencia[];
  obtidos_sem_link_documento: ItemPendencia[];
  obtidos_sem_link_dou: ItemPendencia[];
  documentos_sem_origem_completa: ItemPendencia[];
}
export interface ResultadoLote {
  total: number; obtidos: number; apenas_referencia: number; duplicados: number; falhas: number;
  resultados: { ref: string; erro?: string }[];
}

export interface NoGrafo { id: string; titulo: string; escopo: Escopo; orgao: string; situacao: string }
export interface ArestaGrafo { origem: string; destino: string; tipo: TipoRelacao; qtd: number; pendentes: number; dispositivos: string[] }
export interface Grafo { nos: NoGrafo[]; arestas: ArestaGrafo[] }

export interface EventoAuditoria { em: string; login: string | null; acao: string; detalhes: unknown }

export interface VerificacaoCitacoes {
  citacoes_usadas?: number[];
  citacoes_invalidas?: number[];
  trechos_literais_nao_verificados?: string[];
  sem_citacoes?: boolean;
}

export interface FonteResposta {
  n: number;
  redacao_id: string;
  documento_id: string;
  rotulo: string;
  ato: string;
  situacao: string;
  sintetico?: number | boolean;
  status_validacao: StatusValidacao;
  versao_documento: number;
  fonte_url: string | null;
  url_origem?: string | null;
  url_publicacao_dou: string | null;
  valido_de: string;
  valido_ate: string | null;
  redacao_dada_por: string | null;
  encerrada_por: string | null;
  texto: string;
}

export interface Pesquisa {
  pergunta: string;
  data: string;
  resposta: string;
  modo: string;
  modelo: string;
  verificacao: VerificacaoCitacoes;
  fontes: FonteResposta[];
  alertas: { nivel: string; mensagem: string }[];
  execucao_id?: string;
}

export interface TipoMinuta { tipo: string; nome: string }
export interface MinutaResumo { id: string; titulo: string; status: string; autor: string; atualizado_em: string }
export interface SecaoMinuta { id: string; titulo: string; texto: string }
export interface Minuta {
  id: string;
  titulo: string;
  status: string;
  modo_geracao: string;
  data_referencia: string;
  secoes: SecaoMinuta[];
  verificacao?: VerificacaoCitacoes | null;
}
