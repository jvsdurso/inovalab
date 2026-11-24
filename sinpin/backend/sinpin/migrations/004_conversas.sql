-- Conversas do pilar COMPREENDER (histórico de pesquisas por usuário, como num chat).
-- Cada mensagem guarda um SNAPSHOT (JSON) do que foi exibido na época: reabrir uma conversa mostra exatamente aquilo,
-- com a data de referência e as fontes/versões então usadas. A conversa é PRIVADA do usuário que a criou.
CREATE TABLE conversa (
  id TEXT PRIMARY KEY,
  usuario_id TEXT NOT NULL REFERENCES usuario(id),
  org_id TEXT NOT NULL REFERENCES orgao(id),
  titulo TEXT NOT NULL,
  criado_em TEXT NOT NULL,
  atualizado_em TEXT NOT NULL
);
CREATE INDEX ix_conversa_usuario ON conversa(usuario_id, atualizado_em);

CREATE TABLE conversa_mensagem (
  id TEXT PRIMARY KEY,
  conversa_id TEXT NOT NULL REFERENCES conversa(id),
  ordem INTEGER NOT NULL,
  papel TEXT NOT NULL,               -- 'usuario' | 'assistente'
  conteudo TEXT NOT NULL,            -- JSON
  criado_em TEXT NOT NULL,
  UNIQUE (conversa_id, ordem)
);
