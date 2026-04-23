# wsgi.py
import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(__file__))

# Importa a aplicação (usa 'application' que é a variável exportada)
from app import application

print("=" * 50)
print("🚀 WSGI carregado com sucesso!")
print(f"📂 Diretório: {os.getcwd()}")
print("=" * 50)

if __name__ == "__main__":
    application.run()
