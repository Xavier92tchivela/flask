# wsgi.py
import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(__file__))

# Importa a aplicação
from app import app

if __name__ == "__main__":
    app.run()
