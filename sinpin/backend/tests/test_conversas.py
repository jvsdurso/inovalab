import pytest
from conftest import ctx_de

from sinpin.common.erros import ErroNegocio
from sinpin.conversas import service as conv
from sinpin.ia import orquestrador
from sinpin.pesquisa import service as pesquisa


def _resp(c, ctx, pergunta, data="2024-06-01"):
    busca = pesquisa.buscar(c.db, ctx, pergunta, data)
    r = orquestrador.responder(c.db, c.llm, ctx, pergunta, data, busca)
    return {"pergunta": pergunta, "data": data, **r, "fontes": busca["fontes"], "alertas": busca["alertas"]}


def test_conversa_reabre_completa_na_ordem(c):
    ctx = ctx_de(c, "senatran.servidor")
    q1, q2 = "prazo para transferência de propriedade", "documentos do requerimento de transferência"
    cid = conv.registrar_troca(c.db, ctx, None, q1, "2024-06-01", _resp(c, ctx, q1))
    assert conv.registrar_troca(c.db, ctx, cid, q2, "2024-06-01", _resp(c, ctx, q2)) == cid
    cv = conv.obter(c.db, ctx, cid)
    assert [m["papel"] for m in cv["mensagens"]] == ["usuario", "assistente", "usuario", "assistente"]
    assert [m["ordem"] for m in cv["mensagens"]] == [1, 2, 3, 4]
    assert cv["mensagens"][0]["conteudo"]["texto"] == q1
    assert cv["mensagens"][1]["conteudo"]["fontes"], "o snapshot deve trazer as fontes da época"
    assert cv["titulo"].startswith("prazo para transferência")


def test_nova_conversa_nao_mistura_com_a_antiga(c):
    ctx = ctx_de(c, "senatran.servidor")
    a = conv.registrar_troca(c.db, ctx, None, "pergunta A", "2024-06-01", {"resposta": "ra", "fontes": []})
    b = conv.registrar_troca(c.db, ctx, None, "pergunta B", "2024-06-01", {"resposta": "rb", "fontes": []})
    assert a != b
    assert len(conv.obter(c.db, ctx, a)["mensagens"]) == 2 and len(conv.obter(c.db, ctx, b)["mensagens"]) == 2
    lista = conv.listar(c.db, ctx)
    assert [x["titulo"] for x in lista] == ["pergunta B", "pergunta A"]  # mais recente primeiro
    conv.registrar_troca(c.db, ctx, a, "outra em A", "2024-06-01", {"resposta": "x", "fontes": []})
    assert conv.listar(c.db, ctx)[0]["id"] == a and conv.listar(c.db, ctx)[0]["n_perguntas"] == 2  # A sobe ao topo


def test_conversa_e_privada_ao_usuario(c):
    dono = ctx_de(c, "senatran.servidor")
    outro_orgao = ctx_de(c, "detran.servidor")
    cid = conv.registrar_troca(c.db, dono, None, "caso sigiloso", "2024-06-01", {"resposta": "r", "fontes": []})
    assert conv.listar(c.db, outro_orgao) == []
    for f in (lambda: conv.obter(c.db, outro_orgao, cid), lambda: conv.excluir(c.db, outro_orgao, cid),
              lambda: conv.renomear(c.db, outro_orgao, cid, "x"),
              lambda: conv.registrar_troca(c.db, outro_orgao, cid, "intrusão", "2024-06-01", {})):
        with pytest.raises(ErroNegocio) as e:
            f()
        assert e.value.status == 404
    assert len(conv.obter(c.db, dono, cid)["mensagens"]) == 2  # nada foi anexado pelo intruso


def test_renomear_e_excluir(c):
    ctx = ctx_de(c, "senatran.servidor")
    cid = conv.registrar_troca(c.db, ctx, None, "x" * 200, "2024-06-01", {"resposta": "r", "fontes": []})
    assert len(conv.listar(c.db, ctx)[0]["titulo"]) <= 80
    assert conv.renomear(c.db, ctx, cid, "  Prazo   de transferência ")["titulo"] == "Prazo de transferência"
    conv.excluir(c.db, ctx, cid)
    assert conv.listar(c.db, ctx) == []
    with pytest.raises(ErroNegocio):
        conv.obter(c.db, ctx, cid)
