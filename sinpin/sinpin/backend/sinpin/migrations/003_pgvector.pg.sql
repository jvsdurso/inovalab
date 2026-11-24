-- pgvector (somente PostgreSQL). Dimensão fixa em 768 (ex.: nomic-embed-text). Para outra dimensão, ajuste ANTES da primeira
-- execução (ou crie uma nova migração) e configure SINPIN_EMBEDDING_DIM com o mesmo valor.
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE redacao ADD COLUMN embedding vector(768);

-- Índice aproximado (HNSW, distância de cosseno). A permissão é filtrada na consulta, nunca no índice.
CREATE INDEX ix_redacao_embedding ON redacao USING hnsw (embedding vector_cosine_ops);
