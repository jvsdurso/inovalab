# Passo a passo: configurar e rodar o projeto pela primeira vez

> **Regra do projeto:** nada aqui foi executado pelo desenvolvedor (o ambiente de desenvolvimento não tem Docker, Postgres nem rede).
> Por isso, **toda mudança que exija configuração vem acompanhada, neste arquivo, do passo explicado: o que fazer, por quê, como conferir que deu certo e o que fazer se falhar.**
> Siga na ordem. Se um passo falhar, **pare nele** e me envie a saída do comando indicado em "Se falhar".

---

## Passo 0 — O que precisa estar instalado

| Ferramenta | Para quê | Como conferir |
|---|---|---|
| **Docker Desktop** (Windows/macOS) ou Docker Engine + plugin Compose (Linux) | Sobe banco, backend e frontend com um comando | `docker --version` e `docker compose version` (Compose v2) |
| Navegador atual (Chrome/Edge) | Usar a interface | — |
| *(só se for rodar sem Docker)* Python 3.12 e Node 20 | Rodar backend/frontend direto na máquina | `python --version`, `node --version` |
| *(opcional)* **Ollama** | Busca vetorial e/ou IA local, sem enviar texto para fora | `ollama --version` |

**Windows:** o Docker Desktop precisa estar **aberto e com o motor iniciado** (ícone da baleia sem aviso) antes de qualquer comando `docker`.
**Se falhar:** `Cannot connect to the Docker daemon` = o Docker não está rodando; abra-o e espere iniciar.

## Passo 1 — Extrair o projeto

Extraia `sinpin.zip` numa pasta **sem espaços e sem acentos** no caminho (ex.: `C:\dev\sinpin` ou `~/sinpin`). Abra o terminal **dentro** dessa pasta (onde estão `docker-compose.yml`, `backend/` e `frontend/`).
**Conferir:** `ls` (ou `dir`) mostra `docker-compose.yml`, `.env.example`, `backend`, `frontend`.

## Passo 2 — Criar o arquivo de configuração `.env`

```bash
cp .env.example .env          # Windows (PowerShell): Copy-Item .env.example .env
```

O que cada linha faz (nenhuma é obrigatória para a primeira execução):

| Variável | O que faz | Valor para o primeiro teste |
|---|---|---|
| `POSTGRES_PASSWORD` | Senha do banco criado pelo compose. Só vale dentro da sua máquina, mas troque antes de qualquer uso compartilhado | deixe `sinpin` |
| `SINPIN_SEED_DEMO` | `1` carrega normas **sintéticas** de demonstração (não são normas reais); `0` começa vazio | `1` |
| `ANTHROPIC_API_KEY` etc. | Liga respostas geradas por IA. **Sem isso o sistema responde em "modo extrativo"** (mostra os trechos, sem redigir) | deixe comentado |
| `SINPIN_EMBEDDING_*` | Liga a busca por significado (pgvector). Sem isso a busca é só por palavras | deixe comentado |

**Se falhar:** o compose usa valores padrão quando não existe `.env`; então ele é opcional, mas o passo existe para você enxergar e controlar as opções.

## Passo 3 — Subir tudo

```bash
docker compose up --build
```

O que acontece (a **primeira vez demora vários minutos**: baixa imagens e instala pacotes):
1. `db` (PostgreSQL com pgvector) inicia e fica "healthy";
2. `backend` aplica as migrações (cria as tabelas e a extensão `vector`) e carrega a demonstração;
3. `frontend` compila o Next.js e inicia na porta 3000.

**Conferir (cada item):**
- Log do backend contém `Uvicorn running on http://0.0.0.0:8000`;
- <http://localhost:8000/api/v1/saude> responde JSON com `"status":"ok"`;
- <http://localhost:8000/docs> abre a documentação da API (OpenAPI);
- <http://localhost:3000> abre a interface.

