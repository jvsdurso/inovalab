# SINPIN — Sistema Nacional de Pesquisa e Inteligência Normativa (MVP)

Três pilares sobre a norma vigente, com rastreabilidade de fonte: **CONHECER** (biblioteca, versões, vigência por data, grafo de relações, catálogo do acervo), **COMPREENDER** (pesquisa fundamentada com citações verificadas) e **PRODUZIR** (minutas editáveis, exportação DOCX/PDF).

## Stack (a definida no prompt-mestre)

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript estrito — `frontend/` |
| Backend | Python 3.12 + FastAPI (OpenAPI em `/docs`), monólito modular — `backend/sinpin/` |
| Banco | PostgreSQL 16 + **pgvector** (`vector(768)`, índice HNSW, busca híbrida BM25 + vetor) |
| Infra | Docker / docker compose (`db`, `backend`, `frontend`) |
| Adiados (fora do MVP) | Redis, Keycloak/OIDC (login gov.br), armazenamento S3, workers, OpenTelemetry |

SQLite existe **apenas** como driver de teste offline (a suíte de domínio roda sem Postgres). Em execução normal o banco é o PostgreSQL.

## Rodar

> **Primeira vez?** Siga o [`docs/PASSO_A_PASSO.md`](docs/PASSO_A_PASSO.md): cada passo de configuração está explicado, com como conferir e o que fazer se falhar.


```bash
cp .env.example .env          # opcional: chaves de IA / embeddings
docker compose up --build
```

- Interface: <http://localhost:3000> · API e OpenAPI: <http://localhost:8000/docs>
- Com `SINPIN_SEED_DEMO=1` (padrão do compose) carrega normas **sintéticas** de demonstração. Use `0` em qualquer uso real.
- Sem chave de IA o sistema responde em **modo extrativo** (sem LLM), de forma explícita na tela.

### Sem Docker (desenvolvimento)

```bash
# banco: qualquer PostgreSQL 16 com a extensão pgvector (ex.: docker run -p 5432:5432 -e POSTGRES_USER=sinpin -e POSTGRES_PASSWORD=sinpin -e POSTGRES_DB=sinpin pgvector/pgvector:pg16)
cd backend && pip install -r requirements.txt
SINPIN_SEED_DEMO=1 python -m sinpin --port 8000          # SINPIN_DATABASE_URL padrão: postgresql://sinpin:sinpin@localhost:5432/sinpin
cd ../frontend && npm install && npm run dev              # http://localhost:3000 (proxy /api -> http://localhost:8000; mude com BACKEND_URL)
```

### Testes

```bash
cd backend
python -m pytest -q                                                       # domínio, em SQLite (sem Postgres)
SINPIN_TEST_DATABASE_URL=postgresql://sinpin:sinpin@localhost:5432/sinpin_teste python -m pytest -q   # a MESMA suíte em PostgreSQL + pgvector (crie o banco antes)
cd ../frontend && npm run typecheck && npm run build
```

### Busca vetorial (opcional)

Qualquer endpoint compatível com a API `/embeddings` da OpenAI. Exemplo com Ollama local:

```bash
ollama pull nomic-embed-text      # 768 dimensões, igual ao esquema
# .env:
SINPIN_EMBEDDING_BASE_URL=http://host.docker.internal:11434/v1
SINPIN_EMBEDDING_MODEL=nomic-embed-text
```

Sem provedor, a busca é só lexical. **Privacidade:** com provedor de embeddings *remoto*, o texto de documentos restritos sai da infraestrutura do órgão — prefira provedor local/institucional para acervo restrito. O filtro de permissão é aplicado dentro da própria consulta SQL (vetorial e lexical).

## Roteiro de demonstração (≈ 5 min)

1. **CONHECER → Grafo normativo:** Lei → Res. 101/2018 → alterada pelas Res. 215/2021 e 340/2023; Res. 52/2012 revogada pela 101. Abra a Res. 101 e mude "Texto compilado em" (ex.: 2019 × 2024): o Art. 5º passa de 30 para 60 dias; o Art. 6º some (revogado); o 5º-A só existe a partir de 2021.
2. **COMPREENDER:** clique no exemplo "Mesma pergunta, como era em 01/01/2019" e depois a pergunta sem data. Veja a resposta mudar, os alertas de vigência e as citações `[n]` que levam à fonte.
3. **Isolamento:** troque o usuário (topo) para *DETRAN-XX* e pergunte "indício de fraude documental": a portaria restrita da SENATRAN não aparece em lugar nenhum (lista, busca, grafo, minuta).
4. **PRODUZIR:** "Gerar minuta a partir desta pesquisa" → edite as seções → exporte DOCX/PDF. As seções analíticas ficam `[A PREENCHER]` em modo extrativo (o sistema não finge análise).
5. **Validação humana:** importe uma norma que cite um ato ainda inexistente na base: a relação fica *pendente* e só produz efeito após confirmada (aba "Relações pendentes").

