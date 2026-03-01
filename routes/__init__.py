# routes/__init__.py
"""
Pacote de rotas do sistema DOCTORIA

Este pacote contém todos os blueprints da aplicação organizados por funcionalidade:

Estrutura:
    routes/
    ├── __init__.py          # Este arquivo - inicializador do pacote
    ├── auth.py               # Rotas de autenticação (login, registro, logout)
    ├── base.py               # Funções base compartilhadas (NÃO USAR - está em medico/base.py)
    ├── consulta.py           # Blueprint de consultas (pode ser removido se não usado)
    ├── medico/               # Blueprint do médico (subpacote)
    │   ├── __init__.py       # Inicializador do módulo médico
    │   ├── base.py           # Funções base específicas do médico
    │   ├── consultas.py      # Rotas de consultas do médico
    │   ├── dashboard.py      # Dashboard do médico
    │   ├── pedidos.py        # Pedidos de análise do médico
    │   ├── perfil.py         # Perfil do médico
    │   ├── pacientes.py      # Gerenciamento de pacientes
    │   ├── api.py            # APIs do médico
    │   ├── debug.py          # Rotas de debug
    │   ├── receitas.py       # Gerenciamento de receitas
    │   └── consulta/         # Submódulo de consultas (detalhado)
    │       ├── __init__.py   # Blueprint de consultas detalhadas
    │       ├── medico_routes.py
    │       ├── detalhes.py
    │       ├── acoes.py
    │       ├── agendamento.py
    │       ├── editar.py
    │       └── api.py
    ├── paciente/             # Blueprint do paciente
    │   └── __init__.py
    ├── analista/             # Blueprint do analista
    │   └── __init__.py
    ├── analista_fallback.py  # Fallback para analista (se necessário)
    ├── pedido_analise.py     # Blueprint de pedidos de análise
    └── pedido_analise_fallback.py # Fallback para pedidos (se necessário)
"""

import logging

# Configurar logger para o pacote
logger = logging.getLogger(__name__)

# Versão do pacote de rotas
__version__ = '1.0.0'

# Lista de blueprints disponíveis (para referência)
AVAILABLE_BLUEPRINTS = [
    'auth',
    'medico',
    'paciente',
    'analista',
    'consulta',
    'pedido_analise'
]

# Função auxiliar para listar todos os blueprints registrados
def list_blueprints():
    """Retorna lista de todos os blueprints disponíveis no sistema"""
    return AVAILABLE_BLUEPRINTS

# Exportar apenas o necessário
__all__ = ['list_blueprints', 'AVAILABLE_BLUEPRINTS']

# NOTA: Não importe nada aqui para evitar importações circulares!
# As importações devem ser feitas diretamente nos arquivos que precisam delas.