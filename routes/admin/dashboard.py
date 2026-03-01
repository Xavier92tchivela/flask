# routes/admin/dashboard.py
from flask import render_template, session, jsonify, flash, redirect, url_for
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

def init_dashboard_routes(admin_bp, mysql):
    """Rotas do dashboard principal"""
    
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
            logger.error(traceback.format_exc())
            return None
    
    # ---------- DECORATOR DE AUTENTICAÇÃO ----------
    def admin_required(f):
        from functools import wraps
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
    
    # ---------- ROTA PRINCIPAL ----------
    @admin_bp.route('/')
    @admin_required
    def index():
        """Redireciona para o dashboard"""
        return redirect(url_for('admin.dashboard'))
    
    # ---------- ROTA DO DASHBOARD ----------
    @admin_bp.route('/dashboard')
    @admin_required
    def dashboard():
        """Dashboard principal com estatísticas"""
        try:
            logger.info("=" * 50)
            logger.info("CARREGANDO DASHBOARD ADMIN")
            logger.info("=" * 50)
            
            # Valores padrão para todas as variáveis
            total_medicos = 0
            total_analistas = 0
            total_pacientes = 0
            total_consultas = 0
            consultas_status = []
            ultimos_usuarios = []
            atividades_recentes = []
            
            # Dicionário de estatísticas para o template
            estatisticas = {
                'pendentes': 0,
                'em_analise': 0,
                'concluidos': 0,
                'urgentes': 0
            }
            
            # ========== VERIFICAR ESTRUTURA DO BANCO ==========
            # Primeiro, verificar se as tabelas existem
            tabelas = execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """, fetch=True) or []
            
            tabelas_existentes = [t[0] for t in tabelas if t[0]]
            logger.info(f"Tabelas existentes: {tabelas_existentes}")
            
            # ========== ESTATÍSTICAS GERAIS ==========
            
            # MÉDICOS
            if 'medicos' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM medicos", fetch=True, one=True)
                    total_medicos = result[0] if result and result[0] else 0
                    logger.info(f"Médicos: {total_medicos}")
                except Exception as e:
                    logger.error(f"Erro ao contar médicos: {e}")
            
            # ANALISTAS
            if 'analistas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM analistas", fetch=True, one=True)
                    total_analistas = result[0] if result and result[0] else 0
                    logger.info(f"Analistas: {total_analistas}")
                except Exception as e:
                    logger.error(f"Erro ao contar analistas: {e}")
            
            # PACIENTES
            if 'pacientes' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM pacientes", fetch=True, one=True)
                    total_pacientes = result[0] if result and result[0] else 0
                    logger.info(f"Pacientes: {total_pacientes}")
                except Exception as e:
                    logger.error(f"Erro ao contar pacientes: {e}")
            
            # CONSULTAS
            if 'consultas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM consultas", fetch=True, one=True)
                    total_consultas = result[0] if result and result[0] else 0
                    logger.info(f"Consultas: {total_consultas}")
                except Exception as e:
                    logger.error(f"Erro ao contar consultas: {e}")
            
            # ========== ESTATÍSTICAS POR STATUS ==========
            if 'consultas' in tabelas_existentes:
                try:
                    # Pendentes
                    result = execute_query("SELECT COUNT(*) FROM consultas WHERE status = 'pendente'", fetch=True, one=True)
                    estatisticas['pendentes'] = result[0] if result and result[0] else 0
                    
                    # Em análise
                    result = execute_query("SELECT COUNT(*) FROM consultas WHERE status = 'em_analise'", fetch=True, one=True)
                    estatisticas['em_analise'] = result[0] if result and result[0] else 0
                    
                    # Concluídos
                    result = execute_query("SELECT COUNT(*) FROM consultas WHERE status = 'concluido'", fetch=True, one=True)
                    estatisticas['concluidos'] = result[0] if result and result[0] else 0
                    
                    logger.info(f"Estatísticas por status: {estatisticas}")
                except Exception as e:
                    logger.error(f"Erro ao buscar estatísticas por status: {e}")
            
            # URGENTES (se houver campo urgencia)
            if 'consultas' in tabelas_existentes:
                try:
                    # Verificar se coluna urgencia existe
                    colunas = execute_query("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_NAME = 'consultas' 
                        AND COLUMN_NAME = 'urgencia'
                    """, fetch=True)
                    
                    if colunas and len(colunas) > 0:
                        result = execute_query("SELECT COUNT(*) FROM consultas WHERE urgencia = 'urgente'", fetch=True, one=True)
                        estatisticas['urgentes'] = result[0] if result and result[0] else 0
                    else:
                        estatisticas['urgentes'] = 0
                        logger.info("Coluna 'urgencia' não existe na tabela consultas")
                except Exception as e:
                    logger.error(f"Erro ao buscar consultas urgentes: {e}")
            
            # ========== CONSULTAS POR STATUS (AGRUPADO) ==========
            if 'consultas' in tabelas_existentes:
                try:
                    consultas_status = execute_query("""
                        SELECT COALESCE(status, 'desconhecido') as status, COUNT(*) as total 
                        FROM consultas 
                        GROUP BY status
                    """, fetch=True) or []
                    logger.info(f"Consultas por status: {len(consultas_status)} registros")
                except Exception as e:
                    logger.error(f"Erro ao buscar consultas por status: {e}")
            
            # ========== ÚLTIMOS USUÁRIOS ==========
            if 'usuarios' in tabelas_existentes:
                try:
                    ultimos_usuarios = execute_query("""
                        SELECT 
                            COALESCE(u.id, 0) as id, 
                            COALESCE(u.nome, 'N/A') as nome, 
                            COALESCE(u.email, 'N/A') as email, 
                            COALESCE(u.tipo, 'N/A') as tipo, 
                            COALESCE(u.ativo, 0) as ativo,
                            u.criado_em
                        FROM usuarios u
                        WHERE u.criado_em IS NOT NULL
                        ORDER BY u.criado_em DESC
                        LIMIT 10
                    """, fetch=True) or []
                    logger.info(f"Últimos usuários: {len(ultimos_usuarios)} registros")
                except Exception as e:
                    logger.error(f"Erro ao buscar últimos usuários: {e}")
                    # Fallback - query mais simples
                    try:
                        ultimos_usuarios = execute_query("""
                            SELECT id, nome, email, tipo, ativo, criado_em
                            FROM usuarios
                            ORDER BY criado_em DESC
                            LIMIT 5
                        """, fetch=True) or []
                    except:
                        ultimos_usuarios = []
            
            # ========== ATIVIDADES RECENTES ==========
            if all(tabela in tabelas_existentes for tabela in ['consultas', 'pacientes', 'medicos', 'usuarios']):
                try:
                    # Versão corrigida da query
                    atividades_recentes = execute_query("""
                        SELECT 
                            c.id,
                            CONCAT(
                                COALESCE(p_u.nome, 'Paciente'), 
                                ' - Dr. ', 
                                COALESCE(m_u.nome, 'Médico')
                            ) as descricao,
                            COALESCE(c.status, 'desconhecido') as status,
                            c.data_hora
                        FROM consultas c
                        LEFT JOIN pacientes p ON c.paciente_id = p.id
                        LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                        LEFT JOIN medicos m ON c.medico_id = m.id
                        LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                        WHERE c.data_hora IS NOT NULL
                        ORDER BY c.data_hora DESC
                        LIMIT 5
                    """, fetch=True) or []
                    logger.info(f"Atividades recentes: {len(atividades_recentes)} registros")
                except Exception as e:
                    logger.error(f"Erro ao buscar atividades recentes: {e}")
                    logger.error(traceback.format_exc())
                    
                    # Query mais simples como fallback
                    try:
                        atividades_recentes = execute_query("""
                            SELECT 
                                c.id,
                                'Consulta' as descricao,
                                c.status,
                                c.data_hora
                            FROM consultas c
                            WHERE c.data_hora IS NOT NULL
                            ORDER BY c.data_hora DESC
                            LIMIT 5
                        """, fetch=True) or []
                    except:
                        atividades_recentes = []
            
            # Log final
            logger.info("=" * 50)
            logger.info("DASHBOARD CARREGADO COM SUCESSO")
            logger.info(f"Médicos: {total_medicos}")
            logger.info(f"Analistas: {total_analistas}")
            logger.info(f"Pacientes: {total_pacientes}")
            logger.info(f"Consultas: {total_consultas}")
            logger.info("=" * 50)
            
            # Renderizar template com todas as variáveis
            return render_template('admin/dashboard.html',
                                 estatisticas=estatisticas,
                                 total_medicos=total_medicos,
                                 total_analistas=total_analistas,
                                 total_pacientes=total_pacientes,
                                 total_consultas=total_consultas,
                                 consultas_status=consultas_status,
                                 ultimos_usuarios=ultimos_usuarios,
                                 atividades_recentes=atividades_recentes,
                                 now=datetime.now(),
                                 user=session)
            
        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar dashboard. Verifique os logs.', 'danger')
            
            # Valores padrão em caso de erro
            return render_template('admin/dashboard.html',
                                 user=session,
                                 estatisticas={'pendentes':0, 'em_analise':0, 'concluidos':0, 'urgentes':0},
                                 total_medicos=0,
                                 total_analistas=0,
                                 total_pacientes=0,
                                 total_consultas=0,
                                 consultas_status=[],
                                 ultimos_usuarios=[],
                                 atividades_recentes=[],
                                 now=datetime.now())
    
    # ---------- API DO DASHBOARD ----------
    @admin_bp.route('/api/dashboard-stats')
    @admin_required
    def api_dashboard_stats():
        """API para estatísticas do dashboard (atualização em tempo real)"""
        try:
            stats = {
                'medicos': 0,
                'analistas': 0,
                'pacientes': 0,
                'consultas': 0,
                'consultas_hoje': 0
            }
            
            # Verificar tabelas
            tabelas = execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """, fetch=True) or []
            
            tabelas_existentes = [t[0] for t in tabelas if t[0]]
            
            # Médicos
            if 'medicos' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM medicos", fetch=True, one=True)
                    stats['medicos'] = result[0] if result and result[0] else 0
                except:
                    pass
            
            # Analistas
            if 'analistas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM analistas", fetch=True, one=True)
                    stats['analistas'] = result[0] if result and result[0] else 0
                except:
                    pass
            
            # Pacientes
            if 'pacientes' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM pacientes", fetch=True, one=True)
                    stats['pacientes'] = result[0] if result and result[0] else 0
                except:
                    pass
            
            # Consultas
            if 'consultas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM consultas", fetch=True, one=True)
                    stats['consultas'] = result[0] if result and result[0] else 0
                except:
                    pass
                
                # Consultas de hoje
                try:
                    result = execute_query("""
                        SELECT COUNT(*) 
                        FROM consultas 
                        WHERE DATE(data_hora) = CURDATE()
                    """, fetch=True, one=True)
                    stats['consultas_hoje'] = result[0] if result and result[0] else 0
                except:
                    pass
            
            return jsonify({'success': True, 'data': stats})
            
        except Exception as e:
            logger.error(f"Erro na API de stats: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500