## Acervo e proveniência (definição do acervo)

Cada documento guarda **três endereços distintos**: link do documento individual, link da página de origem e link da publicação no DOU — além de data de assinatura/publicação, formato original, data/hora de captura, **SHA-256**, status de obtenção (`OBTIDO`, `APENAS_INDICE`, `PENDENTE`, `FALHA`) e status de validação jurídica humana (`CONFIRMADO`, `PENDENTE`, `CONTROVERTIDO`, `REJEITADO`).

- **Aba “Catálogo do acervo”:** o que se sabe que existe (inclusive o não obtido), relações informadas por índice **conferidas contra o texto** do ato, relatório de pendências e as fontes oficiais monitoradas. Os 6 atos do índice CONTRAN do contexto do projeto entram como *apenas referência* na demonstração; nenhum link ou texto foi inventado.
- **Página geral nunca vira link de documento:** os índices/portais/DOU cadastrados em `fonte` são recusados como `url_documento` e `url_publicacao_dou`.
- **Pesquisa:** cada fonte citada mostra versão do documento, link e status de validação; o sistema avisa quando a fonte não tem validação humana (“presença no acervo não atesta vigência”).
- **Carga em lote:** `.zip` com `manifesto.json` + originais — formato em [`docs/formato_pacote_acervo.md`](docs/formato_pacote_acervo.md).
- **Ainda não faz:** monitorar fontes e baixar sozinho (não há rotina de coleta/crawler; a captura é feita por quem entrega o pacote), OCR, nem “controvertido” em *relações* (só em documentos).

## Arquitetura (monólito modular)

`backend/sinpin/<módulo>/service.py` é o contrato público de cada módulo; módulos não leem tabelas uns dos outros (exceção documentada: `vigencia` usa `grafo.repo`).

| Módulo | Responsabilidade |
|---|---|
| `identidade` | Contexto (usuário/órgão/perfil) e **a única regra de visibilidade** (`sql_visivel`), aplicada em toda consulta |
| `orgaos`, `auditoria` | Cadastro de órgãos; trilha append-only por órgão |
| `ingestao` | TXT/HTML/PDF/DOCX → texto → metadados → dispositivos → relações → vigência (numa transação) |
| `catalogo` | Catálogo do acervo, fontes oficiais, proveniência (3 links), conferência do índice × texto, carga em lote (.zip) |
| `normativo` | Parser (art., §, incisos, alíneas), documentos versionados, texto compilado por data, histórico |
| `grafo` | Detecção por texto (altera, revoga, revoga parcialmente, regulamenta, complementa, consolida, suspende, restabelece), resolução de destino, validação humana |
| `vigencia` | Aplica efeitos das relações confirmadas sobre as redações (recálculo idempotente) |
| `pesquisa` | Busca **híbrida** (BM25 + vetor pgvector, quando há provedor de embeddings) com o filtro de permissão dentro da própria consulta; classificada por vigência na data |
| `ia` | Provedores (extrativo / Anthropic / OpenAI-compatível), prompts, **verificação de citações**, registro de execuções |
| `producao` | Modelos de documento, geração de minuta, exportação DOCX/PDF |

Modelo temporal (bitemporal): `redacao.valido_de/valido_ate` = validade jurídica; `registrado_em/registrado_ate` = quando o sistema soube/deixou de considerar.
Identidade estável de dispositivo = `caminho` (ex.: `art5.p1.inc2`); cada alteração cria nova *redação*, não sobrescreve.

## Interface e histórico de conversas

