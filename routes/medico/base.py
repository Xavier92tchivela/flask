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
    
    # ========== FUNÇÃO EXECUTE QUERY ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Wrapper para a função do utils.database"""
        try:
            return db_execute_query(mysql, query, params, fetch, one)
        except Exception as e:
            logger.error(f"Erro ao executar query: {e}")
            return None
    
    # ========== DECORATOR ==========
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login para continuar.', 'warning')
                return redirect(url_for('auth.login'))
            
            if session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'warning')
                return redirect(url_for('auth.dashboard'))
            
            # Verificar se tem médico_id na sessão
            if not session.get('medico_id'):
                # Tentar buscar informações do médico
                try:
                    user_id = session.get('user_id')
                    if user_id:
                        medico = execute_query("""
                            SELECT id FROM medicos WHERE usuario_id = %s
                        """, (user_id,), fetch=True, one=True)
                        
                        if medico:
                            if isinstance(medico, dict):
                                session['medico_id'] = medico.get('id')
                            else:
                                session['medico_id'] = medico[0]
                except Exception as e:
                    logger.error(f"Erro ao buscar medico_id: {e}")
            
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== OBTER INFO MÉDICO ==========
    def obter_info_medico():
        """Obtém informações do médico logado"""
        try:
            user_id = session.get('user_id')
            if not user_id:
                logger.error("Nenhum user_id na sessão")
                return None
            
            # Buscar usuário - CORREÇÃO: tratar retorno
            usuario_result = execute_query("""
                SELECT tipo, nome, email, telefone FROM usuarios WHERE id = %s AND ativo = 1
            """, (user_id,), fetch=True, one=True)
            
            # Verificar se encontrou usuário
            if not usuario_result:
                logger.error(f"Usuário não encontrado: {user_id}")
                return None
            
            # Extrair dados do usuário (suporta dict ou tuple)
            if isinstance(usuario_result, dict):
                tipo = usuario_result.get('tipo')
                nome = usuario_result.get('nome')
                email = usuario_result.get('email')
                telefone = usuario_result.get('telefone')
            else:
                tipo = usuario_result[0] if len(usuario_result) > 0 else None
                nome = usuario_result[1] if len(usuario_result) > 1 else None
                email = usuario_result[2] if len(usuario_result) > 2 else None
                telefone = usuario_result[3] if len(usuario_result) > 3 else ''
            
            # Verificar se é médico
            if tipo != 'medico':
                logger.warning(f"Usuário {user_id} não é médico (tipo: {tipo})")
                return None
            
            # Buscar dados do médico
            medico_result = execute_query("""
                SELECT m.id, m.usuario_id, m.especialidade, m.crm, m.status
                FROM medicos m
                WHERE m.usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            # Converter bytes para string se necessário
            def decode_value(val):
                if val is None:
                    return ''
                if isinstance(val, bytes):
                    return val.decode('utf-8', errors='ignore')
                return str(val) if val else ''
            
            # Estruturar retorno
            if medico_result:
                if isinstance(medico_result, dict):
                    info = {
                        'id': medico_result.get('id'),
                        'usuario_id': medico_result.get('usuario_id'),
                        'especialidade': decode_value(medico_result.get('especialidade')) or "Clínico Geral",
                        'crm': decode_value(medico_result.get('crm')) or "CRM não informado",
                        'status': decode_value(medico_result.get('status')) or 'ativo',
                        'nome': decode_value(nome),
                        'email': decode_value(email),
                        'telefone': decode_value(telefone)
                    }
                else:
                    info = {
                        'id': medico_result[0] if len(medico_result) > 0 else None,
                        'usuario_id': medico_result[1] if len(medico_result) > 1 else user_id,
                        'especialidade': decode_value(medico_result[2]) if len(medico_result) > 2 else "Clínico Geral",
                        'crm': decode_value(medico_result[3]) if len(medico_result) > 3 else "CRM não informado",
                        'status': decode_value(medico_result[4]) if len(medico_result) > 4 else 'ativo',
                        'nome': decode_value(nome),
                        'email': decode_value(email),
                        'telefone': decode_value(telefone)
                    }
            else:
                # Médico não encontrado na tabela medicos - retorna apenas dados do usuário
                info = {
                    'id': None,
                    'usuario_id': user_id,
                    'especialidade': "Clínico Geral",
                    'crm': "CRM não informado",
                    'status': 'ativo',
                    'nome': decode_value(nome),
                    'email': decode_value(email),
                    'telefone': decode_value(telefone)
                }
            
            # Atualizar sessão
            if info.get('id'):
                session['medico_id'] = info['id']
            session['medico_especialidade'] = info['especialidade']
            session['medico_crm'] = info['crm']
            
            logger.info(f"Info médico obtida: {info['nome']} (ID: {info.get('id', 'N/A')})")
            return info
            
        except Exception as e:
            logger.error(f"Erro ao obter info médico: {e}")
            logger.error(traceback.format_exc())
            return None
    
    # ========== OBTER CONTADORES ==========
    def obter_contadores(medico_id):
        """Obtém contadores para o dashboard do médico"""
        try:
            hoje = datetime.now().date()
            
            # Consultas de hoje
            consultas_hoje = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            # Pacientes internados
            pacientes_internados = execute_query("""
                SELECT COUNT(*) FROM internacoes 
                WHERE medico_responsavel_id = %s AND status = 'ativa'
            """, (medico_id,), fetch=True, one=True)
            
            # Análises solicitadas
            analises_solicitadas = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            # Leitos ocupados
            leitos_ocupados = execute_query("""
                SELECT COUNT(*) FROM leitos WHERE status = 'ocupado'
            """, fetch=True, one=True)
            
            def get_count(result):
                if not result:
                    return 0
                if isinstance(result, dict):
                    return result.get('COUNT(*)', 0)
                return result[0] if result else 0
            
            return {
                'consultas_hoje': get_count(consultas_hoje),
                'pacientes_internados': get_count(pacientes_internados),
                'analises_solicitadas': get_count(analises_solicitadas),
                'leitos_ocupados': get_count(leitos_ocupados)
            }
        except Exception as e:
            logger.error(f"Erro ao obter contadores: {e}")
            return {
                'consultas_hoje': 0,
                'pacientes_internados': 0,
                'analises_solicitadas': 0,
                'leitos_ocupados': 0
            }
    
    return {
        'medico_required': medico_required,
        'obter_info_medico': obter_info_medico,
        'obter_contadores': obter_contadores,
        'execute_query': execute_query,
        'formatar_data': formatar_data,
        'calcular_idade': calcular_idade
    }