**Se falhar** — rode e me envie a saída:
```bash
docker compose ps
docker compose logs --no-color --tail=120 db
docker compose logs --no-color --tail=120 backend
docker compose logs --no-color --tail=120 frontend
```
Falhas comuns:

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `port is already allocated` (5432, 8000 ou 3000) | Outro programa usa a porta (ex.: Postgres local na 5432) | Pare o outro programa **ou** mude o lado esquerdo da porta em `docker-compose.yml` (ex.: `"5433:5432"`) |
| backend reinicia sozinho; log com `extension "vector" is not available` | Imagem do banco sem pgvector | Confirme que `docker-compose.yml` usa `pgvector/pgvector:pg16` e rode `docker compose down -v && docker compose up --build` |
| backend: `password authentication failed` | Senha mudou depois de o volume do banco existir | `docker compose down -v` (apaga dados!) e suba de novo |
| frontend: erro de `npm`/rede no build | Sem acesso ao registro npm (rede corporativa/proxy) | Configure o proxy do Docker ou rode o frontend sem Docker (Passo 9) |
| tela abre mas "Falha ao carregar o usuário" | Frontend não alcança o backend | Confirme o backend no ar; o endereço do backend é fixado **na construção** do frontend (`BACKEND_URL`, padrão `http://backend:8000`): se mudar, reconstrua com `docker compose up --build` |

## Passo 4 — Primeiro uso (roteiro de 5 minutos)

1. Em <http://localhost:3000>, o menu lateral mostra **Usuário (desenvolvimento)**: escolha `SENATRAN · …servidor`.
2. **Nova Consulta:** clique num exemplo ("Prazo de transferência de propriedade") e em **Consultar**. Confira que a resposta traz citações `[1]`, `[2]`… e o cartão **Base legal aplicada**.
3. Mude **Vigência em** para `2019-01-01` e pergunte de novo: a resposta deve mudar (30 dias → 60 dias, conforme a demonstração).
4. **Histórico:** clique em **Nova Consulta**, faça outra pergunta; no menu, abra a conversa antiga — ela deve abrir **inteira**, sem misturar com a atual.
5. Troque o usuário para `DETRAN-XX`: o histórico do outro usuário **não** aparece (conversas são privadas).
6. **CONHECER** (Biblioteca Normativa): abra um documento, mude a data do texto compilado, veja o grafo e as relações pendentes.

## Passo 5 — (Opcional) Busca vetorial com Ollama

