from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from functools import wraps
from datetime import datetime
import json
import logging
import traceback
import os
import base64
from io import BytesIO
import requests
from PIL import Image
import google.generativeai as genai

logger = logging.getLogger(__name__)

def init_analista(mysql, client, gemini_available, MODEL_NAME, app):
    """Inicializa o blueprint do analista - VERSÃO COMPLETA"""
    
    analista_bp = Blueprint('analista', __name__, url_prefix='/analista')
    
    def execute_query(query, params=None, fetch=False, commit=True, one=False):
        """Executa consulta SQL"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                if one:
                    result = cur.fetchone()
                else:
                    result = cur.fetchall()
            else:
                result = cur.lastrowid
            
            if not fetch and commit:
                mysql.connection.commit()
            
            cur.close()
            return result
        except Exception as e:
            logger.error(f"Database error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            try:
                mysql.connection.rollback()
            except:
                pass
            return None
    
    def analista_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            if session.get('user_type') != 'analista':
                flash('Acesso restrito a analistas.', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data para exibição"""
        if not data:
            return ''
        try:
            if isinstance(data, datetime):
                return data.strftime(formato)
            elif isinstance(data, str):
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(data, fmt).strftime(formato)
                    except ValueError:
                        continue
                return data
            return str(data)
        except Exception as e:
            return str(data)
    
    def calcular_idade(data_nascimento):
        """Calcula idade a partir da data de nascimento"""
        if not data_nascimento:
            return ''
        try:
            if isinstance(data_nascimento, str):
                try:
                    data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d')
                except:
                    try:
                        data_nascimento = datetime.strptime(data_nascimento, '%d/%m/%Y')
                    except:
                        return ''
            hoje = datetime.now()
            idade = hoje.year - data_nascimento.year
            if hoje.month < data_nascimento.month or (hoje.month == data_nascimento.month and hoje.day < data_nascimento.day):
                idade -= 1
            return f"{idade} anos"
        except:
            return ''

    # ========== FUNÇÕES AUXILIARES ==========
    
    def criar_notificacao_medico(medico_id, pedido_id, titulo, mensagem, tipo='diagnostico'):
        """Cria notificação para o médico sobre novo diagnóstico"""
        try:
            # Inserir notificação na tabela notificacoes
            result = execute_query("""
                INSERT INTO notificacoes 
                (usuario_id, tipo, titulo, mensagem, referencia_id, lida, criado_em)
                VALUES (%s, %s, %s, %s, %s, FALSE, NOW())
            """, (
                medico_id,
                tipo,
                titulo,
                mensagem,
                pedido_id
            ), commit=True)
            
            if result:
                logger.info(f"Notificação criada para médico {medico_id} sobre pedido {pedido_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Erro ao criar notificação: {e}")
            return False
    
    def salvar_diagnostico_ia(consulta_id, tipo_exame, descricao, observacoes, 
                             resultado, diagnostico_ia, status='pendente', 
                             imagem_path=None, imagem_base64=None, formato_imagem=None, tamanho_imagem=None):
        """Salva diagnóstico gerado pela IA na tabela diagnostico"""
        try:
            # Verificar se já existe diagnóstico para esta consulta
            existing_diagnostic = execute_query("""
                SELECT id FROM diagnostico WHERE consulta_id = %s
            """, (consulta_id,), fetch=True, one=True)
            
            if existing_diagnostic:
                # Atualizar diagnóstico existente
                result = execute_query("""
                    UPDATE diagnostico 
                    SET tipo_exame = %s,
                        descricao = %s,
                        observacoes = %s,
                        resultado = %s,
                        diagnostico_preliminar = %s,
                        status = %s,
                        imagem_path = %s,
                        imagem_base64 = %s,
                        formato_imagem = %s,
                        tamanho_imagem = %s,
                        atualizado_em = NOW()
                    WHERE consulta_id = %s
                """, (
                    tipo_exame,
                    descricao,
                    observacoes,
                    resultado,
                    diagnostico_ia,
                    status,
                    imagem_path,
                    imagem_base64,
                    formato_imagem,
                    tamanho_imagem,
                    consulta_id
                ), commit=True)
                
                if result is not None:
                    logger.info(f"Diagnóstico atualizado para consulta {consulta_id}")
                    return True
            else:
                # Inserir novo diagnóstico
                result = execute_query("""
                    INSERT INTO diagnostico 
                    (consulta_id, tipo_exame, descricao, observacoes, resultado, 
                     diagnostico_preliminar, status, imagem_path, imagem_base64, 
                     formato_imagem, tamanho_imagem, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    consulta_id,
                    tipo_exame,
                    descricao,
                    observacoes,
                    resultado,
                    diagnostico_ia,
                    status,
                    imagem_path,
                    imagem_base64,
                    formato_imagem,
                    tamanho_imagem
                ), commit=True)
                
                if result:
                    logger.info(f"Novo diagnóstico criado para consulta {consulta_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao salvar diagnóstico: {e}")
            logger.error(traceback.format_exc())
            return False

    # ========== FUNÇÕES PARA ANÁLISE COM IA ==========
    
    def analisar_imagem_com_gemini(imagem_path, contexto_clinico):
        """Analisa imagem usando Gemini AI"""
        try:
            if not gemini_available:
                return None, "API Gemini não configurada"
            
            # Verificar se arquivo existe
            if not os.path.exists(imagem_path):
                return None, "Arquivo de imagem não encontrado"
            
            # Carregar imagem
            try:
                img = Image.open(imagem_path)
            except Exception as e:
                return None, f"Erro ao abrir imagem: {str(e)}"
            
            # Preparar prompt
            prompt = f"""
            Você é um analista médico especialista. Analise esta imagem médica e forneça um diagnóstico detalhado.

            CONTEXTO CLÍNICO:
            {contexto_clinico}

            Por favor, forneça um relatório estruturado com:
            1. Descrição da imagem e qualidade técnica
            2. Achados principais
            3. Diagnóstico sugerido
            4. Recomendações
            5. Nível de urgência (baixa, média, alta, emergência)

            Use linguagem médica apropriada mas clara. Seja objetivo e baseie-se apenas na imagem fornecida.
            """
            
            try:
                # Configurar modelo Gemini
                if not MODEL_NAME:
                    model_name = "gemini-1.5-pro-vision"  # Modelo específico para visão
                else:
                    model_name = MODEL_NAME
                
                # Inicializar o modelo
                model = genai.GenerativeModel(model_name)
                
                # Carregar a imagem
                img_data = Image.open(imagem_path)
                
                # Gerar conteúdo
                response = model.generate_content([prompt, img_data])
                
                # Extrair o texto da resposta
                if response and hasattr(response, 'text'):
                    resultado = response.text
                else:
                    resultado = "Não foi possível gerar um diagnóstico."
                
                return resultado, None
                
            except Exception as e:
                logger.error(f"Erro ao chamar Gemini: {e}")
                logger.error(traceback.format_exc())
                return None, f"Erro na API Gemini: {str(e)}"
                
        except Exception as e:
            logger.error(f"Erro geral na análise: {e}")
            logger.error(traceback.format_exc())
            return None, f"Erro interno: {str(e)}"
    
    def salvar_imagem_temporaria(file):
        """Salva imagem temporariamente para análise"""
        try:
            # Criar diretório temporário se não existir
            temp_dir = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Gerar nome único
            filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            filepath = os.path.join(temp_dir, filename)
            
            # Salvar arquivo
            file.save(filepath)
            
            return filepath
        except Exception as e:
            logger.error(f"Erro ao salvar imagem: {e}")
            return None
    
    def preparar_contexto_clinico(pedido_info, observacoes_analista=''):
        """Prepara contexto clínico para análise"""
        try:
            if not pedido_info:
                return "Informações do pedido não disponíveis."
            
            # Extrair informações do pedido
            tipo_exame = pedido_info[1] or 'Não especificado'
            descricao = pedido_info[2] or 'Não informada'
            observacoes = pedido_info[3] or 'Nenhuma'
            urgencia = pedido_info[4] or 'normal'
            paciente_nome = pedido_info[12] or 'Não informado'
            data_nascimento = pedido_info[13]
            genero = pedido_info[14] or ''
            
            # Calcular idade
            idade = calcular_idade(data_nascimento)
            
            # Preparar contexto
            contexto = f"""
            INFORMAÇÕES DO PACIENTE:
            - Nome: {paciente_nome}
            - Idade: {idade}
            - Gênero: {genero}
            - Tipo de exame: {tipo_exame}
            - Urgência: {urgencia.upper()}
            
            DESCRIÇÃO DO EXAME:
            {descricao}
            
            OBSERVAÇÕES MÉDICAS:
            {observacoes}
            
            OBSERVAÇÕES DO ANALISTA:
            {observacoes_analista or 'Nenhuma'}
            """
            
            return contexto
            
        except Exception as e:
            logger.error(f"Erro ao preparar contexto: {e}")
            return "Erro ao preparar contexto clínico."

    # ========== ROTA: DASHBOARD ==========
    @analista_bp.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista"""
        try:
            user_id = session.get('user_id')
            
            # Buscar informações do analista
            analista_info = execute_query("""
                SELECT a.id, u.nome, a.especialidade 
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            session['analista_id'] = analista_id
            session['user_name'] = analista_info[1]
            session['analista_especialidade'] = analista_info[2]
            
            # Obter estatísticas
            estatisticas = {
                'pendentes': 0,
                'em_analise': 0,
                'concluidos': 0,
                'urgentes': 0
            }
            
            # Pedidos pendentes
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result and result[0] else 0
            
            # Pedidos em análise
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result and result[0] else 0
            
            # Pedidos concluídos
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result and result[0] else 0
            
            # Pedidos urgentes
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result and result[0] else 0
            
            # Pedidos recentes
            pedidos_recentes = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    u.nome as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.analista_id = %s
                AND pa.status IN ('pendente', 'em_analise', 'concluido')
                ORDER BY 
                    CASE 
                        WHEN pa.status = 'pendente' THEN 1
                        WHEN pa.status = 'em_analise' THEN 2
                        WHEN pa.status = 'concluido' THEN 3
                        ELSE 4
                    END,
                    pa.data_solicitacao DESC
                LIMIT 5
            """, (analista_id,), fetch=True)
            
            pedidos_list = []
            if pedidos_recentes:
                for pedido in pedidos_recentes:
                    pedidos_list.append({
                        'id': pedido[0],
                        'tipo_exame': pedido[1],
                        'urgencia': pedido[2],
                        'status': pedido[3],
                        'data_solicitacao': formatar_data(pedido[4]),
                        'paciente_nome': pedido[5] or 'Não informado'
                    })
            
            return render_template('analista/dashboard.html',
                                 user=session,
                                 estatisticas=estatisticas,
                                 pedidos_atribuidos=pedidos_list)
            
        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            flash('Erro ao carregar dashboard.', 'danger')
            return render_template('analista/dashboard.html',
                                 user=session,
                                 estatisticas={'pendentes': 0, 'em_analise': 0, 'concluidos': 0, 'urgentes': 0},
                                 pedidos_atribuidos=[])
    
    # ========== ROTA: API PARA ESTATÍSTICAS DO DASHBOARD ==========
    @analista_bp.route('/api/dashboard-stats')
    @analista_required
    def api_dashboard_stats():
        """API para obter estatísticas do dashboard em JSON"""
        try:
            user_id = session.get('user_id')
            
            # Buscar ID do analista
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_info[0]
            
            # Obter estatísticas
            estatisticas = {
                'pendentes': 0,
                'em_analise': 0,
                'concluidos': 0,
                'urgentes': 0,
                'total': 0
            }
            
            # Pedidos pendentes
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result and result[0] else 0
            
            # Pedidos em análise
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result and result[0] else 0
            
            # Pedidos concluídos
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result and result[0] else 0
            
            # Pedidos urgentes
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result and result[0] else 0
            
            # Total
            estatisticas['total'] = estatisticas['pendentes'] + estatisticas['em_analise'] + estatisticas['concluidos']
            
            # Pedidos recentes
            pedidos_recentes = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    u.nome as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.analista_id = %s
                AND pa.status IN ('pendente', 'em_analise', 'concluido')
                ORDER BY 
                    CASE 
                        WHEN pa.status = 'pendente' THEN 1
                        WHEN pa.status = 'em_analise' THEN 2
                        WHEN pa.status = 'concluido' THEN 3
                        ELSE 4
                    END,
                    pa.data_solicitacao DESC
                LIMIT 5
            """, (analista_id,), fetch=True)
            
            pedidos_list = []
            if pedidos_recentes:
                for pedido in pedidos_recentes:
                    pedidos_list.append({
                        'id': pedido[0],
                        'tipo_exame': pedido[1],
                        'urgencia': pedido[2],
                        'status': pedido[3],
                        'data_solicitacao': formatar_data(pedido[4]),
                        'paciente_nome': pedido[5] or 'Não informado'
                    })
            
            return jsonify({
                'success': True,
                'estatisticas': estatisticas,
                'pedidos_recentes': pedidos_list,
                'analista_id': analista_id
            })
            
        except Exception as e:
            logger.error(f"Erro na API de estatísticas: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'estatisticas': {
                    'pendentes': 0,
                    'em_analise': 0,
                    'concluidos': 0,
                    'urgentes': 0,
                    'total': 0
                },
                'pedidos_recentes': []
            }), 500
    
    # ========== ROTA: STATUS GEMINI ==========
    @analista_bp.route('/api/gemini-status')
    @analista_required
    def api_gemini_status():
        """API para verificar status do Gemini"""
        try:
            return jsonify({
                'success': True,
                'gemini_available': gemini_available,
                'model_name': MODEL_NAME or 'Nenhum',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'gemini_available': False,
                'error': str(e),
                'model_name': None
            }), 500
    
    # ========== ROTA: ANÁLISE DE IMAGEM COM IA ==========
    @analista_bp.route('/api/analisar_imagem/<int:pedido_id>', methods=['POST'])
    @analista_required
    def api_analisar_imagem(pedido_id):
        """API para analisar imagem com IA - ATUALIZADA: MARCA COMO CONCLUÍDO AUTOMATICAMENTE"""
        try:
            # Verificar se o pedido existe e pertence ao analista
            user_id = session.get('user_id')
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'success': False, 'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_info[0]
            
            # Verificar permissão no pedido
            pedido = execute_query("""
                SELECT id, analista_id, status FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'success': False, 'error': 'Pedido não encontrado'}), 404
            
            if pedido[1] != analista_id and pedido[2] != 'pendente':
                return jsonify({'success': False, 'error': 'Acesso negado a este pedido'}), 403
            
            # Verificar se há arquivo
            if 'imagem' not in request.files:
                return jsonify({'success': False, 'error': 'Nenhuma imagem enviada'}), 400
            
            file = request.files['imagem']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
            
            # Verificar extensão
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff', 'tif'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return jsonify({
                    'success': False, 
                    'error': 'Formato não suportado. Use: PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF'
                }), 400
            
            # Verificar tamanho (máx 10MB)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            file.seek(0)
            
            if file_length > 10 * 1024 * 1024:  # 10MB
                return jsonify({'success': False, 'error': 'Arquivo muito grande (máx 10MB)'}), 400
            
            # Obter dados do formulário
            tipo_analise = request.form.get('tipo_analise', 'completa')
            observacoes_analista = request.form.get('observacoes_analista', '')
            
            # Obter informações do paciente E DO PEDIDO
            paciente_info = execute_query("""
                SELECT 
                    u.nome,
                    p.data_nascimento,
                    p.genero,
                    pa.tipo_exame,
                    pa.descricao,
                    pa.observacoes,
                    pa.urgencia,
                    pa.consulta_id,
                    pa.medico_id,
                    pa.analista_id,
                    pa.status
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if paciente_info:
                paciente_nome, data_nascimento, genero, tipo_exame, descricao, observacoes, urgencia, consulta_id, medico_id, pedido_analista_id, pedido_status = paciente_info
                idade = calcular_idade(data_nascimento)
            else:
                paciente_nome = "Não informado"
                idade = ""
                genero = ""
                tipo_exame = "Não especificado"
                descricao = ""
                observacoes = ""
                urgencia = "normal"
                consulta_id = None
                medico_id = None
                pedido_analista_id = None
                pedido_status = 'pendente'
            
            # Se o pedido não tem analista, atribuir ao analista atual
            if not pedido_analista_id or pedido_analista_id == 0:
                execute_query("""
                    UPDATE pedidos_analise 
                    SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                    WHERE id = %s
                """, (analista_id, pedido_id), commit=True)
                pedido_status = 'em_analise'
            
            # Preparar contexto clínico
            contexto_clinico = preparar_contexto_clinico([
                None, tipo_exame, descricao, observacoes, urgencia, 
                None, None, None, None, None, None, None,
                paciente_nome, data_nascimento, genero
            ], observacoes_analista)
            
            # Salvar imagem temporariamente
            temp_image_path = salvar_imagem_temporaria(file)
            if not temp_image_path:
                return jsonify({'success': False, 'error': 'Erro ao salvar imagem'}), 500
            
            # Analisar imagem com Gemini
            diagnostico, error = analisar_imagem_com_gemini(temp_image_path, contexto_clinico)
            
            # VARIÁVEL PARA ARMAZENAR O NOVO STATUS
            novo_status = pedido_status  # Começa com o status atual
            
            # Se o diagnóstico foi gerado com sucesso, ATUALIZAR STATUS DO PEDIDO PARA CONCLUÍDO AUTOMATICAMENTE
            if diagnostico and not error:
                # 1. Atualizar pedido_analise para concluído
                result = execute_query("""
                    UPDATE pedidos_analise 
                    SET resultado_analise = %s,
                        diagnostico_analista = %s,
                        recomendacoes_analista = 'Diagnóstico gerado automaticamente por IA. Verificar se necessário.',
                        status = 'concluido',
                        data_conclusao = NOW(),
                        atualizado_em = NOW()
                    WHERE id = %s
                """, (
                    diagnostico,
                    "Diagnóstico gerado por IA: " + diagnostico[:200] + ("..." if len(diagnostico) > 200 else ""),
                    pedido_id
                ), commit=True)
                
                if result is not None:
                    logger.info(f"✅ Pedido #{pedido_id} marcado como CONCLUÍDO após análise da IA")
                    novo_status = 'concluido'  # Atualizar status para concluído
                    
                    # 2. Salvar na tabela diagnostico
                    if consulta_id:
                        try:
                            # Ler imagem como base64 para salvar no banco
                            with open(temp_image_path, 'rb') as img_file:
                                imagem_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                        except Exception as e:
                            logger.error(f"Erro ao converter imagem para base64: {e}")
                            imagem_base64 = None
                        
                        salvar_diagnostico_ia(
                            consulta_id=consulta_id,
                            tipo_exame=tipo_exame,
                            descricao=descricao,
                            observacoes=observacoes,
                            resultado=diagnostico,
                            diagnostico_ia=diagnostico,
                            status='concluido',
                            imagem_path=temp_image_path,
                            imagem_base64=imagem_base64,
                            formato_imagem=file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else None,
                            tamanho_imagem=file_length
                        )
                    
                    # 3. Criar notificação para o médico
                    if medico_id:
                        titulo_notificacao = f"Diagnóstico gerado por IA - {tipo_exame or 'Exame'}"
                        mensagem_notificacao = f"""
                        O diagnóstico do exame {tipo_exame or ''} do paciente {paciente_nome or ''} foi gerado automaticamente pela IA (Gemini).
                        
                        **Status:** EXAME CONCLUÍDO
                        **Diagnóstico preliminar:** {diagnostico[:150]}...
                        
                        Acesse sua área médica para ver o diagnóstico completo.
                        """
                        
                        criar_notificacao_medico(
                            medico_id=medico_id,
                            pedido_id=pedido_id,
                            titulo=titulo_notificacao,
                            mensagem=mensagem_notificacao,
                            tipo='diagnostico_ia'
                        )
            else:
                # Se houve erro, manter status atual
                novo_status = pedido_status
        
            # Limpar imagem temporária
            try:
                os.remove(temp_image_path)
            except:
                pass
            
            if error:
                return jsonify({
                    'success': False,
                    'error': error,
                    'diagnostico': None,
                    'warning': 'API Gemini com problemas. Use análise manual.',
                    'pedido_status': novo_status  # Retornar status atualizado
                }), 500
            
            # Retornar resultado com status atualizado
            return jsonify({
                'success': True,
                'diagnostico': diagnostico,
                'contexto': contexto_clinico,
                'tipo_analise': tipo_analise,
                'paciente': paciente_nome,
                'consulta_id': consulta_id,
                'timestamp': datetime.now().isoformat(),
                'pedido_status': novo_status,  # Incluir novo status na resposta
                'status_message': '✅ EXAME CONCLUÍDO - Diagnóstico gerado automaticamente por IA' if novo_status == 'concluido' else 'Análise em andamento'
            })
            
        except Exception as e:
            logger.error(f"Erro na análise de imagem: {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f'Erro interno: {str(e)}',
                'diagnostico': None,
                'warning': 'Erro no servidor. Verifique os logs.',
                'pedido_status': pedido_status if 'pedido_status' in locals() else 'em_analise'
            }), 500
    
    # ========== ROTA: DOWNLOAD ANEXO ==========
    @analista_bp.route('/pedidos/<int:pedido_id>/anexo/<filename>')
    @analista_required
    def download_anexo(pedido_id, filename):
        """Download de anexo do pedido"""
        try:
            # Verificar permissão
            user_id = session.get('user_id')
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_info[0]
            
            # Verificar se pedido pertence ao analista
            pedido = execute_query("""
                SELECT analista_id FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido or (pedido[0] != analista_id and pedido[0] is not None):
                return jsonify({'error': 'Acesso negado'}), 403
            
            # Buscar informações do anexo
            anexo = execute_query("""
                SELECT filename, original_name, tipo 
                FROM anexos_pedidos 
                WHERE pedido_id = %s AND filename = %s
            """, (pedido_id, filename), fetch=True, one=True)
            
            if not anexo:
                return jsonify({'error': 'Anexo não encontrado'}), 404
            
            # Caminho do arquivo
            upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
            filepath = os.path.join(upload_folder, 'pedidos', filename)
            
            if not os.path.exists(filepath):
                return jsonify({'error': 'Arquivo não encontrado no servidor'}), 404
            
            return send_file(
                filepath,
                as_attachment=True,
                download_name=anexo[1] or filename,
                mimetype=anexo[2] or 'application/octet-stream'
            )
            
        except Exception as e:
            logger.error(f"Erro no download do anexo: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA: PEDIDOS ==========
    @analista_bp.route('/pedidos')
    @analista_required
    def pedidos():
        """Lista todos os pedidos do analista"""
        try:
            user_id = session.get('user_id')
            
            # Buscar ID do analista
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            session['analista_id'] = analista_id
            
            # Filtros
            status_filter = request.args.get('status', '')
            urgencia_filter = request.args.get('urgencia', '')
            
            # Query base
            query = """
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.descricao,
                    pa.observacoes,
                    u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    m_u.nome as medico_nome,
                    m.especialidade as medico_especialidade
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.analista_id = %s OR pa.analista_id IS NULL
            """
            
            params = [analista_id]
            
            # Adicionar filtros
            conditions = []
            if status_filter:
                conditions.append("pa.status = %s")
                params.append(status_filter)
            
            if urgencia_filter:
                conditions.append("pa.urgencia = %s")
                params.append(urgencia_filter)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " ORDER BY pa.data_solicitacao DESC"
            
            # Executar query
            pedidos_db = execute_query(query, params, fetch=True)
            
            pedidos_list = []
            if pedidos_db:
                for pedido in pedidos_db:
                    idade = calcular_idade(pedido[9]) if pedido[9] else ''
                    
                    pedidos_list.append({
                        'id': pedido[0],
                        'tipo_exame': pedido[1] or '',
                        'urgencia': pedido[2] or 'normal',
                        'status': pedido[3] or 'pendente',
                        'data_solicitacao': formatar_data(pedido[4]),
                        'data_conclusao': formatar_data(pedido[5]),
                        'descricao': pedido[6] or '',
                        'observacoes': pedido[7] or '',
                        'paciente_nome': pedido[8] or 'Não informado',
                        'paciente_data_nascimento': formatar_data(pedido[9], '%d/%m/%Y') if pedido[9] else '',
                        'paciente_idade': idade,
                        'paciente_genero': pedido[10] or '',
                        'medico_nome': pedido[11] or 'Não informado',
                        'medico_especialidade': pedido[12] or ''
                    })
            
            return render_template('analista/pedidos.html',
                                 user=session,
                                 pedidos=pedidos_list,
                                 status_filter=status_filter,
                                 urgencia_filter=urgencia_filter)
            
        except Exception as e:
            logger.error(f"Erro ao listar pedidos: {e}")
            flash('Erro ao carregar pedidos.', 'danger')
            return render_template('analista/pedidos.html',
                                 user=session,
                                 pedidos=[])
    
    # ========== ROTA: ANALISAR PEDIDO - VERSÃO COMPLETA ==========
    @analista_bp.route('/analisar/<int:pedido_id>', methods=['GET', 'POST'])
    @analista_required
    def analisar_pedido(pedido_id):
        """Analisar um pedido específico"""
        try:
            user_id = session.get('user_id')
            
            # Buscar ID do analista
            analista_info = execute_query("""
                SELECT a.id, u.nome FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            session['analista_id'] = analista_id
            session['user_name'] = analista_info[1]
            
            # Buscar informações COMPLETAS do pedido
            pedido_info = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.descricao,
                    pa.observacoes,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.observacoes_medico,
                    u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    m_u.nome as medico_nome,
                    m.especialidade as medico_especialidade,
                    m.crm as medico_crm,
                    m.id as medico_id,  -- IMPORTANTE: ID do médico
                    pa.consulta_id,
                    c.data_hora as consulta_data,
                    c.observacoes as consulta_observacoes
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                LEFT JOIN consultas c ON pa.consulta_id = c.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_info:
                flash(f'Pedido #{pedido_id} não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            # Extrair informações importantes
            medico_id = pedido_info[17]  # ID do médico
            consulta_id = pedido_info[18]  # ID da consulta
            
            # Calcular idade
            idade_paciente = calcular_idade(pedido_info[13])
            
            # Preparar dados do pedido
            pedido = {
                'id': pedido_info[0],
                'tipo_exame': pedido_info[1] or '',
                'descricao': pedido_info[2] or '',
                'observacoes': pedido_info[3] or '',
                'urgencia': pedido_info[4] or 'normal',
                'status': pedido_info[5] or 'pendente',
                'data_solicitacao': formatar_data(pedido_info[6]),
                'data_conclusao': formatar_data(pedido_info[7]),
                'resultado_analise': pedido_info[8] or '',
                'diagnostico_analista': pedido_info[9] or '',
                'recomendacoes_analista': pedido_info[10] or '',
                'observacoes_medico': pedido_info[11] or '',
                'paciente_nome': pedido_info[12] or 'Não informado',
                'paciente_data_nascimento': formatar_data(pedido_info[13], '%d/%m/%Y') if pedido_info[13] else '',
                'paciente_idade': idade_paciente,
                'paciente_genero': pedido_info[14] or '',
                'medico_nome': pedido_info[15] or 'Não informado',
                'medico_especialidade': pedido_info[16] or '',
                'medico_crm': pedido_info[17] or '',
                'medico_id': medico_id,
                'consulta_id': consulta_id,
                'consulta_data': formatar_data(pedido_info[19]),
                'consulta_observacoes': pedido_info[20] or ''
            }
            
            # Se o pedido não tem analista_id, atribuir ao analista atual
            pedido_owner = execute_query("""
                SELECT analista_id FROM pedidos_analise WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if pedido_owner and (not pedido_owner[0] or pedido_owner[0] == 0):
                execute_query("""
                    UPDATE pedidos_analise 
                    SET analista_id = %s 
                    WHERE id = %s
                """, (analista_id, pedido_id), commit=True)
            
            # Buscar anexos
            anexos = execute_query("""
                SELECT id, filename, original_name, tipo, size, upload_date
                FROM anexos_pedidos 
                WHERE pedido_id = %s
                ORDER BY upload_date DESC
            """, (pedido_id,), fetch=True)
            
            anexos_list = []
            if anexos:
                for anexo in anexos:
                    anexos_list.append({
                        'id': anexo[0],
                        'filename': anexo[1],
                        'original_name': anexo[2],
                        'type': anexo[3],
                        'size': anexo[4],
                        'upload_date': formatar_data(anexo[5])
                    })
            
            # Buscar diagnósticos anteriores do paciente
            diagnosticos_anteriores = []
            if pedido_info[12]:  # Se tem paciente_nome
                diagnosticos_db = execute_query("""
                    SELECT 
                        d.diagnostico_final,
                        d.criado_em,
                        m_u.nome as medico_nome,
                        m.especialidade
                    FROM diagnostico d
                    JOIN consultas c ON d.consulta_id = c.id
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE u.nome = %s AND d.diagnostico_final IS NOT NULL
                    ORDER BY d.criado_em DESC
                    LIMIT 5
                """, (pedido_info[12],), fetch=True)
                
                if diagnosticos_db:
                    for diag in diagnosticos_db:
                        diagnosticos_anteriores.append({
                            'diagnostico': diag[0],
                            'data_consulta': formatar_data(diag[1]),
                            'medico_nome': diag[2],
                            'medico_especialidade': diag[3]
                        })
            
            # Se for POST, processar a análise
            if request.method == 'POST':
                acao = request.form.get('acao', '')
                
                if acao == 'iniciar_analise':
                    # Iniciar análise
                    result = execute_query("""
                        UPDATE pedidos_analise 
                        SET status = 'em_analise', atualizado_em = NOW()
                        WHERE id = %s
                    """, (pedido_id,), commit=True)
                    
                    if result is not None:
                        flash('Análise iniciada com sucesso!', 'success')
                        pedido['status'] = 'em_analise'
                
                elif acao == 'concluir':
                    # Concluir análise
                    resultado_analise = request.form.get('resultado_analise', '').strip()
                    diagnostico_analista = request.form.get('diagnostico_analista', '').strip()
                    recomendacoes_analista = request.form.get('recomendacoes_analista', '').strip()
                    
                    if not resultado_analise or not diagnostico_analista:
                        flash('Resultado e diagnóstico são obrigatórios.', 'warning')
                    else:
                        # Atualizar pedido_analise
                        result = execute_query("""
                            UPDATE pedidos_analise 
                            SET resultado_analise = %s,
                                diagnostico_analista = %s,
                                recomendacoes_analista = %s,
                                status = 'concluido',
                                data_conclusao = NOW(),
                                atualizado_em = NOW()
                            WHERE id = %s
                        """, (
                            resultado_analise,
                            diagnostico_analista,
                            recomendacoes_analista,
                            pedido_id
                        ), commit=True)
                        
                        if result is not None:
                            # SALVAR NA TABELA DIAGNOSTICO
                            if consulta_id:
                                salvar_diagnostico_ia(
                                    consulta_id=consulta_id,
                                    tipo_exame=pedido_info[1] or '',
                                    descricao=pedido_info[2] or '',
                                    observacoes=pedido_info[3] or '',
                                    resultado=resultado_analise,
                                    diagnostico_ia=diagnostico_analista,  # Usar diagnóstico do analista
                                    status='concluido'  # Status como concluído
                                )
                            
                            # CRIAR NOTIFICAÇÃO PARA O MÉDICO
                            if medico_id:
                                titulo_notificacao = f"Diagnóstico disponível - {pedido_info[1] or 'Exame'}"
                                mensagem_notificacao = f"""
                                O diagnóstico do exame {pedido_info[1] or ''} do paciente {pedido_info[12] or ''} está disponível.
                                
                                Resultado: {resultado_analise[:100]}...
                                
                                Acesse sua área médica para ver o diagnóstico completo.
                                """
                                
                                criar_notificacao_medico(
                                    medico_id=medico_id,
                                    pedido_id=pedido_id,
                                    titulo=titulo_notificacao,
                                    mensagem=mensagem_notificacao,
                                    tipo='diagnostico'
                                )
                            
                            flash('Análise concluída com sucesso! O médico foi notificado.', 'success')
                            return redirect(url_for('analista.pedidos'))
                        else:
                            flash('Erro ao salvar análise.', 'danger')
            
            return render_template('analista/analisar_exame.html',
                                 user=session,
                                 pedido=pedido,
                                 anexos_pedido=anexos_list,
                                 diagnosticos_anteriores=diagnosticos_anteriores,
                                 gemini_available=gemini_available,
                                 MODEL_NAME=MODEL_NAME,
                                 now=datetime.now())
            
        except Exception as e:
            logger.error(f"Erro ao analisar pedido {pedido_id}: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedido para análise.', 'danger')
            return redirect(url_for('analista.pedidos'))
    
    # ========== ROTA: PRÓXIMO PEDIDO ==========
    @analista_bp.route('/proximo-pedido')
    @analista_required
    def proximo_pedido():
        """Atribuir próximo pedido pendente ao analista"""
        try:
            user_id = session.get('user_id')
            
            # Buscar ID do analista
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            
            # Buscar próximo pedido sem analista
            pedido = execute_query("""
                SELECT id FROM pedidos_analise 
                WHERE (analista_id IS NULL OR analista_id = 0)
                AND status = 'pendente'
                ORDER BY 
                    CASE urgencia 
                        WHEN 'urgente' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    data_solicitacao ASC
                LIMIT 1
            """, fetch=True, one=True)
            
            if not pedido:
                flash('Não há pedidos pendentes disponíveis.', 'info')
                return redirect(url_for('analista.dashboard'))
            
            pedido_id = pedido[0]
            
            # Atribuir pedido
            result = execute_query("""
                UPDATE pedidos_analise 
                SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                WHERE id = %s
            """, (analista_id, pedido_id), commit=True)
            
            if result is not None:
                flash(f'Pedido #{pedido_id} atribuído a você!', 'success')
                return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            else:
                flash('Erro ao atribuir pedido.', 'danger')
                return redirect(url_for('analista.dashboard'))
            
        except Exception as e:
            logger.error(f"Erro ao buscar próximo pedido: {e}")
            flash('Erro ao buscar próximo pedido.', 'danger')
            return redirect(url_for('analista.dashboard'))
    
    # ========== ROTA: MINHAS ANÁLISES ==========
    @analista_bp.route('/minhas-analises')
    @analista_required
    def minhas_analises():
        """Histórico de análises do analista"""
        try:
            user_id = session.get('user_id')
            
            # Buscar ID do analista
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            
            # Buscar análises concluídas
            analises = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.urgencia,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    u.nome as paciente_nome,
                    m_u.nome as medico_nome,
                    pa.diagnostico_analista
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.analista_id = %s
                AND pa.status = 'concluido'
                ORDER BY pa.data_conclusao DESC
                LIMIT 20
            """, (analista_id,), fetch=True)
            
            analises_list = []
            if analises:
                for analise in analises:
                    analises_list.append({
                        'id': analise[0],
                        'tipo_exame': analise[1],
                        'status': analise[2],
                        'urgencia': analise[3],
                        'data_solicitacao': formatar_data(analise[4]),
                        'data_conclusao': formatar_data(analise[5]),
                        'paciente_nome': analise[6] or 'Não informado',
                        'medico_nome': analise[7] or 'Não informado',
                        'diagnostico_analista': analise[8] or ''
                    })
            
            return render_template('analista/minhas_analises.html',
                                 user=session,
                                 analises=analises_list)
            
        except Exception as e:
            logger.error(f"Erro ao carregar histórico: {e}")
            flash('Erro ao carregar histórico.', 'danger')
            return redirect(url_for('analista.dashboard'))
    
    # ========== ROTA: PERFIL ==========
    @analista_bp.route('/perfil')
    @analista_required
    def perfil():
        """Perfil do analista"""
        try:
            user_id = session.get('user_id')
            
            # Buscar informações do analista
            analista_info = execute_query("""
                SELECT 
                    a.*,
                    u.nome,
                    u.email,
                    u.telefone,
                    u.endereco,
                    u.data_cadastro
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Informações do analista não encontradas.', 'danger')
                return redirect(url_for('analista.dashboard'))
            
            analista_dict = {
                'id': analista_info[0],
                'usuario_id': analista_info[1],
                'especialidade': analista_info[2],
                'registro_profissional': analista_info[3],
                'telefone': analista_info[4],
                'is_supervisor': analista_info[5],
                'status': analista_info[6],
                'experiencia': analista_info[7],
                'carga_horaria_semanal': analista_info[8],
                'data_contratacao': analista_info[9],
                'data_desligamento': analista_info[10],
                'criado_em': analista_info[11],
                'atualizado_em': analista_info[12],
                'nome': analista_info[13],
                'email': analista_info[14],
                'telefone_usuario': analista_info[15],
                'endereco': analista_info[16],
                'data_cadastro': analista_info[17]
            }
            
            return render_template('analista/perfil.html',
                                 user=session,
                                 analista=analista_dict)
            
        except Exception as e:
            logger.error(f"Erro ao carregar perfil: {e}")
            flash('Erro ao carregar perfil.', 'danger')
            return redirect(url_for('analista.dashboard'))
    
    # ========== ROTA: CONFIGURAÇÕES ==========
    @analista_bp.route('/configuracoes')
    @analista_required
    def configuracoes():
        """Página de configurações do analista"""
        try:
            return render_template('analista/configuracoes.html',
                                 user=session,
                                 gemini_available=gemini_available,
                                 MODEL_NAME=MODEL_NAME)
            
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            flash('Erro ao carregar configurações.', 'danger')
            return redirect(url_for('analista.dashboard'))
    
    # ========== ROTA: HISTÓRICO (ALIAS) ==========
    @analista_bp.route('/historico')
    @analista_required
    def historico():
        """Alias para minhas_analises para compatibilidade"""
        return redirect(url_for('analista.minhas_analises'))
    
    return analista_bp