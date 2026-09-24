"""camada comportamental: reservas, recorrencias e diagnosticos

Revision ID: b1a2c3d4e5f6
Revises: e7719734b1cb
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "b1a2c3d4e5f6"
down_revision = "e7719734b1cb"
branch_labels = None
depends_on = None

_MONEY = sa.Numeric(12, 2)


def upgrade() -> None:
    op.create_table(
        "reserva_sazonal",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("usuario_id", sa.Integer, nullable=False, index=True),
        sa.Column("descricao", sa.String(120), nullable=False),
        sa.Column("categoria", sa.String(60), nullable=True),
        sa.Column("custo_anual_estimado", _MONEY, nullable=False),
        sa.Column("saldo_acumulado", _MONEY, nullable=False, server_default="0"),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("criada_em", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "recorrencia",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("usuario_id", sa.Integer, nullable=False, index=True),
        sa.Column("descricao", sa.String(120), nullable=False),
        sa.Column("categoria", sa.String(60), nullable=True),
        sa.Column("valor_mensal", _MONEY, nullable=False),
        sa.Column("relevancia", sa.String(20), nullable=False, server_default="media"),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("atualizada_em", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "diagnostico",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("usuario_id", sa.Integer, nullable=False, index=True),
        sa.Column("periodo", sa.String(7), nullable=False),
        sa.Column("total_analisado", _MONEY, nullable=False, server_default="0"),
        sa.Column("qtd_lancamentos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("gerado_em", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("usuario_id", "periodo", name="uq_diagnostico_usuario_periodo"),
    )

    op.create_table(
        "diagnostico_padrao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "diagnostico_id",
            sa.Integer,
            sa.ForeignKey("diagnostico.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chave", sa.String(60), nullable=False),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("evidencia", sa.Text, nullable=False),
        sa.Column("vies", sa.String(200), nullable=False),
        sa.Column("confianca", sa.String(10), nullable=False),
        sa.Column("recomendacao", sa.Text, nullable=False),
        sa.Column("valor_envolvido", _MONEY, nullable=False, server_default="0"),
    )

    op.create_table(
        "diagnostico_ressalva",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "diagnostico_id",
            sa.Integer,
            sa.ForeignKey("diagnostico.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("texto", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("diagnostico_ressalva")
    op.drop_table("diagnostico_padrao")
    op.drop_table("diagnostico")
    op.drop_table("recorrencia")
    op.drop_table("reserva_sazonal")