Por quê: encontra trechos pelo **significado**, não só por palavras iguais.
1. Instale o Ollama (<https://ollama.com>) e rode `ollama pull nomic-embed-text` (modelo de 768 dimensões, igual ao esquema do banco).
2. Confira: `ollama list` mostra `nomic-embed-text`.
3. No `.env`, descomente e ajuste:
   ```
   SINPIN_EMBEDDING_BASE_URL=http://host.docker.internal:11434/v1
   SINPIN_EMBEDDING_MODEL=nomic-embed-text
   SINPIN_EMBEDDING_DIM=768
   ```
   (`host.docker.internal` é como o contêiner enxerga o Ollama da sua máquina. No Linux o compose já mapeia isso.)
4. Reinicie: `docker compose up -d --force-recreate backend`. Na subida o sistema **indexa o que ainda não tem vetor**, em segundo plano.
5. **Conferir:** no menu lateral aparece "busca vetorial ativa". Para outro modelo/dimensão, a coluna do banco (`vector(768)`) precisa ser ajustada **antes** do primeiro uso — me avise.

**Privacidade:** com provedor **remoto**, o texto de documentos restritos sai da infraestrutura do órgão. Para acervo restrito, use provedor local/institucional.
**Se falhar:** `docker compose logs --tail=80 backend` e procure `embedding`. Erro de conexão = Ollama fechado ou URL errada; o sistema continua funcionando só com busca lexical.

## Passo 6 — (Opcional) IA generativa

Sem chave, o sistema funciona em **modo extrativo** (não inventa texto). Para respostas redigidas:
- **Anthropic:** `ANTHROPIC_API_KEY=sk-ant-…` no `.env` → `docker compose up -d --force-recreate backend`. O texto da pergunta e dos trechos recuperados **sai para o provedor**: não use com documentos sigilosos sem decisão institucional.
- **Local (Ollama/vLLM):** `SINPIN_LLM_PROVIDER=openai_compat`, `SINPIN_OPENAI_BASE_URL=http://host.docker.internal:11434/v1`, `SINPIN_LLM_MODEL=<modelo baixado>`.
- **Conferir:** o menu lateral mostra `IA: <provedor> (<modelo>)`. Faça uma pergunta e verifique se aparecem avisos vermelhos de "citações inexistentes" — se aparecerem, **não use** a resposta.
- Os provedores foram escritos contra a documentação das APIs e **nunca foram chamados de verdade**: este é o primeiro teste real. Se der erro, envie `docker compose logs --tail=80 backend`.

## Passo 7 — Rodar os testes automáticos

**Domínio (sem Postgres, usa SQLite):**
```bash
cd backend
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```
Esperado: tudo verde (1 teste pulado = o de Postgres). `tests/test_api.py` só roda com `fastapi`/`uvicorn` instalados (já vêm no `requirements.txt`).

**A mesma suíte em PostgreSQL + pgvector** (valida o driver, as migrações e a busca híbrida — **o teste mais importante para nós, pois eu não consegui rodá-lo**):
```bash
docker compose up -d db
docker compose exec db psql -U sinpin -d postgres -c "CREATE DATABASE sinpin_teste;"
cd backend
SINPIN_TEST_DATABASE_URL=postgresql://sinpin:sinpin@localhost:5432/sinpin_teste python -m pytest -q     # PowerShell: $env:SINPIN_TEST_DATABASE_URL="..."; python -m pytest -q
```
⚠ A suíte **apaga todas as tabelas** do banco apontado: use sempre o `sinpin_teste`, nunca o `sinpin`.
**Se falhar:** me envie o trecho do **primeiro** erro (`pytest -x -q 2>&1 | head -60`).

## Passo 8 — Conferir o frontend isoladamente

```bash
cd frontend
npm install
npm run typecheck      # tipos TypeScript
npm run build          # compilação de produção do Next.js
```
**Se falhar:** me envie a saída completa do comando que falhou.

## Passo 9 — Rodar sem Docker (alternativa)

1. Banco: `docker run -d --name sinpin-db -p 5432:5432 -e POSTGRES_USER=sinpin -e POSTGRES_PASSWORD=sinpin -e POSTGRES_DB=sinpin pgvector/pgvector:pg16`
2. Backend: `cd backend && pip install -r requirements.txt && SINPIN_SEED_DEMO=1 python -m sinpin --port 8000`
3. Frontend: `cd frontend && npm install && npm run dev` → <http://localhost:3000> (o proxy `/api` aponta para `http://localhost:8000`; mude com a variável `BACKEND_URL`).

## Passo 10 — Parar, reiniciar e começar do zero

- Parar mantendo os dados: `docker compose down`
- Subir de novo: `docker compose up`
- **Apagar tudo** (banco e arquivos): `docker compose down -v` ⚠ irreversível.

## Passo 11 — Antes de usar com dados reais (checklist)

- [ ] `SINPIN_SEED_DEMO=0` (sem normas sintéticas) e banco novo (`down -v`).
- [ ] Senha do banco trocada e porta 5432 não exposta (remova o mapeamento `ports` do serviço `db`).
- [ ] **Login gov.br ainda não existe**: o modo `dev` aceita qualquer identidade. **Não exponha as portas 3000/8000 fora da sua máquina.**
- [ ] Decisão sobre enviar texto a provedores externos de IA/embeddings.
- [ ] Brasão e logos substituídos pelos arquivos oficiais (os do protótipo são desenhos aproximados).
- [ ] Rotina de cópia de segurança do volume `pgdata` e da pasta de arquivos.
- [ ] Fontes do cabeçalho: a interface carrega as fontes Inter/Plus Jakarta Sans do Google Fonts no **navegador**. Em rede sem internet elas caem para fontes do sistema (sem erro); se a política do órgão proibir essa chamada externa, me avise para hospedá-las localmente.
