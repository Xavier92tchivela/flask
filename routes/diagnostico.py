from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from flask_mysqldb import MySQL
from datetime import datetime, date
import json
import logging
import os
from functools import wraps
import traceback
import base64
from PIL import Image
import io
import google.generativeai as genai

logger = logging.getLogger(__name__)

def init_analista(mysql, client=None, gemini_available=False, MODEL_NAME=None, app=None):
    """Inicializa e retorna o blueprint do analista"""
    
    analista_bp = Blueprint('analista', __name__, url_prefix='/analista')
    
    # ========== CONFIGURAÇÃO GEMINI ==========
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if GEMINI_API_KEY and not gemini_available:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            client = genai.GenerativeModel('gemini-pro-vision')
            gemini_available = True
            MODEL_NAME = 'gemini-pro-vision'
            logger.info("API Gemini configurada com sucesso")
        except Exception as e:
            logger.error(f"Erro ao configurar Gemini: {e}")
            gemini_available = False
    
    # ========== DECORATORS ==========
    def analista_required(f):
        """Decorator para garantir que o usuário é um analista"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            if session.get('user_type') != 'analista':
                flash('Acesso restrito a analistas.', 'warning')
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÕES AUXILIARES ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Função auxiliar para executar queries no banco de dados"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                if one:
                    return result[0] if result else None
                return result
            else:
                mysql.connection.commit()
                cur.close()
                return None
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, str):
            try:
                if 'T' in data:
                    return datetime.fromisoformat(data.replace('Z', '+00:00')).strftime(formato)
                else:
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(data, fmt).strftime(formato)
                        except ValueError:
                            continue
                    return data
            except:
                return data
        return str(data)
    
    def obter_info_analista():
        """Obtém informações do analista logado"""
        try:
            user_id = session.get('user_id')
            if not user_id:
                return None
            
            # Buscar informações do analista
            analista_info = execute_query("""
                SELECT a.*, u.nome, u.email, u.telefone
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE a.usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                # Se não encontrar, criar estrutura básica
                usuario_info = execute_query(
                    "SELECT nome, email, telefone FROM usuarios WHERE id = %s",
                    (user_id,), fetch=True, one=True
                )
                
                if usuario_info:
                    return {
                        'id': None,
                        'usuario_id': user_id,
                        'especialidade': 'Geral',
                        'registro_profissional': 'N/A',
                        'is_supervisor': False,
                        'status': 'ativo',
                        'nome': usuario_info[0],
                        'email': usuario_info[1],
                        'telefone': usuario_info[2]
                    }
                return None
            
            # Converter para dicionário
            return {
                'id': analista_info[0],
                'usuario_id': analista_info[1],
                'especialidade': analista_info[2],
                'registro_profissional': analista_info[3],
                'is_supervisor': bool(analista_info[4]),
                'status': analista_info[5],
                'criado_em': formatar_data(analista_info[6]),
                'atualizado_em': formatar_data(analista_info[7]),
                'nome': analista_info[8],
                'email': analista_info[9],
                'telefone': analista_info[10]
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter info analista: {e}")
            return None
    
    def calcular_idade(data_nascimento):
        """Calcula idade a partir da data de nascimento"""
        if not data_nascimento:
            return None
        
        try:
            if isinstance(data_nascimento, str):
                # Tentar diferentes formatos
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        nascimento = datetime.strptime(data_nascimento, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    return None
            elif isinstance(data_nascimento, datetime):
                nascimento = data_nascimento.date()
            else:
                nascimento = data_nascimento
            
            hoje = date.today()
            idade = hoje.year - nascimento.year
            
            # Ajustar se ainda não fez aniversário este ano
            if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                idade -= 1
            
            return idade
        except Exception as e:
            logger.error(f"Erro ao calcular idade: {e}")
            return None
    
    def processar_imagem_gemini_avancado(imagem_path, tipo_analise, observacoes="", contexto_paciente=None):
        """Processa imagem usando Gemini API para análise avançada"""
        try:
            if not gemini_available or not client:
                return None, "API Gemini não configurada"
            
            # Ler imagem
            with open(imagem_path, "rb") as img_file:
                imagem_bytes = img_file.read()
            
            # Preparar contexto do paciente
            contexto_texto = ""
            if contexto_paciente:
                contexto_texto = f"""
                CONTEXTO DO PACIENTE:
                - Nome: {contexto_paciente.get('nome', 'Não informado')}
                - Idade: {contexto_paciente.get('idade', 'Não informada')}
                - Gênero: {contexto_paciente.get('genero', 'Não informado')}
                - Tipo de Exame: {contexto_paciente.get('tipo_exame', 'Não especificado')}
                - Descrição: {contexto_paciente.get('descricao', '')}
                """
            
            # Criar prompt baseado no tipo de análise
            if tipo_analise == "completa":
                prompt = f"""
                Você é um especialista médico analisando uma imagem de exame. 
                
                {contexto_texto}
                
                Observações do analista: {observacoes}
                
                FORNECE UMA ANÁLISE DETALHADA COM:
                
                1. DESCRIÇÃO TÉCNICA DA IMAGEM:
                - Tipo de imagem (radiografia, ultrassom, tomografia, ressonância, etc.)
                - Região anatômica
                - Qualidade técnica
                - Posicionamento
                
                2. ACHADOS PRINCIPAIS:
                - Estruturas normais identificadas
                - Anormalidades detectadas
                - Medidas relevantes (se aplicável)
                - Densidades, cores, contrastes
                
                3. ANÁLISE DE ANORMALIDADES:
                - Localização precisa
                - Características (tamanho, forma, bordas, densidade)
                - Relação com estruturas adjacentes
                - Presença de múltiplas lesões
                
                4. DIAGNÓSTICO DIFERENCIAL:
                - Lista de possíveis diagnósticos em ordem de probabilidade
                - Justificativa para cada possibilidade
                - Fatores que suportam ou refutam cada diagnóstico
                
                5. RECOMENDAÇÕES:
                - Exames complementares necessários
                - Acompanhamento sugerido
                - Tratamentos iniciais a considerar
                - Referência a especialista se necessário
                
                6. NÍVEL DE URGÊNCIA:
                - Classifique como: URGENTE, ALTA PRIORIDADE, ROTINA
                - Justifique a classificação
                
                7. RELATÓRIO PARA O MÉDICO:
                - Resumo executivo
                - Achados mais relevantes
                - Recomendações principais
                
                Formate a resposta de forma clara, usando títulos, subtítulos e listas.
                Use linguagem médica apropriada mas explique termos técnicos quando necessário.
                """
            
            elif tipo_analise == "detect_anomalies":
                prompt = f"""
                Analise esta imagem médica e DETECTE ESPECIFICAMENTE ANOMALIAS:
                
                {contexto_texto}
                
                Observações: {observacoes}
                
                FOQUE EM:
                1. Liste TODAS as anomalias visíveis
                2. Para cada anomalia:
                   - Localização exata
                   - Tamanho aproximado
                   - Forma e características
                   - Densidade/ecogenicidade
                   - Efeito nas estruturas vizinhas
                3. Classifique por gravidade:
                   - CRÍTICA (necessita intervenção imediata)
                   - GRAVE (necessita atenção urgente)
                   - MODERADA (acompanhamento necessário)
                   - LEVE (observação)
                4. Sugira próximos passos imediatos
                """
            
            elif tipo_analise == "comparative":
                prompt = f"""
                Analise esta imagem para COMPARAÇÃO com exames anteriores:
                
                {contexto_texto}
                
                Observações: {observacoes}
                
                FORNECE:
                1. Comparação de achados
                2. Progressão ou regressão de lesões
                3. Novas alterações
                4. Resolução de alterações anteriores
                5. Avaliação de resposta a tratamento
                """
            
            else:  # análise rápida
                prompt = f"""
                ANÁLISE RÁPIDA DE IMAGEM MÉDICA:
                
                {contexto_texto}
                
                Observações: {observacoes}
                
                Forneça em formato conciso:
                - Achados principais (máximo 5)
                - Anomalias detectadas
                - Recomendação inicial
                - Urgência sugerida
                """
            
            # Preparar imagem para Gemini
            image_parts = [
                {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(imagem_bytes).decode('utf-8')
                }
            ]
            
            # Configurar o modelo
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 4096,  # Aumentado para análises mais longas
            }
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            # Chamar API Gemini
            response = client.generate_content(
                contents=[prompt] + image_parts,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            return response.text, None
            
        except Exception as e:
            logger.error(f"Erro ao processar imagem com Gemini: {e}")
            logger.error(traceback.format_exc())
            return None, f"Erro na análise: {str(e)}"
    
    # ========== ROTAS PRINCIPAIS ==========
    
    @analista_bp.route('/')
    @analista_bp.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista"""
        analista_info = obter_info_analista()
        
        # Buscar pedidos atribuídos ao analista
        pedidos = execute_query("""
            SELECT pa.*, 
                   p_u.nome as paciente_nome,
                   c.data_hora as data_consulta,
                   m_u.nome as medico_nome,
                   m.especialidade
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN consultas c ON pa.consulta_id = c.id
            JOIN medicos m ON pa.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE pa.analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
            AND pa.status IN ('pendente', 'em_analise')
            ORDER BY 
                CASE pa.urgencia 
                    WHEN 'urgente' THEN 1
                    WHEN 'alta' THEN 2
                    WHEN 'normal' THEN 3
                    ELSE 4
                END,
                pa.data_solicitacao DESC
            LIMIT 10
        """, (session['user_id'],), fetch=True)
        
        # Converter para lista de dicionários
        pedidos_formatados = []
        for pedido in pedidos:
            pedidos_formatados.append({
                'id': pedido[0],
                'consulta_id': pedido[1],
                'paciente_nome': pedido[18] if len(pedido) > 18 else 'Paciente',
                'medico_nome': pedido[20] if len(pedido) > 20 else 'Médico',
                'tipo_exame': pedido[5] if len(pedido) > 5 else 'Exame',
                'descricao': pedido[6] if len(pedido) > 6 else '',
                'observacoes': pedido[7] if len(pedido) > 7 else '',
                'urgencia': pedido[8] if len(pedido) > 8 else 'normal',
                'status': pedido[9] if len(pedido) > 9 else 'pendente',
                'data_solicitacao': formatar_data(pedido[10]) if len(pedido) > 10 else '',
                'has_anexos': bool(pedido[15]) if len(pedido) > 15 else False
            })
        
        # Estatísticas rápidas
        estatisticas = execute_query("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) as pendentes,
                SUM(CASE WHEN status = 'em_analise' THEN 1 ELSE 0 END) as em_analise,
                SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) as concluidos
            FROM pedidos_analise 
            WHERE analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
        """, (session['user_id'],), fetch=True, one=True)
        
        return render_template('analista/dashboard.html', 
                             pedidos=pedidos_formatados,
                             estatisticas=estatisticas,
                             analista_info=analista_info,
                             user=session,
                             gemini_available=gemini_available)
    
    @analista_bp.route('/api/dashboard-stats')
    @analista_required
    def api_dashboard_stats():
        """API para estatísticas do dashboard do analista"""
        try:
            # Buscar estatísticas do analista
            analista_id_result = execute_query(
                "SELECT id FROM analistas WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            
            if not analista_id_result:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_id_result[0]
            
            # Contadores para o dashboard
            stats = {
                'pedidos_pendentes': execute_query("""
                    SELECT COUNT(*) FROM pedidos_analise 
                    WHERE analista_id = %s AND status = 'pendente'
                """, (analista_id,), fetch=True, one=True) or (0,),
                
                'pedidos_em_analise': execute_query("""
                    SELECT COUNT(*) FROM pedidos_analise 
                    WHERE analista_id = %s AND status = 'em_analise'
                """, (analista_id,), fetch=True, one=True) or (0,),
                
                'analises_concluidas_7dias': execute_query("""
                    SELECT COUNT(*) FROM pedidos_analise 
                    WHERE analista_id = %s 
                    AND status = 'concluido'
                    AND data_conclusao >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                """, (analista_id,), fetch=True, one=True) or (0,),
                
                'analises_aprovacao_pendente': execute_query("""
                    SELECT COUNT(*) FROM pedidos_analise 
                    WHERE analista_id = %s 
                    AND status = 'concluido'
                    AND status_aprovacao = 'pendente'
                """, (analista_id,), fetch=True, one=True) or (0,)
            }
            
            return jsonify({
                'success': True,
                'stats': {
                    'pedidos_pendentes': stats['pedidos_pendentes'][0],
                    'pedidos_em_analise': stats['pedidos_em_analise'][0],
                    'analises_concluidas_7dias': stats['analises_concluidas_7dias'][0],
                    'analises_aprovacao_pendente': stats['analises_aprovacao_pendente'][0],
                    'gemini_available': gemini_available
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do dashboard: {e}")
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar estatísticas'
            }), 500
    
    @analista_bp.route('/pedidos')
    @analista_required
    def pedidos():
        """Listar todos os pedidos atribuídos ao analista"""
        analista_info = obter_info_analista()
        
        status_filter = request.args.get('status', 'todos')
        urgencia_filter = request.args.get('urgencia', 'todos')
        
        # Construir query base
        query = """
            SELECT pa.*, 
                   p_u.nome as paciente_nome,
                   c.data_hora as data_consulta,
                   m_u.nome as medico_nome,
                   m.especialidade
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN consultas c ON pa.consulta_id = c.id
            JOIN medicos m ON pa.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE pa.analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
        """
        
        params = [session['user_id']]
        
        # Adicionar filtros
        conditions = []
        if status_filter != 'todos':
            conditions.append("pa.status = %s")
            params.append(status_filter)
        
        if urgencia_filter != 'todos':
            conditions.append("pa.urgencia = %s")
            params.append(urgencia_filter)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY pa.data_solicitacao DESC"
        
        pedidos = execute_query(query, params, fetch=True)
        
        # Converter para lista de dicionários
        pedidos_formatados = []
        for pedido in pedidos:
            pedidos_formatados.append({
                'id': pedido[0],
                'paciente_nome': pedido[18] if len(pedido) > 18 else 'Paciente',
                'medico_nome': pedido[20] if len(pedido) > 20 else 'Médico',
                'tipo_exame': pedido[5] if len(pedido) > 5 else 'Exame',
                'descricao': pedido[6] if len(pedido) > 6 else '',
                'urgencia': pedido[8] if len(pedido) > 8 else 'normal',
                'status': pedido[9] if len(pedido) > 9 else 'pendente',
                'data_solicitacao': formatar_data(pedido[10]) if len(pedido) > 10 else '',
                'has_anexos': bool(pedido[15]) if len(pedido) > 15 else False
            })
        
        return render_template('analista/pedidos.html', 
                             pedidos=pedidos_formatados,
                             status_filter=status_filter,
                             urgencia_filter=urgencia_filter,
                             analista_info=analista_info,
                             gemini_available=gemini_available,
                             user=session)
    
    @analista_bp.route('/pedidos/analisar/<int:pedido_id>', methods=['GET', 'POST'])
    @analista_required
    def analisar_pedido(pedido_id):
        """Página para análise de um pedido específico"""
        analista_info = obter_info_analista()
        
        # Verificar se o pedido existe e pertence ao analista
        pedido = execute_query("""
            SELECT pa.*, 
                   p_u.nome as paciente_nome,
                   p.data_nascimento,
                   p.genero,
                   c.data_hora as data_consulta,
                   c.observacoes as consulta_observacoes,
                   m_u.nome as medico_nome,
                   m.especialidade,
                   m.crm
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN consultas c ON pa.consulta_id = c.id
            JOIN medicos m ON pa.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE pa.id = %s AND pa.analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
        """, (pedido_id, session['user_id']), fetch=True, one=True)
        
        if not pedido:
            flash('Pedido não encontrado ou não tem permissão para analisar.', 'danger')
            return redirect(url_for('analista.dashboard'))
        
        if request.method == 'POST':
            # Verificar ação do formulário
            acao = request.form.get('acao')
            
            if acao == 'iniciar_analise':
                # Iniciar análise
                execute_query("""
                    UPDATE pedidos_analise 
                    SET status = 'em_analise'
                    WHERE id = %s
                """, (pedido_id,))
                
                flash('Análise iniciada com sucesso!', 'success')
                return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            
            elif acao == 'concluir':
                # Concluir análise
                resultado_analise = request.form.get('resultado_analise', '').strip()
                diagnostico_analista = request.form.get('diagnostico_analista', '').strip()
                recomendacoes_analista = request.form.get('recomendacoes_analista', '').strip()
                
                if not resultado_analise or not diagnostico_analista:
                    flash('Resultado e diagnóstico são obrigatórios.', 'warning')
                    return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
                
                # Atualizar pedido com os resultados da análise
                execute_query("""
                    UPDATE pedidos_analise 
                    SET resultado_analise = %s,
                        diagnostico_analista = %s,
                        recomendacoes_analista = %s,
                        status = 'concluido',
                        data_conclusao = NOW()
                    WHERE id = %s
                """, (resultado_analise, diagnostico_analista, recomendacoes_analista, pedido_id))
                
                flash('Análise concluída com sucesso! O médico será notificado.', 'success')
                return redirect(url_for('analista.dashboard'))
        
        # GET: Preparar dados para o template
        # Converter para dicionário
        pedido_dict = {
            'id': pedido[0],
            'consulta_id': pedido[1],
            'medico_id': pedido[2],
            'paciente_id': pedido[3],
            'analista_id': pedido[4],
            'tipo_exame': pedido[5] if len(pedido) > 5 else '',
            'descricao': pedido[6] if len(pedido) > 6 else '',
            'observacoes': pedido[7] if len(pedido) > 7 else '',
            'urgencia': pedido[8] if len(pedido) > 8 else 'normal',
            'status': pedido[9] if len(pedido) > 9 else 'pendente',
            'data_solicitacao': formatar_data(pedido[10]) if len(pedido) > 10 else '',
            'data_conclusao': formatar_data(pedido[11]) if len(pedido) > 11 else None,
            'resultado_analise': pedido[12] if len(pedido) > 12 else '',
            'diagnostico_analista': pedido[13] if len(pedido) > 13 else '',
            'recomendacoes_analista': pedido[14] if len(pedido) > 14 else '',
            'anexos': pedido[15] if len(pedido) > 15 else None,
            'status_aprovacao': pedido[16] if len(pedido) > 16 else 'pendente',
            'observacoes_medico': pedido[17] if len(pedido) > 17 else '',
            'paciente_nome': pedido[18] if len(pedido) > 18 else 'Paciente',
            'paciente_data_nascimento': pedido[19] if len(pedido) > 19 else None,
            'paciente_genero': pedido[20] if len(pedido) > 20 else '',
            'data_consulta': formatar_data(pedido[21]) if len(pedido) > 21 else '',
            'consulta_observacoes': pedido[22] if len(pedido) > 22 else '',
            'medico_nome': pedido[23] if len(pedido) > 23 else 'Médico',
            'medico_especialidade': pedido[24] if len(pedido) > 24 else '',
            'medico_crm': pedido[25] if len(pedido) > 25 else ''
        }
        
        # Calcular idade do paciente
        if pedido_dict['paciente_data_nascimento']:
            pedido_dict['paciente_idade'] = calcular_idade(pedido_dict['paciente_data_nascimento'])
        
        # Converter anexos de JSON para lista
        anexos_pedido = []
        if pedido_dict.get('anexos'):
            try:
                anexos_data = json.loads(pedido_dict['anexos'])
                if isinstance(anexos_data, list):
                    anexos_pedido = anexos_data
                elif isinstance(anexos_data, dict):
                    anexos_pedido = [anexos_data]
            except Exception as e:
                logger.error(f"Erro ao converter anexos: {e}")
                anexos_pedido = []
        
        # Buscar histórico de diagnósticos do paciente
        diagnosticos_anteriores = []
        try:
            diags = execute_query("""
                SELECT d.*, c.data_hora as data_consulta
                FROM diagnostico d
                JOIN consultas c ON d.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
                LIMIT 5
            """, (pedido[3],), fetch=True)
            
            if diags:
                for diag in diags:
                    diagnosticos_anteriores.append({
                        'id': diag[0],
                        'consulta_id': diag[1],
                        'diagnostico': diag[2],
                        'recomendacoes': diag[3],
                        'data_consulta': formatar_data(diag[4]) if diag[4] else ''
                    })
        except Exception as e:
            logger.error(f"Erro ao buscar diagnósticos anteriores: {e}")
        
        return render_template('analista/analisar_exame.html',
                             pedido=pedido_dict,
                             anexos_pedido=anexos_pedido,
                             diagnosticos_anteriores=diagnosticos_anteriores,
                             analista_info=analista_info,
                             gemini_available=gemini_available,
                             user=session,
                             now=datetime.now())
    
    @analista_bp.route('/api/analisar_imagem/<int:pedido_id>', methods=['POST'])
    @analista_required
    def analisar_imagem(pedido_id):
        """API para análise de imagem com IA Gemini"""
        try:
            # Verificar se o pedido pertence ao analista
            pedido_check = execute_query("""
                SELECT id FROM pedidos_analise 
                WHERE id = %s AND analista_id = (
                    SELECT id FROM analistas WHERE usuario_id = %s
                )
            """, (pedido_id, session['user_id']), fetch=True, one=True)
            
            if not pedido_check:
                return jsonify({'error': 'Pedido não encontrado ou sem permissão'}), 403
            
            # Verificar arquivo de imagem
            if 'imagem' not in request.files:
                return jsonify({'error': 'Nenhuma imagem enviada'}), 400
            
            imagem = request.files['imagem']
            if imagem.filename == '':
                return jsonify({'error': 'Nenhuma imagem selecionada'}), 400
            
            # Verificar extensão
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}
            if '.' not in imagem.filename or \
               imagem.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return jsonify({'error': 'Formato de arquivo não suportado'}), 400
            
            # Obter tipo de análise
            tipo_analise = request.form.get('tipo_analise', 'completa')
            observacoes = request.form.get('observacoes_analista', '')
            
            # Criar diretório para uploads se não existir
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'analista')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Salvar imagem
            filename = f"pedido_{pedido_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{imagem.filename}"
            filepath = os.path.join(upload_dir, filename)
            imagem.save(filepath)
            
            # Buscar informações do pedido para contexto
            pedido_info = execute_query("""
                SELECT pa.tipo_exame, pa.descricao, pa.observacoes,
                       p.data_nascimento, p.genero, u.nome as paciente_nome
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            contexto_paciente = None
            if pedido_info:
                idade = calcular_idade(pedido_info[3]) if pedido_info[3] else None
                contexto_paciente = {
                    'nome': pedido_info[5] if pedido_info[5] else 'Paciente',
                    'idade': idade,
                    'genero': pedido_info[4] if pedido_info[4] else 'Não informado',
                    'tipo_exame': pedido_info[0] if pedido_info[0] else 'Exame',
                    'descricao': pedido_info[1] if pedido_info[1] else '',
                    'observacoes': pedido_info[2] if pedido_info[2] else ''
                }
            
            # Processar imagem com Gemini se disponível
            diagnostico = ""
            if gemini_available and client:
                diagnostico, error = processar_imagem_gemini_avancado(
                    filepath, 
                    tipo_analise, 
                    observacoes,
                    contexto_paciente
                )
                
                if error:
                    diagnostico = f"""
                    ⚠️ **API GEMINI INDISPONÍVEL**
                    
                    **Arquivo:** {imagem.filename}
                    **Tipo de análise solicitada:** {tipo_analise}
                    **Observações do analista:** {observacoes}
                    
                    **ERRO:** {error}
                    
                    **RECOMENDAÇÃO:**
                    Faça uma análise manual detalhada da imagem ou configure a API Gemini.
                    """
                    warning = error
                else:
                    # Adicionar cabeçalho ao diagnóstico
                    diagnostico_completo = f"""
                    📋 **RELATÓRIO DE ANÁLISE COM IA GEMINI**
                    
                    **Data da análise:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
                    **Pedido:** #{pedido_id}
                    **Arquivo analisado:** {imagem.filename}
                    **Tipo de análise:** {tipo_analise}
                    **Observações do analista:** {observacoes}
                    
                    {'**Contexto do paciente:**' if contexto_paciente else ''}
                    {f"- Paciente: {contexto_paciente.get('nome', '')}" if contexto_paciente else ''}
                    {f"- Idade: {contexto_paciente.get('idade', '')}" if contexto_paciente and contexto_paciente.get('idade') else ''}
                    {f"- Gênero: {contexto_paciente.get('genero', '')}" if contexto_paciente else ''}
                    {f"- Tipo de exame: {contexto_paciente.get('tipo_exame', '')}" if contexto_paciente else ''}
                    
                    {'---' * 20}
                    
                    {diagnostico}
                    
                    {'---' * 20}
                    
                    **Analista responsável:** {session.get('user_name', 'Analista')}
                    **Data e hora:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                    
                    *Este é um relatório gerado por IA. O analista médico deve revisar e validar todas as informações.*
                    """
                    diagnostico = diagnostico_completo
                    warning = None
            else:
                # Análise básica (offline)
                diagnostico = f"""
                ⚠️ **ANÁLISE BÁSICA (SEM IA)**
                
                **Data da análise:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
                **Pedido:** #{pedido_id}
                **Arquivo:** {imagem.filename}
                **Tipo de análise:** {tipo_analise}
                **Observações do analista:** {observacoes}
                
                **DETALHES TÉCNICOS:**
                - Arquivo salvo com sucesso: {filename}
                - Tamanho: {os.path.getsize(filepath)} bytes
                - API Gemini não configurada
                
                **RECOMENDAÇÕES PARA ANÁLISE MANUAL:**
                1. Examine cuidadosamente toda a imagem
                2. Procure por anomalias ou padrões incomuns
                3. Compare com imagens de referência
                4. Considere o contexto clínico do paciente
                5. Documente todos os achados relevantes
                6. Consulte literatura médica específica
                7. Considere exames complementares
                
                **Para análise completa com IA, configure a API Gemini nas configurações do sistema.**
                
                ---
                
                **Analista:** {session.get('user_name', 'Analista')}
                **Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                """
                warning = "API Gemini não configurada. Análise básica fornecida."
            
            # Salvar resultado no banco de dados (rascunho)
            execute_query("""
                UPDATE pedidos_analise 
                SET resultado_analise = CONCAT(COALESCE(resultado_analise, ''), '\n\n---\n', %s)
                WHERE id = %s
            """, (f"Análise IA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n{diagnostico}", pedido_id))
            
            return jsonify({
                'success': True,
                'diagnostico': diagnostico,
                'arquivo': filename,
                'gemini_available': gemini_available,
                'warning': warning if 'warning' in locals() else None,
                'contexto_paciente': contexto_paciente
            })
            
        except Exception as e:
            logger.error(f"Erro na análise de imagem: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500
    
    @analista_bp.route('/download_anexo/<int:pedido_id>/<filename>')
    @analista_required
    def download_anexo(pedido_id, filename):
        """Download de anexo do pedido"""
        # Verificar permissão
        pedido_check = execute_query("""
            SELECT id FROM pedidos_analise 
            WHERE id = %s AND analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
        """, (pedido_id, session['user_id']), fetch=True, one=True)
        
        if not pedido_check:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('analista.dashboard'))
        
        # Construir caminho do arquivo
        filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'analista', filename)
        
        if not os.path.exists(filepath):
            flash('Arquivo não encontrado.', 'warning')
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
        
        # Enviar arquivo
        from flask import send_file
        return send_file(filepath, as_attachment=True)
    
    # ========== OUTRAS ROTAS ==========
    
    @analista_bp.route('/minhas-analises')
    @analista_required
    def minhas_analises():
        """Listar análises concluídas pelo analista"""
        analista_info = obter_info_analista()
        
        analises = execute_query("""
            SELECT pa.*, 
                   p_u.nome as paciente_nome,
                   c.data_hora as data_consulta,
                   m_u.nome as medico_nome,
                   pa.status_aprovacao
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN consultas c ON pa.consulta_id = c.id
            JOIN medicos m ON pa.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE pa.analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
            AND pa.status = 'concluido'
            ORDER BY pa.data_conclusao DESC
        """, (session['user_id'],), fetch=True)
        
        # Converter para lista de dicionários
        analises_formatadas = []
        for analise in analises:
            analises_formatadas.append({
                'id': analise[0],
                'paciente_nome': analise[18] if len(analise) > 18 else 'Paciente',
                'medico_nome': analise[20] if len(analise) > 20 else 'Médico',
                'tipo_exame': analise[5] if len(analise) > 5 else 'Exame',
                'diagnostico_analista': analise[13] if len(analise) > 13 else '',
                'status_aprovacao': analise[16] if len(analise) > 16 else 'pendente',
                'data_conclusao': formatar_data(analise[11]) if len(analise) > 11 else ''
            })
        
        return render_template('analista/minhas_analises.html',
                             analises=analises_formatadas,
                             analista_info=analista_info,
                             gemini_available=gemini_available,
                             user=session)
    
    @analista_bp.route('/perfil')
    @analista_required
    def perfil():
        """Perfil do analista"""
        analista_info = obter_info_analista()
        
        if not analista_info:
            flash('Informações do analista não encontradas.', 'danger')
            return redirect(url_for('analista.dashboard'))
        
        # Estatísticas do analista
        estatisticas = execute_query("""
            SELECT 
                COUNT(*) as total_analises,
                SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) as analises_concluidas,
                SUM(CASE WHEN status_aprovacao = 'aprovado' THEN 1 ELSE 0 END) as analises_aprovadas,
                SUM(CASE WHEN urgencia = 'urgente' THEN 1 ELSE 0 END) as urgencias
            FROM pedidos_analise 
            WHERE analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
        """, (session['user_id'],), fetch=True, one=True)
        
        return render_template('analista/perfil.html',
                             analista=analista_info,
                             estatisticas=estatisticas,
                             gemini_available=gemini_available,
                             user=session)
    
    @analista_bp.route('/configuracoes')
    @analista_required
    def configuracoes():
        """Configurações do analista"""
        analista_info = obter_info_analista()
        return render_template('analista/configuracoes.html',
                             analista=analista_info,
                             gemini_available=gemini_available,
                             user=session)
    
    @analista_bp.route('/relatorios')
    @analista_required
    def relatorios():
        """Relatórios do analista"""
        analista_info = obter_info_analista()
        return render_template('analista/relatorios.html',
                             analista_info=analista_info,
                             gemini_available=gemini_available,
                             user=session)
    
    @analista_bp.route('/api/contadores')
    @analista_required
    def api_contadores():
        """API para contadores do dashboard"""
        # Pedidos em análise
        pedidos_analise = execute_query("""
            SELECT COUNT(*) FROM pedidos_analise 
            WHERE analista_id = (SELECT id FROM analistas WHERE usuario_id = %s)
            AND status = 'em_analise'
        """, (session['user_id'],), fetch=True, one=True)
        
        # Pedidos pendentes
        pedidos_pendentes = execute_query("""
            SELECT COUNT(*) FROM pedidos_analise 
            WHERE analista_id = (SELECT id FROM analistas WHERE usuario_id = %s)
            AND status = 'pendente'
        """, (session['user_id'],), fetch=True, one=True)
        
        # Análises concluídas
        analises_concluidas = execute_query("""
            SELECT COUNT(*) FROM pedidos_analise 
            WHERE analista_id = (SELECT id FROM analistas WHERE usuario_id = %s)
            AND status = 'concluido'
        """, (session['user_id'],), fetch=True, one=True)
        
        # Análises aprovadas
        analises_aprovadas = execute_query("""
            SELECT COUNT(*) FROM pedidos_analise 
            WHERE analista_id = (SELECT id FROM analistas WHERE usuario_id = %s)
            AND status_aprovacao = 'aprovado'
        """, (session['user_id'],), fetch=True, one=True)
        
        return jsonify({
            'pedidos_analise': pedidos_analise[0] if pedidos_analise else 0,
            'pedidos_pendentes': pedidos_pendentes[0] if pedidos_pendentes else 0,
            'analises_concluidas': analises_concluidas[0] if analises_concluidas else 0,
            'analises_aprovadas': analises_aprovadas[0] if analises_aprovadas else 0,
            'gemini_available': gemini_available
        })
    
    @analista_bp.route('/proximo-pedido')
    @analista_required
    def proximo_pedido():
        """Redirecionar para o próximo pedido"""
        # Buscar próximo pedido pendente
        proximo = execute_query("""
            SELECT pa.id
            FROM pedidos_analise pa
            WHERE pa.analista_id = (
                SELECT id FROM analistas WHERE usuario_id = %s
            )
            AND pa.status = 'pendente'
            ORDER BY 
                CASE pa.urgencia 
                    WHEN 'urgente' THEN 1
                    WHEN 'alta' THEN 2
                    WHEN 'normal' THEN 3
                    ELSE 4
                END,
                pa.data_solicitacao ASC
            LIMIT 1
        """, (session['user_id'],), fetch=True, one=True)
        
        if proximo:
            return redirect(url_for('analista.analisar_pedido', pedido_id=proximo[0]))
        else:
            flash('Não há pedidos disponíveis no momento.', 'info')
            return redirect(url_for('analista.dashboard'))
    
    @analista_bp.route('/api/gemini-status')
    @analista_required
    def api_gemini_status():
        """API para verificar status da Gemini"""
        return jsonify({
            'gemini_available': gemini_available,
            'model_name': MODEL_NAME if gemini_available else None
        })
    
    return analista_bp