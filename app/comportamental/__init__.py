"""Camada comportamental do Sistema de Controle Orçamentário.

Adiciona ao MVP uma leitura psicológica dos gastos (economia comportamental)
sobre os dados já importados: motor de diagnóstico, caixinhas de gastos
sazonais, raio-x de recorrências e o pague-se-primeiro dos 10%.
"""

from .router import router as comportamental_router

__all__ = ["comportamental_router"]
