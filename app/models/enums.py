import enum


class Role(str, enum.Enum):
    admin = "admin"
    user = "user"


class CategoryKind(str, enum.Enum):
    """Natureza da categoria de gasto."""

    fixa = "fixa"
    variavel = "variavel"
    ambos = "ambos"


class PaymentMethod(str, enum.Enum):
    dinheiro = "dinheiro"
    debito = "debito"
    credito = "credito"
    pix = "pix"
    boleto = "boleto"
    outro = "outro"