A interface segue o protótipo visual (barra gov.br, cabeçalho institucional, menu lateral escuro, chat). O pilar COMPREENDER é o chat; CONHECER é a "Biblioteca Normativa"; PRODUZIR é "Minutas".
O **histórico de pesquisas é salvo no servidor, por usuário** (tabelas `conversa` e `conversa_mensagem`): abrir uma conversa antiga mostra a conversa **inteira**, como no ChatGPT, com o retrato do que foi exibido na época (fontes, versões e data de vigência). Cada pergunta é uma pesquisa independente, sem memória de contexto entre perguntas. As conversas são privadas (nem colegas do mesmo órgão as enxergam). Respostas antigas trazem aviso de que a norma pode ter mudado e o botão "Repetir com a vigência de hoje".
As respostas e "vigências" fixas do protótipo HTML eram dados de exemplo e **não** foram portadas: tudo vem da pesquisa real no acervo. O nome do produto, links e perguntas-exemplo ficam em `frontend/src/lib/marca.ts` (o protótipo usava "SIPEN"; o projeto, "SINPIN").

## Decisões de projeto

- **Relações só por texto expresso.** Nunca "norma nova revoga a antiga". Confiança ≥ 0,8 e destino único → confirmada automaticamente (reversível, auditada); o resto fica *pendente* e não altera vigência.
- **Efeito limitado pela audiência:** ato restrito de um órgão não altera a vigência de norma nacional para os demais (fica só como relação informativa).
- **Autenticação de desenvolvimento** por cabeçalho `X-Dev-User` (seletor no topo da interface). O login gov.br (Keycloak/OIDC) entra depois, trocando apenas `get_ctx()` em `backend/sinpin/api/deps.py`.

## O que NÃO foi verificado (leia antes de demonstrar)

O pacote foi desenvolvido em um ambiente sem rede, sem Docker e sem Postgres. Portanto:

- **Verificado por teste automático:** toda a lógica de domínio (parser, vigência bitemporal, grafo, isolamento entre órgãos, catálogo/proveniência, lote .zip, busca, minutas, verificação de citações) — em SQLite — e a tradução de SQL e das migrações para Postgres.
- **Verificado só por checagem estática:** o frontend (checagem de tipos TypeScript com stubs de react/next; `next build` **não** foi executado).
- **NÃO executado:** o driver PostgreSQL (psycopg), as migrações em Postgres real, o pgvector/HNSW e a busca híbrida, a camada FastAPI (`tests/test_api.py` precisa de FastAPI instalado), `docker compose build/up` e o `next build`. Há teste pronto para Postgres (`SINPIN_TEST_DATABASE_URL`) — rodá-lo é o primeiro passo recomendado; se algo falhar, o log do primeiro erro basta para corrigir.
- Os provedores `anthropic` e `openai_compat` e o provedor de embeddings foram escritos contra a API documentada, mas não foram exercitados contra serviços reais.

## Limitações conhecidas

- Autenticação gov.br/OIDC **não implementada**: qualquer pessoa com acesso à porta pode se passar por qualquer usuário. **Não exponha fora de localhost**.
- Parser: não trata itens numerados (1., 2.), anexos/tabelas, nem PDFs escaneados (sem OCR). A extração de HTML foi testada só com HTML sintético, **não** com páginas reais do Planalto/DOU: confira o resultado. "Revogam-se as disposições em contrário" é ignorada de propósito (não identifica ato).
- `SUSPENDE`/`RESTABELECE`/`REGULAMENTA`/`COMPLEMENTA`/`CONSOLIDA` são registradas no grafo, mas **não** alteram vigência automaticamente.
- A verificação de citações reduz, não elimina, alucinação; a revisão humana é obrigatória. A proteção contra prompt injection é em camadas (sinalização, fontes como dado, escape de tags, verificação) e não é infalível.
- Sem criptografia em repouso, sem controle de cota. Presença no acervo **não atesta vigência**: sem validação jurídica humana o sistema avisa.
- Não use documentos reais sigilosos ou dados pessoais em ambiente de desenvolvimento.

## Próximos passos sugeridos

1. Rodar a suíte contra Postgres e o `docker compose up`; corrigir o que aparecer.
2. gov.br via Keycloak/OIDC e perfis reais por órgão.
3. Cadastro **manual** de relações e de data de efeito; suspensão/restabelecimento no cálculo de vigência.
4. Ingestão de fontes oficiais (Planalto/DOU/LexML) com fonte oficial por dispositivo; OCR; reranking.
5. Modelos institucionais de documentos (cabeçalhos, numeração SEI) e fila de revisão/assinatura.
