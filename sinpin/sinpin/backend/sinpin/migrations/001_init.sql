-- SINPIN :: esquema inicial
-- Convenções:
--  * ids de domínio são TEXT estáveis (uuid hex); orgao.id é o slug da sigla.
--  * datas jurídicas (valido_de/valido_ate/vigencia_*) = tempo VÁLIDO, formato AAAA-MM-DD, intervalo [de, ate).
--  * registrado_em/registrado_ate = tempo de SISTEMA (quando o SINPIN passou a conhecer/deixou de considerar).

CREATE TABLE orgao (
  id TEXT PRIMARY KEY,
  sigla TEXT NOT NULL,
  nome TEXT NOT NULL,
  registrado_em TEXT NOT NULL
);

CREATE TABLE usuario (
  id TEXT PRIMARY KEY,
  login TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES orgao(id),
  perfil TEXT NOT NULL CHECK (perfil IN ('SERVIDOR','ADMIN_ORGAO','CURADOR_NACIONAL')),
  ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE documento (
  id TEXT PRIMARY KEY,
  escopo TEXT NOT NULL CHECK (escopo IN ('NACIONAL','INSTITUCIONAL_COMPARTILHADO','INSTITUCIONAL_RESTRITO')),
  org_id TEXT NOT NULL REFERENCES orgao(id),
  tipo TEXT NOT NULL,
  numero TEXT,
  ano INTEGER,
  orgao_emissor TEXT,
  titulo TEXT NOT NULL,
  ementa TEXT,
  data_publicacao TEXT,
  vigencia_inicio TEXT,
  vigencia_fim TEXT,                 -- DERIVADO (revogação total); recalculado pelo módulo de vigência
  fonte_url TEXT,
  sintetico INTEGER NOT NULL DEFAULT 0,
  versao_atual INTEGER NOT NULL DEFAULT 1,
  alertas TEXT NOT NULL DEFAULT '[]',
  criado_por TEXT,
  registrado_em TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_documento_ident ON documento
  (org_id, tipo, (COALESCE(numero,'')), (COALESCE(ano,0)), (COALESCE(orgao_emissor,'')))
  WHERE numero IS NOT NULL;
CREATE INDEX ix_documento_escopo ON documento(escopo, org_id);

CREATE TABLE documento_versao (
  id TEXT PRIMARY KEY,
  documento_id TEXT NOT NULL REFERENCES documento(id),
  versao INTEGER NOT NULL,
  texto TEXT NOT NULL,
  hash TEXT NOT NULL,
  nome_arquivo TEXT,
  arquivo_chave TEXT,
  registrado_em TEXT NOT NULL,
  registrado_por TEXT,
  UNIQUE (documento_id, versao)
);

CREATE TABLE compartilhamento (
  documento_id TEXT NOT NULL REFERENCES documento(id),
  org_id TEXT NOT NULL REFERENCES orgao(id),
  PRIMARY KEY (documento_id, org_id)
);

-- Dispositivo = identidade ESTÁVEL de um artigo/§/inciso/alínea dentro do documento.
CREATE TABLE dispositivo (
  id TEXT PRIMARY KEY,
  documento_id TEXT NOT NULL REFERENCES documento(id),
  caminho TEXT NOT NULL,             -- ex.: art5.p1.inc2.alb
  nivel TEXT NOT NULL,               -- ARTIGO | PARAGRAFO | INCISO | ALINEA | TRECHO
  pai_caminho TEXT,
  grupo TEXT,                        -- capítulo/seção a que pertence
  ordem INTEGER NOT NULL DEFAULT 0,
  criado_por_relacao_id TEXT,        -- dispositivo incluído por um ato modificador
  registrado_em TEXT NOT NULL,
  UNIQUE (documento_id, caminho)
);
CREATE INDEX ix_dispositivo_doc ON dispositivo(documento_id);

-- Redação = texto de um dispositivo com seu intervalo de validade jurídica (bitemporal).
CREATE TABLE redacao (
  id TEXT PRIMARY KEY,
  dispositivo_id TEXT NOT NULL REFERENCES dispositivo(id),
  tipo TEXT NOT NULL CHECK (tipo IN ('ORIGINAL','ALTERACAO')),
  texto TEXT NOT NULL,
  valido_de TEXT NOT NULL,
  valido_ate TEXT,
  motivo_fim TEXT,                   -- REVOGADO | SUBSTITUIDO
  encerrada_por_relacao_id TEXT,
  origem_documento_id TEXT,          -- ato que deu esta redação (ALTERACAO)
  origem_relacao_id TEXT,
  versao_doc INTEGER,
  registrado_em TEXT NOT NULL,
  registrado_ate TEXT                -- NULL = ainda considerada pelo sistema
);
CREATE INDEX ix_redacao_disp ON redacao(dispositivo_id);

CREATE TABLE relacao (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL CHECK (tipo IN
    ('ALTERA','REVOGA','REVOGA_PARCIALMENTE','REGULAMENTA','COMPLEMENTA','CONSOLIDA','SUSPENDE','RESTABELECE')),
  origem_documento_id TEXT NOT NULL REFERENCES documento(id),
  origem_caminho TEXT,
  destino_documento_id TEXT REFERENCES documento(id),   -- NULL = referência ainda não resolvida
  destino_caminho TEXT,
  destino_tipo TEXT,
  destino_numero TEXT,
  destino_ano INTEGER,
  destino_emissor TEXT,
  destino_ref TEXT,                  -- referência literal encontrada no texto
  data_efeito TEXT,
  texto_novo TEXT,                   -- redação proposta (ALTERA)
  evidencia TEXT,                    -- trecho que sustenta a relação
  confianca DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('SUGERIDA','CONFIRMADA','REJEITADA')),
  origem_deteccao TEXT NOT NULL CHECK (origem_deteccao IN ('AUTO','MANUAL')),
  efeito_aplicado INTEGER NOT NULL DEFAULT 0,
  nota_efeito TEXT,
  validado_por TEXT,
  validado_em TEXT,
  registrado_em TEXT NOT NULL
);
CREATE INDEX ix_relacao_origem ON relacao(origem_documento_id);
CREATE INDEX ix_relacao_destino ON relacao(destino_documento_id);

CREATE TABLE relacao_historico (
  id TEXT PRIMARY KEY,
  relacao_id TEXT NOT NULL REFERENCES relacao(id),
  status_anterior TEXT,
  status_novo TEXT NOT NULL,
  por TEXT,
  em TEXT NOT NULL,
  motivo TEXT
);

CREATE TABLE auditoria (
  id TEXT PRIMARY KEY,
  em TEXT NOT NULL,
  usuario_id TEXT,
  org_id TEXT,
  acao TEXT NOT NULL,
  entidade TEXT,
  entidade_id TEXT,
  detalhes TEXT
);
CREATE INDEX ix_auditoria_org ON auditoria(org_id, em);

CREATE TABLE ia_execucao (
  id TEXT PRIMARY KEY,
  em TEXT NOT NULL,
  usuario_id TEXT,
  org_id TEXT,
  finalidade TEXT NOT NULL,
  provider TEXT NOT NULL,
  modelo TEXT,
  parametros TEXT,
  prompt_hash TEXT,
  pergunta TEXT,
  data_referencia TEXT,
  fontes TEXT,                       -- ids das redações usadas como fonte
  resposta TEXT,
  verificacao TEXT
);

CREATE TABLE minuta (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgao(id),
  usuario_id TEXT NOT NULL,
  tipo TEXT NOT NULL,
  assunto TEXT NOT NULL,
  titulo TEXT NOT NULL,
  secoes TEXT NOT NULL,              -- JSON [{id,titulo,texto}]
  fontes TEXT NOT NULL DEFAULT '[]', -- JSON (snapshot das fontes citáveis)
  data_referencia TEXT,
  modo_geracao TEXT,
  status TEXT NOT NULL DEFAULT 'RASCUNHO',
  criado_em TEXT NOT NULL,
  atualizado_em TEXT NOT NULL
);
