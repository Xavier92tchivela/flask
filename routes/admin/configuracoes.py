# routes/admin/configuracoes.py
from flask import render_template, request, redirect, url_for, flash, session
import logging
from datetime import datetime 
from functools import wraps

logger = logging.getLogger(__name__)

def init_configuracoes_routes(admin_bp, mysql):
    """Rotas para configurações do sistema"""
    
    # ---------- FUNÇÃO AUXILIAR DE QUERY ----------
    def execute_query(query, params=None, fetch=False, one=False):
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                if one and result:
                    result = result[0]
            else:
                mysql.connection.commit()
                result = None
            
            cur.close()
            return result
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            return None
    
    # ---------- DECORATOR DE AUTENTICAÇÃO ----------
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar o painel administrativo.', 'warning')
                return redirect(url_for('admin.login'))
            
            if session.get('user_type') != 'admin':
                flash('Acesso restrito a administradores.', 'danger')
                return redirect(url_for('admin.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    
    # ---------- PÁGINA DE CONFIGURAÇÕES ----------
    @admin_bp.route('/configuracoes', methods=['GET', 'POST'])
    @admin_required
    def configuracoes():
        """Configurações gerais do sistema"""
        
        # Buscar configurações atuais
        config = {}
        try:
            # Criar tabela se não existir
            execute_query("""
                CREATE TABLE IF NOT EXISTS configuracoes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    config_key VARCHAR(100) UNIQUE,
                    config_value TEXT,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            config_rows = execute_query("""
                SELECT config_key, config_value 
                FROM configuracoes
            """, fetch=True) or []
            
            for row in config_rows:
                config[row[0]] = row[1]
        except Exception as e:
            logger.error(f"Erro ao buscar configurações: {e}")
            # Valores padrão
            config = {
                'sistema_nome': 'DoctorIA',
                'sistema_descricao': 'Sistema de Diagnóstico por IA',
                'email_contato': 'contato@doctoria.com',
                'telefone_contato': '+244 999 999 999',
                'limite_consultas_dia': '50',
                'manutencao': '0'
            }
        
        if request.method == 'POST':
            # Salvar configurações
            sistema_nome = request.form.get('sistema_nome', 'DoctorIA')
            sistema_descricao = request.form.get('sistema_descricao', '')
            email_contato = request.form.get('email_contato', '')
            telefone_contato = request.form.get('telefone_contato', '')
            limite_consultas_dia = request.form.get('limite_consultas_dia', '50')
            manutencao = 1 if request.form.get('manutencao') else 0
            
            try:
                # Salvar cada configuração
                configuracoes = {
                    'sistema_nome': sistema_nome,
                    'sistema_descricao': sistema_descricao,
                    'email_contato': email_contato,
                    'telefone_contato': telefone_contato,
                    'limite_consultas_dia': limite_consultas_dia,
                    'manutencao': str(manutencao)
                }
                
                for key, value in configuracoes.items():
                    execute_query("""
                        INSERT INTO configuracoes (config_key, config_value) 
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE config_value = %s
                    """, (key, value, value))
                
                flash('Configurações salvas com sucesso!', 'success')
                logger.info("Configurações do sistema atualizadas")
                
            except Exception as e:
                logger.error(f"Erro ao salvar configurações: {e}")
                flash('Erro ao salvar configurações.', 'danger')
            
            return redirect(url_for('admin.configuracoes'))
        
        return render_template('admin/configuracoes.html', 
                             config=config, 
                             user=session,
                             now=datetime.now() )
                            
    