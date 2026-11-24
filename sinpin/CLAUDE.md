# Regras do projeto (para o assistente que evoluir este repositório)

1. **Stack definida — não trocar:** Next.js + TypeScript (frontend), Python + FastAPI (backend), PostgreSQL + pgvector, Docker. SQLite existe só para testes offline.
2. **Configuração sempre explicada:** o desenvolvedor original não conseguia executar o projeto no ambiente de desenvolvimento. Portanto, **toda mudança que exija configuração, instalação, variável de ambiente, migração, comando ou teste local deve vir com o passo explicado** (o que fazer, por quê, como conferir, o que fazer se falhar) e **registrado em `docs/PASSO_A_PASSO.md`**. Ao entregar, diga explicitamente o que **não** foi executado.
3. **Honestidade:** nunca inventar normas, URLs, relações ou "vigências conferidas". Dados de exemplo são sempre rotulados como sintéticos; respostas só com trechos do acervo, com citação, versão e data de vigência.
4. **Não mudar o que funciona** sem pedido; evoluir a partir do arquivo mais recente do usuário.
5. Identidade visual do protótipo (gov.br, SENATRAN) está em `frontend/src/app/globals.css`; textos/nome/links em `frontend/src/lib/marca.ts`.
