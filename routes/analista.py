# routes/analista/__init__.py - VERSÃO CORRIGIDA
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
    """Inicializa o blueprint do analista - VERSÃO COMPLETA CORRIGIDA"""
    
    analista_bp = Blueprint('analista', __name__, url_prefix='/analista')
    
    def execute_query(query, params=None, fetch=False, commit=True, one=False):
        """Executa consulta SQL - USANDO A CONEXÃO DO MYSQL PASSADA"""
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
            if not consulta_id:
                logger.warning("consulta_id é None, não é possível salvar diagnóstico")
                return False
            
            existing_diagnostic = execute_query("""
                SELECT id FROM diagnostico WHERE consulta_id = %s
            """, (consulta_id,), fetch=True, one=True)
            
            if existing_diagnostic:
                diagnostico_id = existing_diagnostic[0] if isinstance(existing_diagnostic, (list, tuple)) else existing_diagnostic.get('id')
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
                    WHERE id = %s
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
                    diagnostico_id
                ), commit=True)
                
                if result is not None:
                    logger.info(f"Diagnóstico atualizado para consulta {consulta_id}")
                    return True
            else:
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
            if not gemini_available or not client:
                return None, "API Gemini não configurada"
            
            if not os.path.exists(imagem_path):
                return None, "Arquivo de imagem não encontrado"
            
            try:
                img = Image.open(imagem_path)
            except Exception as e:
                return None, f"Erro ao abrir imagem: {str(e)}"
            
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
                # Usar o modelo correto
                model_name = MODEL_NAME if MODEL_NAME else "gemini-1.5-pro"
                
                # Inicializar o modelo
                model = genai.GenerativeModel(model_name)
                
                # Gerar conteúdo
                response = model.generate_content([prompt, img])
                
                if response and hasattr(response, 'text'):
                    resultado = response.text
                else:
                    resultado = "Não foi possível gerar um diagnóstico."
                
                return resultado, None
                
            except Exception as e:
                logger.error(f"Erro ao chamar Gemini: {e}")
                return None, f"Erro na API Gemini: {str(e)}"
                
        except Exception as e:
            logger.error(f"Erro geral na análise: {e}")
            return None, f"Erro interno: {str(e)}"
    
    def salvar_imagem_temporaria(file):
        """Salva imagem temporariamente para análise"""
        try:
            upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
            temp_dir = os.path.join(upload_folder, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            filepath = os.path.join(temp_dir, filename)
            
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
            
            tipo_exame = pedido_info[1] if len(pedido_info) > 1 else 'Não especificado'
            descricao = pedido_info[2] if len(pedido_info) > 2 else 'Não informada'
            observacoes = pedido_info[3] if len(pedido_info) > 3 else 'Nenhuma'
            urgencia = pedido_info[4] if len(pedido_info) > 4 else 'normal'
            paciente_nome = pedido_info[12] if len(pedido_info) > 12 else 'Não informado'
            data_nascimento = pedido_info[13] if len(pedido_info) > 13 else None
            genero = pedido_info[14] if len(pedido_info) > 14 else ''
            
            idade = calcular_idade(data_nascimento)
            
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

    # ========== ROTA: ANÁLISE MANUAL ==========
    @analista_bp.route('/analise_manual/<int:pedido_id>')
    @analista_required
    def analise_manual(pedido_id):
        """Página de análise manual do pedido"""
        try:
            if pedido_id == 0:
                flash('Por favor, selecione um pedido primeiro.', 'warning')
                return redirect(url_for('analista.pedidos'))
            
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"Erro no redirecionamento: {e}")
            flash('Erro ao redirecionar para análise manual.', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA: DASHBOARD ==========
    @analista_bp.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id, u.nome, a.especialidade 
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0] if isinstance(analista_info, (list, tuple)) else analista_info.get('id')
            session['analista_id'] = analista_id
            session['user_name'] = analista_info[1] if isinstance(analista_info, (list, tuple)) else analista_info.get('nome')
            session['analista_especialidade'] = analista_info[2] if isinstance(analista_info, (list, tuple)) else analista_info.get('especialidade')
            
            estatisticas = {
                'pendentes': 0, 'em_analise': 0, 'concluidos': 0, 'urgentes': 0
            }
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result else 0
            
            pedidos_recentes = execute_query("""
                SELECT 
                    pa.id, pa.tipo_exame, pa.urgencia, pa.status, pa.data_solicitacao,
                    COALESCE(u.nome, 'Confidencial') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.analista_id = %s OR pa.analista_id IS NULL
                ORDER BY 
                    CASE pa.status 
                        WHEN 'pendente' THEN 1
                        WHEN 'em_analise' THEN 2
                        ELSE 3
                    END,
                    pa.data_solicitacao DESC
                LIMIT 10
            """, (analista_id,), fetch=True)
            
            pedidos_list = []
            if pedidos_recentes:
                for p in pedidos_recentes:
                    pedidos_list.append({
                        'id': p[0],
                        'tipo_exame': p[1] or 'N/A',
                        'urgencia': p[2] or 'normal',
                        'status': p[3] or 'pendente',
                        'data_solicitacao': formatar_data(p[4]),
                        'paciente_nome': p[5] or 'Confidencial'
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
                                 estatisticas={'pendentes':0,'em_analise':0,'concluidos':0,'urgentes':0},
                                 pedidos_atribuidos=[])

    # ========== ROTA: API PARA ESTATÍSTICAS DO DASHBOARD ==========
    @analista_bp.route('/api/dashboard-stats')
    @analista_required
    def api_dashboard_stats():
        """API para obter estatísticas do dashboard em JSON"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_info[0] if isinstance(analista_info, (list, tuple)) else analista_info.get('id')
            
            estatisticas = {
                'pendentes': 0, 'em_analise': 0, 'concluidos': 0, 'urgentes': 0, 'total': 0
            }
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result else 0
            
            estatisticas['total'] = estatisticas['pendentes'] + estatisticas['em_analise'] + estatisticas['concluidos']
            
            return jsonify({'success': True, 'estatisticas': estatisticas})
            
        except Exception as e:
            logger.error(f"Erro na API de estatísticas: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return analista_bp
