# routes/admin/dashboard.py - VERSÃO CORRIGIDA
from flask import render_template, session, jsonify, flash, redirect, url_for
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

def init_dashboard_routes(admin_bp, mysql):
    """Rotas do dashboard principal"""
    
    # ===== FUNÇÃO AUXILIAR PARA EXTRAIR VALOR =====
    def extrair_valor(resultado, indice=0, chave=None, padrao=None):
        """Extrai valor de forma segura de dict ou tuple/list"""
        if resultado is None:
            return padrao
        
        if isinstance(resultado, dict):
            if chave:
                return resultado.get(chave, padrao)
            # Se não tem chave, pega o primeiro valor
            valores = list(resultado.values())
            return valores[0] if valores else padrao
        
        if isinstance(resultado, (tuple, list)):
            if len(resultado) > indice:
                return resultado[indice]
            return padrao
        
        return resultado if resultado is not None else padrao
    
    # ===== FUNÇÃO PARA EXTRAIR LISTA DE VALORES =====
    def extrair_lista_valores(resultados, indice=0, chave=None):
        """Extrai uma lista de valores de uma lista de resultados"""
        if not resultados:
            return []
        
        lista = []
        for item in resultados:
            valor = extrair_valor(item, indice, chave)
            if valor is not None:
                lista.append(valor)
        return lista
    
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
            
            # CORREÇÃO: Extrair nomes das tabelas de forma segura
            if tabelas:
                # Verificar se o primeiro resultado é dicionário ou tupla
                first_item = tabelas[0]
                if isinstance(first_item, dict):
                    tabelas_existentes = [t.get('table_name') for t in tabelas if t.get('table_name')]
                else:
                    # É tupla/lista
                    tabelas_existentes = [t[0] for t in tabelas if t and len(t) > 0]
            else:
                tabelas_existentes = []
            
            logger.info(f"Tabelas existentes: {tabelas_existentes}")
            
            # ========== ESTATÍSTICAS GERAIS ==========
            
            # MÉDICOS
            if 'medicos' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM medicos", fetch=True, one=True)
                    if isinstance(result, dict):
                        total_medicos = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        total_medicos = result[0] if result else 0
                    logger.info(f"Médicos: {total_medicos}")
                except Exception as e:
                    logger.error(f"Erro ao contar médicos: {e}")
            
            # ANALISTAS
            if 'analistas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM analistas", fetch=True, one=True)
                    if isinstance(result, dict):
                        total_analistas = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        total_analistas = result[0] if result else 0
                    logger.info(f"Analistas: {total_analistas}")
                except Exception as e:
                    logger.error(f"Erro ao contar analistas: {e}")
            
            # PACIENTES
            if 'pacientes' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM pacientes", fetch=True, one=True)
                    if isinstance(result, dict):
                        total_pacientes = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        total_pacientes = result[0] if result else 0
                    logger.info(f"Pacientes: {total_pacientes}")
                except Exception as e:
                    logger.error(f"Erro ao contar pacientes: {e}")
            
            # CONSULTAS
            if 'consultas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM consultas", fetch=True, one=True)
                    if isinstance(result, dict):
                        total_consultas = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        total_consultas = result[0] if result else 0
                    logger.info(f"Consultas: {total_consultas}")
                except Exception as e:
                    logger.error(f"Erro ao contar consultas: {e}")
            
            # ========== ESTATÍSTICAS POR STATUS ==========
            if 'consultas' in tabelas_existentes:
                try:
                    # Pendentes
                    result = execute_query("SELECT COUNT(*) FROM consultas WHERE status = 'pendente'", fetch=True, one=True)
                    if isinstance(result, dict):
                        estatisticas['pendentes'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        estatisticas['pendentes'] = result[0] if result else 0
                    
                    # Em análise
                    result = execute_query("SELECT COUNT(*) FROM consultas WHERE status = 'em_analise'", fetch=True, one=True)
                    if isinstance(result, dict):
                        estatisticas['em_analise'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        estatisticas['em_analise'] = result[0] if result else 0
                    
                    # Concluídos
                    result = execute_query("SELECT COUNT(*) FROM consultas WHERE status = 'concluido'", fetch=True, one=True)
                    if isinstance(result, dict):
                        estatisticas['concluidos'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        estatisticas['concluidos'] = result[0] if result else 0
                    
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
                    
                    if colunas:
                        result = execute_query("SELECT COUNT(*) FROM consultas WHERE urgencia = 'urgente'", fetch=True, one=True)
                        if isinstance(result, dict):
                            estatisticas['urgentes'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                        elif isinstance(result, (tuple, list)):
                            estatisticas['urgentes'] = result[0] if result else 0
                    else:
                        estatisticas['urgentes'] = 0
                        logger.info("Coluna 'urgencia' não existe na tabela consultas")
                except Exception as e:
                    logger.error(f"Erro ao buscar consultas urgentes: {e}")
            
            # ========== CONSULTAS POR STATUS (AGRUPADO) ==========
            if 'consultas' in tabelas_existentes:
                try:
                    consultas_status_raw = execute_query("""
                        SELECT COALESCE(status, 'desconhecido') as status, COUNT(*) as total 
                        FROM consultas 
                        GROUP BY status
                    """, fetch=True) or []
                    
                    # Processar consultas_status
                    for item in consultas_status_raw:
                        if isinstance(item, dict):
                            consultas_status.append({
                                'status': item.get('status', 'desconhecido'),
                                'total': item.get('total', 0)
                            })
                        elif isinstance(item, (tuple, list)):
                            consultas_status.append({
                                'status': item[0] if len(item) > 0 else 'desconhecido',
                                'total': item[1] if len(item) > 1 else 0
                            })
                    
                    logger.info(f"Consultas por status: {len(consultas_status)} registros")
                except Exception as e:
                    logger.error(f"Erro ao buscar consultas por status: {e}")
            
            # ========== ÚLTIMOS USUÁRIOS ==========
            if 'usuarios' in tabelas_existentes:
                try:
                    ultimos_usuarios_raw = execute_query("""
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
                    
                    # Processar últimos usuários
                    for item in ultimos_usuarios_raw:
                        if isinstance(item, dict):
                            ultimos_usuarios.append({
                                'id': item.get('id', 0),
                                'nome': item.get('nome', 'N/A'),
                                'email': item.get('email', 'N/A'),
                                'tipo': item.get('tipo', 'N/A'),
                                'ativo': item.get('ativo', 0),
                                'criado_em': item.get('criado_em')
                            })
                        elif isinstance(item, (tuple, list)):
                            ultimos_usuarios.append({
                                'id': item[0] if len(item) > 0 else 0,
                                'nome': item[1] if len(item) > 1 else 'N/A',
                                'email': item[2] if len(item) > 2 else 'N/A',
                                'tipo': item[3] if len(item) > 3 else 'N/A',
                                'ativo': item[4] if len(item) > 4 else 0,
                                'criado_em': item[5] if len(item) > 5 else None
                            })
                    
                    logger.info(f"Últimos usuários: {len(ultimos_usuarios)} registros")
                except Exception as e:
                    logger.error(f"Erro ao buscar últimos usuários: {e}")
            
            # ========== ATIVIDADES RECENTES ==========
            if all(tabela in tabelas_existentes for tabela in ['consultas', 'pacientes', 'medicos', 'usuarios']):
                try:
                    atividades_recentes_raw = execute_query("""
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
                    
                    # Processar atividades recentes
                    for item in atividades_recentes_raw:
                        if isinstance(item, dict):
                            atividades_recentes.append({
                                'id': item.get('id', 0),
                                'descricao': item.get('descricao', ''),
                                'status': item.get('status', 'desconhecido'),
                                'data_hora': item.get('data_hora')
                            })
                        elif isinstance(item, (tuple, list)):
                            atividades_recentes.append({
                                'id': item[0] if len(item) > 0 else 0,
                                'descricao': item[1] if len(item) > 1 else '',
                                'status': item[2] if len(item) > 2 else 'desconhecido',
                                'data_hora': item[3] if len(item) > 3 else None
                            })
                    
                    logger.info(f"Atividades recentes: {len(atividades_recentes)} registros")
                except Exception as e:
                    logger.error(f"Erro ao buscar atividades recentes: {e}")
                    
                    # Query mais simples como fallback
                    try:
                        atividades_recentes_raw = execute_query("""
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
                        
                        for item in atividades_recentes_raw:
                            if isinstance(item, dict):
                                atividades_recentes.append({
                                    'id': item.get('id', 0),
                                    'descricao': item.get('descricao', 'Consulta'),
                                    'status': item.get('status', 'desconhecido'),
                                    'data_hora': item.get('data_hora')
                                })
                            elif isinstance(item, (tuple, list)):
                                atividades_recentes.append({
                                    'id': item[0] if len(item) > 0 else 0,
                                    'descricao': item[1] if len(item) > 1 else 'Consulta',
                                    'status': item[2] if len(item) > 2 else 'desconhecido',
                                    'data_hora': item[3] if len(item) > 3 else None
                                })
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
            
            # CORREÇÃO: Extrair nomes das tabelas de forma segura
            tabelas_existentes = []
            for t in tabelas:
                if isinstance(t, dict):
                    nome = t.get('table_name')
                    if nome:
                        tabelas_existentes.append(nome)
                elif isinstance(t, (tuple, list)) and len(t) > 0 and t[0]:
                    tabelas_existentes.append(t[0])
            
            # Médicos
            if 'medicos' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM medicos", fetch=True, one=True)
                    if isinstance(result, dict):
                        stats['medicos'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        stats['medicos'] = result[0] if result else 0
                except:
                    pass
            
            # Analistas
            if 'analistas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM analistas", fetch=True, one=True)
                    if isinstance(result, dict):
                        stats['analistas'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        stats['analistas'] = result[0] if result else 0
                except:
                    pass
            
            # Pacientes
            if 'pacientes' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM pacientes", fetch=True, one=True)
                    if isinstance(result, dict):
                        stats['pacientes'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        stats['pacientes'] = result[0] if result else 0
                except:
                    pass
            
            # Consultas
            if 'consultas' in tabelas_existentes:
                try:
                    result = execute_query("SELECT COUNT(*) FROM consultas", fetch=True, one=True)
                    if isinstance(result, dict):
                        stats['consultas'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        stats['consultas'] = result[0] if result else 0
                except:
                    pass
                
                # Consultas de hoje
                try:
                    result = execute_query("""
                        SELECT COUNT(*) 
                        FROM consultas 
                        WHERE DATE(data_hora) = CURDATE()
                    """, fetch=True, one=True)
                    if isinstance(result, dict):
                        stats['consultas_hoje'] = extrair_valor(result, 0, 'COUNT(*)', 0)
                    elif isinstance(result, (tuple, list)):
                        stats['consultas_hoje'] = result[0] if result else 0
                except:
                    pass
            
            return jsonify({'success': True, 'data': stats})
            
        except Exception as e:
            logger.error(f"Erro na API de stats: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
