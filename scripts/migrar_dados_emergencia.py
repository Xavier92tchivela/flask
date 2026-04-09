# scripts/migrar_dados_emergencia.py
import mysql.connector
import os
import sys

# Adicionar caminho do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.security import security
    print("✅ Módulo de segurança carregado")
except ImportError as e:
    print(f"❌ Erro ao carregar security: {e}")
    sys.exit(1)

def migrar_receitas():
    """Migra receitas existentes para formato criptografado"""
    
    print("\n" + "="*60)
    print("🔐 MIGRAÇÃO DE EMERGÊNCIA - RECEITAS")
    print("="*60)
    
    # Conectar ao banco
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",  # Coloque sua senha
            database="sistema_medico"
        )
        cursor = conn.cursor()
        print("✅ Conectado ao banco sistema_medico")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    # Verificar dados atuais
    cursor.execute("""
        SELECT id, consulta_id, diagnostico, prescricao, recomendacoes 
        FROM receita
    """)
    
    receitas = cursor.fetchall()
    print(f"\n📊 Total de receitas: {len(receitas)}")
    
    # Mostrar amostra dos dados
    print("\n📝 Amostra dos dados ATUAIS:")
    for rec in receitas[:3]:
        print(f"  ID {rec[0]}: Diagnostico tipo: {type(rec[2])}")
        print(f"     Valor: {str(rec[2])[:100]}...")
    
    # Perguntar se quer migrar
    resposta = input("\n⚠️  Deseja migrar todas as receitas? (s/N): ")
    if resposta.lower() != 's':
        print("Operação cancelada.")
        return
    
    # Migrar cada receita
    migradas = 0
    erros = 0
    
    for rec in receitas:
        rec_id, consulta_id, diag, presc, recs = rec
        
        try:
            # Verificar se já está criptografado
            if diag and isinstance(diag, str) and not diag.startswith(b'gAAAAA'):
                diag_enc = security.encrypt(diag)
            else:
                diag_enc = diag
            
            if presc and isinstance(presc, str) and not presc.startswith(b'gAAAAA'):
                presc_enc = security.encrypt(presc)
            else:
                presc_enc = presc
            
            if recs and isinstance(recs, str) and not recs.startswith(b'gAAAAA'):
                recs_enc = security.encrypt(recs)
            else:
                recs_enc = recs
            
            # Atualizar
            cursor.execute("""
                UPDATE receita 
                SET diagnostico = %s,
                    prescricao = %s,
                    recomendacoes = %s
                WHERE id = %s
            """, (diag_enc, presc_enc, recs_enc, rec_id))
            
            migradas += 1
            if migradas % 10 == 0:
                print(f"  Progresso: {migradas}/{len(receitas)}")
                
        except Exception as e:
            print(f"  ❌ Erro na receita {rec_id}: {e}")
            erros += 1
    
    conn.commit()
    
    print(f"\n✅ {migradas} receitas migradas com sucesso!")
    if erros > 0:
        print(f"⚠️  {erros} receitas com erro")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    migrar_receitas()