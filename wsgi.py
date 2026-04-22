# wsgi.py
import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(__file__))

# Importa a aplicação - USE application em vez de app
from app import application

if __name__ == "__main__":
    application.run()
