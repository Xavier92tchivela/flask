from flask import Blueprint

# Criar o blueprint do farmacêutico
farmaceutico_bp = Blueprint('farmaceutico', __name__, url_prefix='/farmaceutico')

# Importar os módulos
from . import dashboard
from . import prescricoes
from . import dispensacoes
from . import estoque
from . import produtos
from . import fornecedores
from . import relatorios