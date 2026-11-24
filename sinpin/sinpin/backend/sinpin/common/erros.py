from __future__ import annotations


class ErroNegocio(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, detalhes=None):
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes

    def como_dict(self) -> dict:
        d = {"erro": {"codigo": self.codigo, "mensagem": self.mensagem}}
        if self.detalhes is not None:
            d["erro"]["detalhes"] = self.detalhes
        return d


def nao_encontrado(o_que: str = "Recurso") -> ErroNegocio:
    # 404 também para recursos de outra instituição: não vazar existência.
    return ErroNegocio(404, "nao_encontrado", f"{o_que} não encontrado.")


def proibido(msg: str = "Operação não permitida para o seu perfil.") -> ErroNegocio:
    return ErroNegocio(403, "proibido", msg)


def invalido(msg: str, detalhes=None) -> ErroNegocio:
    return ErroNegocio(422, "invalido", msg, detalhes)
