# wsgi.py
import sys
import os
import traceback

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("🚀 Iniciando WSGI...")
print(f"📂 Diretório atual: {os.getcwd()}")
print(f"📁 Arquivos: {os.listdir('.')[:10]}")
print("=" * 60)

try:
    print("1. Importando app...")
    from app import application
    print("   ✅ App importado com sucesso!")
    print(f"   📌 Tipo: {type(application)}")
except Exception as e:
    print(f"   ❌ Erro ao importar app: {e}")
    traceback.print_exc()
    raise

print("=" * 60)
print("✅ WSGI carregado com sucesso!")
print("=" * 60)

if __name__ == "__main__":
    application.run()
