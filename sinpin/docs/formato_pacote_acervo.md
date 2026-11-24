# Pacote de carga do acervo (para o agente/equipe de coleta)

Entrega: um `.zip` com `manifesto.json` na raiz + os arquivos originais capturados (PDF, HTML, DOCX ou TXT).
Importação: aba **CONHECER → Catálogo do acervo → Importar lote** (perfil curador) ou `POST /api/v1/catalogo/importar` (campo `pacote`).

```json
{
  "itens": [
    {
      "tipo": "RESOLUCAO",
      "orgao_emissor": "CONTRAN",
      "numero": "1032",
      "ano": 2026,
      "arquivo": "originais/resolucao_1032_2026.pdf",
      "url_documento": "URL EXATA do arquivo/texto individual do ato",
      "url_origem": "página oficial onde o documento foi localizado (índice)",
      "url_publicacao_dou": "edição do DOU em que o ato foi publicado",
      "data_assinatura": "AAAA-MM-DD",
      "data_publicacao": "AAAA-MM-DD",
      "capturado_em": "AAAA-MM-DDTHH:MM:SS",
      "status_validacao": "PENDENTE",
      "observacao": "texto livre",
      "relacoes_indice": [
        {"tipo": "REVOGA", "alvo_tipo": "RESOLUCAO", "numero": "941", "ano": 2022, "observacao": "opcional"}
      ]
    }
  ]
}
```

## Regras (o sistema aplica; violações voltam por item, sem derrubar o lote)
- **Obrigatórios:** `tipo`, `numero`, `ano`. `arquivo` é opcional: sem ele o item entra como **apenas referência do índice** (sem texto, sem efeito jurídico).
- **Três endereços distintos.** Não preencha os três com o mesmo valor. Endereço de **página geral** (os índices e portais cadastrados em *Fontes oficiais*, a home do DOU) é **recusado** como `url_documento` e como `url_publicacao_dou`. Se não souber, deixe em branco — nada será inventado nem copiado de outro campo.
- `tipo`: `LEI`, `LEI_COMPLEMENTAR`, `DECRETO`, `DECRETO_LEI`, `RESOLUCAO`, `PORTARIA`, `INSTRUCAO_NORMATIVA`, `DELIBERACAO`, `MEDIDA_PROVISORIA`, `NOTA_TECNICA`, `ORDEM_DE_SERVICO`, `OUTRO`.
- `status_validacao`: `PENDENTE` (padrão), `CONFIRMADO`, `CONTROVERTIDO`, `REJEITADO`. Quem importa normalmente deixa `PENDENTE`; a confirmação é humana, no documento.
- `relacoes_indice` são **hipóteses** do índice (`ALTERA`, `REVOGA`, `REVOGA_PARCIALMENTE`, `REGULAMENTA`, `COMPLEMENTA`, `CONSOLIDA`, `SUSPENDE`, `RESTABELECE`). Nunca alteram vigência. O sistema as confronta com o que o **texto** do ato declara e aponta divergências no relatório.
- **Hash SHA-256** e formato original são calculados pelo sistema sobre o arquivo enviado. Reenviar o mesmo arquivo não duplica; arquivo diferente para o mesmo ato vira **nova versão** (a versão anterior é preservada e a validação humana volta a *pendente*).
- Textos **HTML**: texto tachado (`<strike>`, `<s>`, `<del>`) é descartado (redação revogada em compilados) e o sistema avisa. Confira com o ato original.
- PDF escaneado não tem OCR: vem com aviso e sem texto útil.
- Limites: 2.000 arquivos, 60 MB por arquivo, 400 MB no total. O zip nunca é extraído em disco.
