// Identidade e textos configuráveis do produto (um único lugar para trocar nome, links e exemplos).
// O protótipo visual usava "SIPEN"; o projeto definido é "SINPIN". Para usar o outro nome, altere só `nome`/`extenso` aqui.
export const MARCA = {
  nome: "SINPIN",
  extenso: "Sistema Nacional de Pesquisa e Inteligência Normativa",
  lema: "Inteligência Normativa em Trânsito e Transporte",
  orgaoMinisterio: "Ministério dos Transportes",
  orgaoSecretaria: "Secretaria Nacional de Trânsito",
  orgaoSigla: "SENATRAN",
};

export const LINKS = {
  govbr: "https://www.gov.br",
  orgaosGoverno: "https://www.gov.br/pt-br/orgaos-do-governo",
  portariasSenatran:
    "https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/portarias-senatran",
};

/** Perguntas-exemplo (apenas atalhos para digitar; NÃO são respostas prontas — toda consulta passa pela pesquisa real). */
export const PERGUNTAS_EXEMPLO: { rotulo: string; pergunta: string }[] = [
  {
    rotulo: "Prazo de transferência de propriedade",
    pergunta:
      "Qual o prazo para o adquirente requerer a transferência de propriedade do veículo?",
  },
  {
    rotulo: "Descumprimento do prazo",
    pergunta:
      "O que acontece com o adquirente que descumpre o prazo de transferência?",
  },
  {
    rotulo: "Documentos do requerimento",
    pergunta: "Quais documentos instruem o requerimento de transferência?",
  },
  {
    rotulo: "Fraude documental",
    pergunta: "Como a SENATRAN trata indício de fraude documental?",
  },
];

/** Unidades geradoras oferecidas na exportação para o SEI! (ajuste à realidade do órgão). */
export const UNIDADES_SEI = [
  "MT/SENATRAN/CGREG",
  "MT/SENATRAN/CGIT",
  "MT/SENATRAN/CGSNT",
];
export const TIPOS_DOC_SEI = ["Despacho", "Nota Informativa", "Ofício"];
