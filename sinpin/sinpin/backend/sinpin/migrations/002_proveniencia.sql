-- SINPIN :: proveniência documental e catálogo do acervo
-- documento.fonte_url passa a significar, SEMPRE, o LINK DO DOCUMENTO INDIVIDUAL (nunca página geral).
-- Os três endereços são campos distintos: documento (fonte_url), página de origem (url_origem) e publicação no DOU.

ALTER TABLE documento ADD COLUMN url_origem TEXT;
ALTER TABLE documento ADD COLUMN url_publicacao_dou TEXT;
ALTER TABLE documento ADD COLUMN data_assinatura TEXT;
ALTER TABLE documento ADD COLUMN formato_original TEXT;
ALTER TABLE documento ADD COLUMN status_obtencao TEXT NOT NULL DEFAULT 'OBTIDO'
  CHECK (status_obtencao IN ('OBTIDO','APENAS_INDICE','PENDENTE','FALHA'));
ALTER TABLE documento ADD COLUMN status_validacao TEXT NOT NULL DEFAULT 'PENDENTE'
  CHECK (status_validacao IN ('CONFIRMADO','PENDENTE','CONTROVERTIDO','REJEITADO'));

ALTER TABLE documento_versao ADD COLUMN capturado_em TEXT;   -- quando o arquivo foi capturado na fonte

-- Fontes oficiais monitoradas (páginas GERAIS: índices, portais, DOU). Não são documentos individuais.
CREATE TABLE fonte (
  id TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  url TEXT NOT NULL,
  funcao TEXT NOT NULL CHECK (funcao IN ('COMPILADO','INDICE','PUBLICACAO','PESQUISA','MONITORAMENTO','INSTITUCIONAL')),
  utilizacao TEXT,
  nota TEXT,
  registrado_em TEXT NOT NULL
);

-- Catálogo do acervo nacional: o que SE SABE que existe (inclusive o que ainda não foi obtido).
-- Item com status_obtencao = APENAS_INDICE é só uma referência ao índice: não há texto, nem efeito jurídico.
CREATE TABLE catalogo_item (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,
  numero TEXT NOT NULL,
  ano INTEGER NOT NULL,
  orgao_emissor TEXT,
  titulo TEXT NOT NULL,
  url_documento TEXT,
  url_origem TEXT,
  url_publicacao_dou TEXT,
  data_assinatura TEXT,
  data_publicacao TEXT,
  status_obtencao TEXT NOT NULL DEFAULT 'APENAS_INDICE'
    CHECK (status_obtencao IN ('OBTIDO','APENAS_INDICE','PENDENTE','FALHA')),
  status_validacao TEXT NOT NULL DEFAULT 'PENDENTE'
    CHECK (status_validacao IN ('CONFIRMADO','PENDENTE','CONTROVERTIDO','REJEITADO')),
  relacoes_indice TEXT NOT NULL DEFAULT '[]',  -- HIPÓTESES informadas pelo índice (JSON); sem efeito até confirmação no texto
  observacao TEXT,
  documento_id TEXT REFERENCES documento(id),
  registrado_em TEXT NOT NULL,
  atualizado_em TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_catalogo_ident ON catalogo_item (tipo, numero, ano, (COALESCE(orgao_emissor,'')));
CREATE INDEX ix_catalogo_status ON catalogo_item(status_obtencao);
