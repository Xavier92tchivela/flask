from app import app, mysql
from werkzeug.security import generate_password_hash
import uuid

def init_db():
    with app.app_context():
        cur = mysql.connection.cursor()
        
        # Create tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            uuid CHAR(36) NOT NULL UNIQUE,
            nome VARCHAR(150) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            senha VARCHAR(255) NOT NULL,
            telefone VARCHAR(20),
            tipo ENUM('paciente', 'medico', 'admin') NOT NULL,
            ativo BOOLEAN DEFAULT TRUE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_tipo (tipo),
            INDEX idx_email (email)
        )
        """)
        
        # Create other tables similarly...
        
        # Insert sample admin user
        admin_uuid = str(uuid.uuid4())
        admin_password = generate_password_hash('admin123')
        
        try:
            cur.execute("""
            INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (admin_uuid, 'Administrador', 'admin@medical.com', admin_password, '(11) 99999-9999', 'admin'))
            
            mysql.connection.commit()
            print("Banco de dados inicializado com sucesso!")
            
        except Exception as e:
            print(f"Erro ao inicializar banco de dados: {e}")
            mysql.connection.rollback()
        
        finally:
            cur.close()

if __name__ == '__main__':
    init_db()