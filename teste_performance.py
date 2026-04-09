import MySQLdb
import json
import time
import random
import uuid
from datetime import datetime, timedelta

# Configurações MySQL
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "root"
MYSQL_DB = "sistema_medico"
MYSQL_PORT = 3306

def conectar_mysql():
    return MySQLdb.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        passwd=MYSQL_PASSWORD,
        db=MYSQL_DB,
        port=MYSQL_PORT,
        charset='utf8mb4'
    )

def get_ultimo_id_teste():
    """Obtém o último número usado nos emails de teste"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        # Busca o maior número nos emails de teste
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(email, '.teste', -1), '@', 1) AS UNSIGNED))
            FROM usuarios 
            WHERE email LIKE '%@email.com'
        """)
        
        resultado = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return resultado if resultado else 0
    except:
        return 0

def inserir_usuarios_sem_duplicatas(quantidade=5000):
    """Insere usuários garantindo emails únicos"""
    resultado = {"sucesso": False, "mensagem": "", "erros": [], "tempo_segundos": 0, "inseridos": 0}
    start_time = time.time()
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        # Descobre qual o próximo número disponível
        ultimo_id = get_ultimo_id_teste()
        print(f"📊 Último ID de teste encontrado: {ultimo_id}")
        
        # Se já existem muitos, sugere limpar
        if ultimo_id > 10000:
            print("\n⚠️  MUITOS REGISTROS DE TESTE ENCONTRADOS!")
            print(f"   Total: {ultimo_id} registros")
            resposta = input("   Deseja limpar todos antes de continuar? (s/N): ")
            if resposta.lower() == 's':
                limpar_usuarios_teste()
                ultimo_id = 0
        
        inicio = ultimo_id + 1
        fim = inicio + quantidade - 1
        
        print(f"\n🚀 Inserindo usuários de {inicio} até {fim}")
        
        # Listas para dados realistas
        primeiros_nomes = ['João', 'Maria', 'José', 'Ana', 'Carlos', 'Mariana', 'Pedro', 'Juliana']
        sobrenomes = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Pereira', 'Lima', 'Almeida']
        
        inseridos = 0
        batch_size = 100
        
        for i in range(inicio, fim + 1):
            try:
                # Gera UUID
                uuid_val = str(uuid.uuid4())
                
                # Gera nome
                nome_completo = f"{random.choice(primeiros_nomes)} {random.choice(sobrenomes)}"
                nome_bin = nome_completo.encode('utf-8')
                
                # Email ÚNICO usando o contador
                email = f"usuario.teste{i}@email.com"
                email_bin = email.encode('utf-8')
                
                # Tipo com distribuição
                tipo_rand = random.random()
                if tipo_rand < 0.7:
                    tipo = 'paciente'
                elif tipo_rand < 0.85:
                    tipo = 'medico'
                elif tipo_rand < 0.95:
                    tipo = 'enfermeiro'
                else:
                    tipo = random.choice(['admin', 'analista'])
                
                # SQL
                sql = """INSERT INTO usuarios (
                    uuid, nome, email, senha, telefone, endereco, 
                    tipo, ativo, criado_em, atualizado_em
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                
                valores = (
                    uuid_val, nome_bin, email_bin, '123456',
                    f"(11) 9{random.randint(10000000, 99999999)}",
                    f"Rua Teste, {random.randint(1,1000)}",
                    tipo, 1, datetime.now(), datetime.now()
                )
                
                cursor.execute(sql, valores)
                inseridos += 1
                
            except MySQLdb.IntegrityError as e:
                if "Duplicate entry" in str(e):
                    print(f"⚠️  Email duplicado detectado: {email} - pulando...")
                else:
                    resultado["erros"].append(str(e))
            
            if i % batch_size == 0:
                conn.commit()
                progresso = ((i - inicio + 1) / quantidade) * 100
                print(f"   Progresso: {i - inicio + 1}/{quantidade} ({progresso:.1f}%)")
        
        conn.commit()
        
        tempo_total = round(time.time() - start_time, 2)
        
        resultado["sucesso"] = True
        resultado["mensagem"] = f"{inseridos} usuários inseridos em {tempo_total} segundos"
        resultado["inseridos"] = inseridos
        resultado["tempo_segundos"] = tempo_total
        
        print(f"\n✅ Inserção concluída!")
        print(f"   📊 Inseridos: {inseridos}")
        print(f"   ⏱️  Tempo: {tempo_total}s")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        resultado["mensagem"] = f"Erro: {str(e)}"
        print(f"\n❌ Erro: {e}")
        
    return resultado

def limpar_usuarios_teste():
    """Remove usuários de teste"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE email LIKE '%@email.com'")
        total = cursor.fetchone()[0]
        
        if total == 0:
            print("✅ Nenhum usuário de teste encontrado!")
            return
        
        print(f"\n⚠️  Serão removidos {total} usuários de teste")
        confirm = input("Digite 'REMOVER' para confirmar: ")
        
        if confirm == "REMOVER":
            cursor.execute("DELETE FROM usuarios WHERE email LIKE '%@email.com'")
            conn.commit()
            print(f"✅ {cursor.rowcount} usuários removidos!")
        else:
            print("❌ Operação cancelada")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

def menu():
    print("\n" + "="*60)
    print(" 🧪 TESTE DE PERFORMANCE - VERSÃO SEM DUPLICATAS")
    print("="*60)
    
    print("\n1️⃣  - Inserir 5000 usuários (evitando duplicatas)")
    print("2️⃣  - Limpar usuários de teste")
    print("3️⃣  - Ver estatísticas")
    print("4️⃣  - Sair")
    
    opcao = input("\n👉 Escolha: ")
    
    if opcao == "1":
        res = inserir_usuarios_sem_duplicatas(5000)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif opcao == "2":
        limpar_usuarios_teste()
    elif opcao == "3":
        ultimo = get_ultimo_id_teste()
        print(f"\n📊 Estatísticas:")
        print(f"   Último ID de teste: {ultimo}")
    elif opcao == "4":
        return
    else:
        print("❌ Opção inválida")
    
    input("\nPressione Enter para continuar...")
    menu()

if __name__ == "__main__":
    menu()