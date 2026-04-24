# routes/medico/base.py
from flask import session, flash, redirect, url_for
from datetime import datetime
import logging
import traceback
from functools import wraps
from utils.database import execute_query as db_execute_query
from utils.helpers import formatar_data, calcular_idade

logger = logging.getLogger(__name__)

def init_medico_base(mysql):
    """Inicializa funções base compartilhadas do médico"""
    
    # ========== FUNÇÃO PARA CONVERTER BYTES ==========
    def garantir_string(valor):
        """Converte bytes para string de forma segura"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        return str(valor)
    
    # ========== FUNÇÃO EXECUTE QUERY ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Wrapper para a função do utils.database"""
        try:
            return db_execute_query(mysql, query, params, fetch, one)
        except Exception as e:
            logger.error(f"Erro ao executar query: {e}")
            return None
    
    # ========== OBTER MÉDICO ID ==========
    def obter_medico_id():
        """Obtém o ID do médico da sessão ou do banco"""
        if 'medico_id' in session and session['medico_id']:
            return session['medico_id']
        if 'user_id' not in session:
            return None
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM medicos WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                medico_id = resultado[0] if isinstance(resultado, (list, tuple)) else resultado.get('id')
                session['medico_id'] = medico_id
                return medico_id
            return None
        except Exception as e:
            logger.error(f"Erro ao obter medico_id: {e}")
            return None
    
    # ========== DECORATOR ==========
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== OBTER INFO MÉDICO ==========
    def obter_info_medico():
        try:
            user_id = session.get('user_id')
            if not user_id:
                logger.error("Nenhum user_id na sessão")
                return None
            
            usuario = execute_query("""
                SELECT tipo, nome, email, telefone FROM usuarios WHERE id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not usuario or usuario[0] != 'medico':
                return None
            
            medico = execute_query("""
                SELECT m.id, m.usuario_id, m.especialidade, m.crm, m.status,
                       u.nome, u.email, u.telefone
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if medico:
                return {
                    'id': medico[0],
                    'usuario_id': medico[1],
                    'especialidade': garantir_string(medico[2]) if medico[2] else "Clínico Geral",
                    'crm': garantir_string(medico[3]) if medico[3] else "CRM não informado",
                    'status': garantir_string(medico[4]) if medico[4] else 'ativo',
                    'nome': garantir_string(medico[5]) if medico[5] else '',
                    'email': garantir_string(medico[6]) if medico[6] else '',
                    'telefone': garantir_string(medico[7]) if medico[7] else ''
                }
            
            return {
                'id': None,
                'usuario_id': user_id,
                'especialidade': "Clínico Geral",
                'crm': "CRM não informado",
                'status': 'ativo',
                'nome': garantir_string(usuario[1]) if usuario[1] else '',
                'email': garantir_string(usuario[2]) if usuario[2] else '',
                'telefone': garantir_string(usuario[3]) if usuario[3] else ''
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter info médico: {e}")
            logger.error(traceback.format_exc())
            return None
    
    # ========== VERIFICAR SE MÉDICO EXISTE NA TABELA MEDICOS ==========
    def verificar_criar_medico():
        """Verifica se o médico existe na tabela medicos, se não, cria"""
        try:
            user_id = session.get('user_id')
            if not user_id:
                return None
            
            # Verificar se já existe
            medico = execute_query("""
                SELECT id FROM medicos WHERE usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if medico:
                return medico[0]
            
            # Criar perfil de médico
            execute_query("""
                INSERT INTO medicos (usuario_id, especialidade, crm, status)
                VALUES (%s, %s, %s, %s)
            """, (user_id, 'Clínico Geral', 'CRM-AGUARDANDO', 'ativo'))
            
            # Buscar o ID criado
            medico = execute_query("""
                SELECT id FROM medicos WHERE usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if medico:
                session['medico_id'] = medico[0]
                return medico[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao verificar/criar médico: {e}")
            return None
    
    return {
        'medico_required': medico_required,
        'obter_info_medico': obter_info_medico,
        'obter_medico_id': obter_medico_id,
        'verificar_criar_medico': verificar_criar_medico,
        'execute_query': execute_query,
        'formatar_data': formatar_data,
        'calcular_idade': calcular_idade,
        'garantir_string': garantir_string
    }
