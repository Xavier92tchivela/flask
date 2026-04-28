# routes/pedido_analise.py - VERSÃO COMPLETA CORRIGIDA
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime, date, timedelta
import json
import logging
import traceback
from werkzeug.utils import secure_filename
import os

logger = logging.getLogger(__name__)

def init_pedido_analise(mysql, app):
    """Inicializa o blueprint de pedidos de análise"""
    
    pedido_analise_bp = Blueprint('pedido_analise', __name__, url_prefix='/pedido-analise')
    
    # Configurações
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'analises')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'dcm', 'zip', 'rar'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Criar pasta de uploads se não existir
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # ===== FUNÇÃO PARA CONVERTER BYTES PARA STRING =====
    def converter_bytes_para_str(dados):
        """
        Converte recursivamente qualquer valor bytes para string
        Funciona com dicionários, listas, tuplas e valores simples
        """
        if dados is None:
            return None
        elif isinstance(dados, bytes):
            try:
                return dados.decode('utf-8')
            except:
                return str(dados)
        elif isinstance(dados, dict):
            return {converter_bytes_para_str(chave): converter_bytes_para_str(valor) 
                    for chave, valor in dados.items()}
        elif isinstance(dados, (list, tuple)):
            return [converter_bytes_para_str(item) for item in dados]
        elif isinstance(dados, (int, float, bool)):
            return dados
        else:
            return dados

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
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
            
            # CONVERTER BYTES PARA STRING SE FOR FETCH
            if fetch and result:
                result = converter_bytes_para_str(result)
            
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
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data para exibição"""
        if not data:
            return ''
        try:
            if isinstance(data, datetime):
                return data.strftime(formato)
            elif isinstance(data, date):
                return data.strftime('%d/%m/%Y')
            elif isinstance(data, str):
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(data, fmt).strftime(formato)
                    except ValueError:
                        continue
                return data
            return str(data)
        except Exception as e:
            return str(data)
    
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    def calcular_idade(data_nascimento):
        """Calcula idade a partir da data de nascimento"""
        if not data_nascimento:
            return None
        try:
            if isinstance(data_nascimento, str):
                nascimento = datetime.strptime(data_nascimento[:10], '%Y-%m-%d').date()
            elif isinstance(data_nascimento, date):
                nascimento = data_nascimento
            elif isinstance(data_nascimento, datetime):
                nascimento = data_nascimento.date()
            else:
                return None
            
            hoje = date.today()
            idade = hoje.year - nascimento.year
            
            if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                idade -= 1
            
            return idade
        except Exception as e:
            return None
    
    # ===== FUNÇÃO AUXILIAR PARA EXTRAIR VALOR DE RESULTADO =====
    def extrair_valor_resultado(resultado, indice=0, chave=None, padrao=None):
        """
        Extrai valor de forma segura de um resultado que pode ser dict, tuple ou list
        """
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
    
    # ===== FUNÇÃO PARA BUSCAR SINAIS VITAIS =====
    def buscar_sinais_vitais(consulta_id):
        """Busca os sinais vitais de uma consulta"""
        if not consulta_id:
            return None
        
        try:
            sinais_query = """
                SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                       temperatura, saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
                FROM sinais_vitais
                WHERE consulta_id = %s
                ORDER BY data_afericao DESC
                LIMIT 1
            """
            sinais_data = execute_query(sinais_query, (consulta_id,), fetch=True, one=True)
            
            if not sinais_data:
                return None
            
            from routes.consulta import (
                classificar_pressao_arterial, classificar_frequencia_cardiaca,
                classificar_frequencia_respiratoria, classificar_temperatura,
                classificar_saturacao_oxigenio, classificar_glicemia
            )
            
            sinais_vitais = {
                'id': extrair_valor_resultado(sinais_data, 0, 'id'),
                'pressao_arterial': extrair_valor_resultado(sinais_data, 1, 'pressao_arterial'),
                'pa_classificacao': classificar_pressao_arterial(extrair_valor_resultado(sinais_data, 1, 'pressao_arterial')) if extrair_valor_resultado(sinais_data, 1, 'pressao_arterial') else None,
                'frequencia_cardiaca': extrair_valor_resultado(sinais_data, 2, 'frequencia_cardiaca'),
                'fc_classificacao': classificar_frequencia_cardiaca(extrair_valor_resultado(sinais_data, 2, 'frequencia_cardiaca')) if extrair_valor_resultado(sinais_data, 2, 'frequencia_cardiaca') else None,
                'frequencia_respiratoria': extrair_valor_resultado(sinais_data, 3, 'frequencia_respiratoria'),
                'fr_classificacao': classificar_frequencia_respiratoria(extrair_valor_resultado(sinais_data, 3, 'frequencia_respiratoria')) if extrair_valor_resultado(sinais_data, 3, 'frequencia_respiratoria') else None,
                'temperatura': float(extrair_valor_resultado(sinais_data, 4, 'temperatura')) if extrair_valor_resultado(sinais_data, 4, 'temperatura') else None,
                'temp_classificacao': classificar_temperatura(extrair_valor_resultado(sinais_data, 4, 'temperatura')) if extrair_valor_resultado(sinais_data, 4, 'temperatura') else None,
                'saturacao_oxigenio': extrair_valor_resultado(sinais_data, 5, 'saturacao_oxigenio'),
                'spo2_classificacao': classificar_saturacao_oxigenio(extrair_valor_resultado(sinais_data, 5, 'saturacao_oxigenio')) if extrair_valor_resultado(sinais_data, 5, 'saturacao_oxigenio') else None,
                'glicemia': extrair_valor_resultado(sinais_data, 6, 'glicemia'),
                'glicemia_classificacao': classificar_glicemia(extrair_valor_resultado(sinais_data, 6, 'glicemia')) if extrair_valor_resultado(sinais_data, 6, 'glicemia') else None,
                'peso': float(extrair_valor_resultado(sinais_data, 7, 'peso')) if extrair_valor_resultado(sinais_data, 7, 'peso') else None,
                'data_afericao': formatar_data(extrair_valor_resultado(sinais_data, 8, 'data_afericao'), '%d/%m/%Y %H:%M') if extrair_valor_resultado(sinais_data, 8, 'data_afericao') else '',
                'observacoes': extrair_valor_resultado(sinais_data, 9, 'observacoes') or ''
            }
            
            return sinais_vitais
            
        except Exception as e:
            logger.error(f"Erro ao buscar sinais vitais: {e}")
            return None
    
    # ==============================
    # ROTA: NOVO PEDIDO DE ANÁLISE
    # ==============================
    @pedido_analise_bp.route('/novo')
    @medico_required
    def novo_pedido():
        """Página para criar novo pedido de análise"""
        try:
            user_id = session['user_id']
            
            # Obter ID do médico - CORRIGIDO
            medico_result = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            
            if not medico_result:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # CORREÇÃO: Extrair medico_id de forma segura
            medico_id = extrair_valor_resultado(medico_result, 0, 'id')
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Buscar consultas recentes
            consultas = execute_query("""
                SELECT 
                    c.id,
                    c.data_hora,
                    c.status,
                    u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    p.id as paciente_id,
                    c.observacoes,
                    (SELECT COUNT(*) FROM sinais_vitais sv WHERE sv.consulta_id = c.id) as tem_sinais
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s 
                AND c.status IN ('realizada', 'agendada')
                ORDER BY c.data_hora DESC
                LIMIT 15
            """, (medico_id,), fetch=True)
            
            # BUSCAR ANALISTAS
            analistas_raw = execute_query("""
                SELECT 
                    a.id,
                    COALESCE(u.nome, CONCAT('Analista ', a.id)) as nome,
                    COALESCE(a.especialidade, 'Geral') as especialidade,
                    COALESCE(a.registro_profissional, '') as registro,
                    a.status,
                    COALESCE(a.telefone, '') as telefone,
                    COALESCE(a.is_supervisor, 0) as is_supervisor,
                    a.carga_horaria_semanal,
                    a.data_contratacao,
                    (SELECT COUNT(*) 
                     FROM pedidos_analise pa 
                     WHERE pa.analista_id = a.id 
                     AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                FROM analistas a
                LEFT JOIN usuarios u ON a.usuario_id = u.id
                WHERE a.status = 'ativo'
                ORDER BY nome
            """, fetch=True)
            
            # Converter analistas para lista de dicionários
            analistas = []
            if analistas_raw:
                for a in analistas_raw:
                    analista_dict = {
                        'id': extrair_valor_resultado(a, 0, 'id'),
                        'nome': str(extrair_valor_resultado(a, 1, 'nome')) if extrair_valor_resultado(a, 1, 'nome') else f'Analista {extrair_valor_resultado(a, 0, "id")}',
                        'especialidade': str(extrair_valor_resultado(a, 2, 'especialidade')) if extrair_valor_resultado(a, 2, 'especialidade') else 'Geral',
                        'registro': str(extrair_valor_resultado(a, 3, 'registro')) if extrair_valor_resultado(a, 3, 'registro') else '',
                        'status': str(extrair_valor_resultado(a, 4, 'status')) if extrair_valor_resultado(a, 4, 'status') else 'ativo',
                        'telefone': str(extrair_valor_resultado(a, 5, 'telefone')) if extrair_valor_resultado(a, 5, 'telefone') else '',
                        'is_supervisor': extrair_valor_resultado(a, 6, 'is_supervisor', 0),
                        'carga_horaria': extrair_valor_resultado(a, 7, 'carga_horaria_semanal', 40),
                        'data_contratacao': extrair_valor_resultado(a, 8, 'data_contratacao'),
                        'pedidos_ativos': extrair_valor_resultado(a, 9, 'pedidos_ativos', 0)
                    }
                    analistas.append(analista_dict)
            
            print(f"[DEBUG] Analistas encontrados: {len(analistas)}")
            
            # Tipos de exame
            tipos_exame = [
                'Biópsia', 'Exame de Sangue Completo', 'Hemograma', 'Glicemia',
                'Colesterol Total', 'Triglicerídeos', 'Urina Tipo 1', 'Urocultura',
                'Coprocultura', 'Parasitológico', 'Radiografia', 'Ultrassonografia',
                'Tomografia Computadorizada', 'Ressonância Magnética', 'Eletrocardiograma',
                'Endoscopia', 'Colonoscopia', 'Citologia', 'Histopatologia',
                'Imunohistoquímica', 'Biópsia de Pele', 'Biópsia de Mama',
                'Papanicolau', 'Exame Microbiológico', 'Teste Genético',
                'Marcador Tumoral', 'Outro'
            ]
            
            # Preparar consultas
            consultas_list = []
            if consultas:
                for c in consultas:
                    idade = calcular_idade(extrair_valor_resultado(c, 4, 'data_nascimento'))
                    consultas_list.append({
                        'id': extrair_valor_resultado(c, 0, 'id'),
                        'data_hora': formatar_data(extrair_valor_resultado(c, 1, 'data_hora')),
                        'status': extrair_valor_resultado(c, 2, 'status'),
                        'paciente_nome': extrair_valor_resultado(c, 3, 'paciente_nome') or 'Paciente',
                        'data_nascimento': formatar_data(extrair_valor_resultado(c, 4, 'data_nascimento'), '%d/%m/%Y') if extrair_valor_resultado(c, 4, 'data_nascimento') else '',
                        'idade': idade,
                        'genero': extrair_valor_resultado(c, 5, 'genero'),
                        'paciente_id': extrair_valor_resultado(c, 6, 'paciente_id'),
                        'observacoes': extrair_valor_resultado(c, 7, 'observacoes') or '',
                        'tem_sinais': extrair_valor_resultado(c, 8, 'tem_sinais', 0)
                    })
            
            # Consulta pré-selecionada
            consulta_id_param = request.args.get('consulta_id')
            consulta_selecionada = None
            sinais_consulta = None
            
            if consulta_id_param and consulta_id_param.isdigit():
                consulta_id_int = int(consulta_id_param)
                for consulta in consultas_list:
                    if consulta['id'] == consulta_id_int:
                        consulta_selecionada = consulta
                        sinais_consulta = buscar_sinais_vitais(consulta_id_int)
                        break
            
            return render_template('medico/novo_pedido_analise.html',
                                  consultas=consultas_list,
                                  analistas=analistas,
                                  tipos_exame=tipos_exame,
                                  consulta_selecionada=consulta_selecionada,
                                  sinais_consulta=sinais_consulta,
                                  formatar_data=formatar_data,
                                  calcular_idade=calcular_idade,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao carregar novo pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar dados.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ==============================
    # ROTA: CRIAR PEDIDO (PRINCIPAL)
    # ==============================
    @pedido_analise_bp.route('/criar', methods=['POST'])
    @medico_required
    def criar_pedido():
        """Criar um novo pedido de análise"""
        try:
            user_id = session['user_id']
            
            # Obter dados do formulário
            paciente_id = request.form.get('paciente_id')
            consulta_id = request.form.get('consulta_id') or None
            tipo_exame = request.form.get('tipo_exame')
            descricao = request.form.get('descricao')
            observacoes = request.form.get('observacoes', '')
            urgencia = request.form.get('urgencia', 'normal')
            analista_id = request.form.get('analista_id') or None
            incluir_sinais = request.form.get('incluir_sinais') == '1'
            
            # Se tipo_exame for "outro", usar o campo outro_exame
            outro_exame = request.form.get('outro_exame', '')
            if tipo_exame == 'outro' and outro_exame:
                tipo_exame = outro_exame
            
            # Validações
            if not paciente_id or not tipo_exame or not descricao.strip():
                flash('Preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('pedido_analise.novo_pedido'))
            
            # Obter ID do médico
            medico_result = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            
            if not medico_result:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            medico_id = extrair_valor_resultado(medico_result, 0, 'id')
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Buscar sinais vitais se solicitado
            observacoes_adicionais = observacoes
            if incluir_sinais and consulta_id:
                sinais = buscar_sinais_vitais(int(consulta_id))
                if sinais:
                    sinais_texto = f"""
SINAIS VITAIS DO PACIENTE:
• Pressão Arterial: {sinais.get('pressao_arterial', 'N/I')} ({sinais.get('pa_classificacao', 'N/I')})
• Frequência Cardíaca: {sinais.get('frequencia_cardiaca', 'N/I')} bpm ({sinais.get('fc_classificacao', 'N/I')})
• Frequência Respiratória: {sinais.get('frequencia_respiratoria', 'N/I')} rpm ({sinais.get('fr_classificacao', 'N/I')})
• Temperatura: {sinais.get('temperatura', 'N/I')} °C ({sinais.get('temp_classificacao', 'N/I')})
• Saturação O2: {sinais.get('saturacao_oxigenio', 'N/I')}% ({sinais.get('spo2_classificacao', 'N/I')})
• Glicemia: {sinais.get('glicemia', 'N/I')} mg/dL ({sinais.get('glicemia_classificacao', 'N/I')})
• Peso: {sinais.get('peso', 'N/I')} kg
Data da aferição: {sinais.get('data_afericao', 'N/I')}
"""
                    if sinais.get('observacoes'):
                        sinais_texto += f"Obs. dos sinais: {sinais.get('observacoes')}\n"
                    
                    observacoes_adicionais = observacoes + "\n\n" + sinais_texto
                    logger.info(f"Sinais vitais incluídos no pedido para consulta #{consulta_id}")
            
            # Processar analista
            analista_atribuido = None
            
            if analista_id and analista_id != 'auto':
                analista_check = execute_query(
                    "SELECT id FROM analistas WHERE id = %s AND status = 'ativo'",
                    (analista_id,), fetch=True, one=True
                )
                if analista_check:
                    analista_atribuido = extrair_valor_resultado(analista_check, 0, 'id')
            
            if not analista_atribuido:
                analista_auto = execute_query("""
                    SELECT 
                        a.id,
                        (SELECT COUNT(*) 
                         FROM pedidos_analise pa 
                         WHERE pa.analista_id = a.id 
                         AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                    FROM analistas a
                    WHERE a.status = 'ativo'
                    ORDER BY pedidos_ativos, a.id
                    LIMIT 1
                """, fetch=True, one=True)
                
                if analista_auto:
                    analista_atribuido = extrair_valor_resultado(analista_auto, 0, 'id')
                    print(f"[DEBUG] Analista atribuído automaticamente: ID {analista_atribuido}")
                else:
                    flash('Nenhum analista disponível no momento.', 'warning')
            
            # Processar anexos
            anexos_info = []
            if 'anexos[]' in request.files:
                files = request.files.getlist('anexos[]')
                for file in files:
                    if file and file.filename:
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)
                        
                        if file_size > MAX_FILE_SIZE:
                            flash(f'Arquivo {file.filename} excede 10MB.', 'warning')
                            continue
                        
                        if allowed_file(file.filename):
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = secure_filename(f"{timestamp}_{file.filename}")
                            file_path = os.path.join(UPLOAD_FOLDER, filename)
                            file.save(file_path)
                            
                            anexos_info.append({
                                'filename': filename,
                                'original_name': file.filename,
                                'path': f'/static/uploads/analises/{filename}',
                                'size': file_size,
                                'upload_time': datetime.now().isoformat()
                            })
                        else:
                            flash(f'Tipo de arquivo não permitido: {file.filename}', 'warning')
            
            anexos_json = json.dumps(anexos_info, ensure_ascii=False) if anexos_info else None
            
            pedido_id = execute_query("""
                INSERT INTO pedidos_analise 
                (consulta_id, medico_id, paciente_id, analista_id, tipo_exame, 
                 descricao, observacoes, urgencia, status, data_solicitacao,
                 status_aprovacao, anexos, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendente', NOW(), 
                        'pendente', %s, NOW())
            """, (
                consulta_id, medico_id, paciente_id, analista_atribuido, tipo_exame,
                descricao.strip(), 
                observacoes_adicionais.strip() if observacoes_adicionais else None,
                urgencia,
                anexos_json
            ), commit=True)
            
            if pedido_id:
                execute_query("""
                    INSERT INTO logs 
                    (usuario_id, acao, tabela_afetada, registro_id, detalhes, data_registro)
                    VALUES (%s, 'criar', 'pedidos_analise', %s, %s, NOW())
                """, (
                    user_id,
                    pedido_id,
                    json.dumps({
                        'tipo_exame': tipo_exame,
                        'urgencia': urgencia,
                        'paciente_id': paciente_id,
                        'analista_id': analista_atribuido,
                        'incluiu_sinais': incluir_sinais
                    })
                ), commit=True)
                
                flash('Pedido de análise criado com sucesso!', 'success')
                print(f"[SUCCESS] Pedido criado: ID {pedido_id}")
                return redirect(url_for('pedido_analise.meus_pedidos'))
            else:
                flash('Erro ao salvar pedido no banco de dados.', 'danger')
                return redirect(url_for('pedido_analise.novo_pedido'))
            
        except Exception as e:
            logger.error(f"Erro ao criar pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro interno ao processar pedido.', 'danger')
            return redirect(url_for('pedido_analise.novo_pedido'))
    
    # ==============================
    # ROTA: MEUS PEDIDOS
    # ==============================
    @pedido_analise_bp.route('/meus-pedidos')
    @medico_required
    def meus_pedidos():
        """Lista todos os pedidos do médico"""
        try:
            user_id = session['user_id']
            
            medico_result = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            
            if not medico_result:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            medico_id = extrair_valor_resultado(medico_result, 0, 'id')
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Filtros
            status_filter = request.args.get('status', '')
            urgencia_filter = request.args.get('urgencia', '')
            
            query = """
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.urgencia,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    COALESCE(up.nome, CONCAT('Paciente ', pa.paciente_id)) as paciente_nome,
                    COALESCE(
                        (SELECT ua.nome FROM usuarios ua 
                         JOIN analistas a ON ua.id = a.usuario_id 
                         WHERE a.id = pa.analista_id),
                        'Não atribuído'
                    ) as analista_nome,
                    pa.status_aprovacao,
                    pa.paciente_id,
                    pa.consulta_id,
                    (SELECT COUNT(*) FROM sinais_vitais sv WHERE sv.consulta_id = pa.consulta_id) as tem_sinais
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios up ON p.usuario_id = up.id
                WHERE pa.medico_id = %s
            """
            
            params = [medico_id]
            
            conditions = []
            if status_filter:
                conditions.append("pa.status = %s")
                params.append(status_filter)
            
            if urgencia_filter:
                conditions.append("pa.urgencia = %s")
                params.append(urgencia_filter)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " ORDER BY pa.data_solicitacao DESC LIMIT 50"
            
            pedidos = execute_query(query, params, fetch=True)
            
            pedidos_list = []
            if pedidos:
                for p in pedidos:
                    pedidos_list.append({
                        'id': extrair_valor_resultado(p, 0, 'id'),
                        'tipo_exame': str(extrair_valor_resultado(p, 1, 'tipo_exame')) if extrair_valor_resultado(p, 1, 'tipo_exame') else 'Não especificado',
                        'status': str(extrair_valor_resultado(p, 2, 'status')) if extrair_valor_resultado(p, 2, 'status') else 'pendente',
                        'urgencia': str(extrair_valor_resultado(p, 3, 'urgencia')) if extrair_valor_resultado(p, 3, 'urgencia') else 'normal',
                        'data_solicitacao': formatar_data(extrair_valor_resultado(p, 4, 'data_solicitacao')),
                        'data_conclusao': formatar_data(extrair_valor_resultado(p, 5, 'data_conclusao')),
                        'paciente_nome': str(extrair_valor_resultado(p, 6, 'paciente_nome')) if extrair_valor_resultado(p, 6, 'paciente_nome') else f'Paciente {extrair_valor_resultado(p, 9, "paciente_id")}',
                        'analista_nome': str(extrair_valor_resultado(p, 7, 'analista_nome')) if extrair_valor_resultado(p, 7, 'analista_nome') else 'Não atribuído',
                        'status_aprovacao': str(extrair_valor_resultado(p, 8, 'status_aprovacao')) if extrair_valor_resultado(p, 8, 'status_aprovacao') else 'pendente',
                        'paciente_id': extrair_valor_resultado(p, 9, 'paciente_id'),
                        'consulta_id': extrair_valor_resultado(p, 10, 'consulta_id'),
                        'tem_sinais': extrair_valor_resultado(p, 11, 'tem_sinais', 0)
                    })
            
            # Estatísticas
            total_pedidos = extrair_valor_resultado(execute_query("SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s", (medico_id,), fetch=True, one=True), 0, 'COUNT(*)', 0)
            pedidos_pendentes = extrair_valor_resultado(execute_query("SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'pendente'", (medico_id,), fetch=True, one=True), 0, 'COUNT(*)', 0)
            pedidos_em_analise = extrair_valor_resultado(execute_query("SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'em_analise'", (medico_id,), fetch=True, one=True), 0, 'COUNT(*)', 0)
            pedidos_concluidos = extrair_valor_resultado(execute_query("SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'concluido'", (medico_id,), fetch=True, one=True), 0, 'COUNT(*)', 0)
            pedidos_cancelados = extrair_valor_resultado(execute_query("SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'cancelado'", (medico_id,), fetch=True, one=True), 0, 'COUNT(*)', 0)
            
            return render_template('medico/meus_pedidos.html',
                                  pedidos=pedidos_list,
                                  total_pedidos=total_pedidos,
                                  pedidos_pendentes=pedidos_pendentes,
                                  pedidos_em_analise=pedidos_em_analise,
                                  pedidos_concluidos=pedidos_concluidos,
                                  pedidos_cancelados=pedidos_cancelados,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao carregar meus pedidos: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedidos.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ==============================
    # ROTA: VER DETALHES DO PEDIDO
    # ==============================
    @pedido_analise_bp.route('/pedido/<int:pedido_id>')
    @medico_required
    def ver_pedido(pedido_id):
        """Ver detalhes de um pedido específico"""
        try:
            user_id = session['user_id']
            
            pedido_result = execute_query("""
                SELECT pa.*, m.usuario_id as medico_usuario_id
                FROM pedidos_analise pa
                JOIN medicos m ON pa.medico_id = m.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_result:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            medico_usuario_id = extrair_valor_resultado(pedido_result, -1, 'medico_usuario_id')
            
            if medico_usuario_id != user_id:
                flash('Pedido não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            pedido_info = execute_query("""
                SELECT 
                    pa.id,
                    pa.medico_id,
                    pa.paciente_id,
                    pa.consulta_id,
                    pa.analista_id,
                    pa.tipo_exame,
                    pa.urgencia,
                    pa.descricao,
                    pa.observacoes,
                    pa.observacoes_medico,
                    pa.anexos,
                    pa.status,
                    pa.status_aprovacao,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.criado_em,
                    pa.atualizado_em,
                    COALESCE(up.nome, CONCAT('Paciente ', pa.paciente_id)) as paciente_nome,
                    COALESCE(
                        (SELECT ua.nome FROM usuarios ua 
                         JOIN analistas a ON ua.id = a.usuario_id 
                         WHERE a.id = pa.analista_id),
                        'Não atribuído'
                    ) as analista_nome,
                    um.nome as medico_nome,
                    m.especialidade as medico_especialidade,
                    m.crm as medico_crm,
                    p.data_nascimento,
                    p.genero,
                    p.endereco,
                    p.telefone as paciente_telefone,
                    c.data_hora as consulta_data,
                    c.observacoes as consulta_observacoes
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios up ON p.usuario_id = up.id
                JOIN medicos m ON pa.medico_id = m.id
                JOIN usuarios um ON m.usuario_id = um.id
                LEFT JOIN consultas c ON pa.consulta_id = c.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_info:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            pedido_dict = {
                'id': extrair_valor_resultado(pedido_info, 0, 'id'),
                'medico_id': extrair_valor_resultado(pedido_info, 1, 'medico_id'),
                'paciente_id': extrair_valor_resultado(pedido_info, 2, 'paciente_id'),
                'consulta_id': extrair_valor_resultado(pedido_info, 3, 'consulta_id'),
                'analista_id': extrair_valor_resultado(pedido_info, 4, 'analista_id'),
                'tipo_exame': str(extrair_valor_resultado(pedido_info, 5, 'tipo_exame')) if extrair_valor_resultado(pedido_info, 5, 'tipo_exame') else 'Não especificado',
                'urgencia': str(extrair_valor_resultado(pedido_info, 6, 'urgencia')) if extrair_valor_resultado(pedido_info, 6, 'urgencia') else 'normal',
                'descricao': str(extrair_valor_resultado(pedido_info, 7, 'descricao')) if extrair_valor_resultado(pedido_info, 7, 'descricao') else '',
                'observacoes': str(extrair_valor_resultado(pedido_info, 8, 'observacoes')) if extrair_valor_resultado(pedido_info, 8, 'observacoes') else '',
                'observacoes_medico': str(extrair_valor_resultado(pedido_info, 9, 'observacoes_medico')) if extrair_valor_resultado(pedido_info, 9, 'observacoes_medico') else '',
                'anexos': extrair_valor_resultado(pedido_info, 10, 'anexos'),
                'status': str(extrair_valor_resultado(pedido_info, 11, 'status')) if extrair_valor_resultado(pedido_info, 11, 'status') else 'pendente',
                'status_aprovacao': str(extrair_valor_resultado(pedido_info, 12, 'status_aprovacao')) if extrair_valor_resultado(pedido_info, 12, 'status_aprovacao') else 'pendente',
                'data_solicitacao': formatar_data(extrair_valor_resultado(pedido_info, 13, 'data_solicitacao')),
                'data_conclusao': formatar_data(extrair_valor_resultado(pedido_info, 14, 'data_conclusao')),
                'resultado_analise': str(extrair_valor_resultado(pedido_info, 15, 'resultado_analise')) if extrair_valor_resultado(pedido_info, 15, 'resultado_analise') else '',
                'diagnostico_analista': str(extrair_valor_resultado(pedido_info, 16, 'diagnostico_analista')) if extrair_valor_resultado(pedido_info, 16, 'diagnostico_analista') else '',
                'recomendacoes_analista': str(extrair_valor_resultado(pedido_info, 17, 'recomendacoes_analista')) if extrair_valor_resultado(pedido_info, 17, 'recomendacoes_analista') else '',
                'criado_em': formatar_data(extrair_valor_resultado(pedido_info, 18, 'criado_em')),
                'atualizado_em': formatar_data(extrair_valor_resultado(pedido_info, 19, 'atualizado_em')),
                'paciente_nome': str(extrair_valor_resultado(pedido_info, 20, 'paciente_nome')) if extrair_valor_resultado(pedido_info, 20, 'paciente_nome') else f'Paciente {extrair_valor_resultado(pedido_info, 2, "paciente_id")}',
                'analista_nome': str(extrair_valor_resultado(pedido_info, 21, 'analista_nome')) if extrair_valor_resultado(pedido_info, 21, 'analista_nome') else 'Não atribuído',
                'medico_nome': str(extrair_valor_resultado(pedido_info, 22, 'medico_nome')) if extrair_valor_resultado(pedido_info, 22, 'medico_nome') else '',
                'medico_especialidade': str(extrair_valor_resultado(pedido_info, 23, 'medico_especialidade')) if extrair_valor_resultado(pedido_info, 23, 'medico_especialidade') else '',
                'medico_crm': str(extrair_valor_resultado(pedido_info, 24, 'medico_crm')) if extrair_valor_resultado(pedido_info, 24, 'medico_crm') else '',
                'data_nascimento': extrair_valor_resultado(pedido_info, 25, 'data_nascimento'),
                'genero': str(extrair_valor_resultado(pedido_info, 26, 'genero')) if extrair_valor_resultado(pedido_info, 26, 'genero') else '',
                'endereco': str(extrair_valor_resultado(pedido_info, 27, 'endereco')) if extrair_valor_resultado(pedido_info, 27, 'endereco') else '',
                'paciente_telefone': str(extrair_valor_resultado(pedido_info, 28, 'paciente_telefone')) if extrair_valor_resultado(pedido_info, 28, 'paciente_telefone') else '',
                'consulta_data': formatar_data(extrair_valor_resultado(pedido_info, 29, 'consulta_data')),
                'consulta_observacoes': str(extrair_valor_resultado(pedido_info, 30, 'consulta_observacoes')) if extrair_valor_resultado(pedido_info, 30, 'consulta_observacoes') else ''
            }
            
            if pedido_dict.get('data_nascimento'):
                pedido_dict['idade'] = calcular_idade(pedido_dict['data_nascimento'])
            
            anexos_list = []
            if pedido_dict.get('anexos'):
                try:
                    if isinstance(pedido_dict['anexos'], str):
                        anexos_list = json.loads(pedido_dict['anexos'])
                    else:
                        anexos_list = pedido_dict['anexos']
                except:
                    anexos_list = []
            
            sinais_vitais = None
            if pedido_dict.get('consulta_id'):
                sinais_vitais = buscar_sinais_vitais(pedido_dict['consulta_id'])
            
            return render_template('medico/ver_pedido.html',
                                  pedido=pedido_dict,
                                  anexos=anexos_list,
                                  sinais_vitais=sinais_vitais,
                                  formatar_data=formatar_data,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao ver pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedido.', 'danger')
            return redirect(url_for('pedido_analise.meus_pedidos'))
    
    # ==============================
    # ROTA: CANCELAR PEDIDO
    # ==============================
    @pedido_analise_bp.route('/cancelar/<int:pedido_id>', methods=['POST'])
    @medico_required
    def cancelar_pedido(pedido_id):
        """Cancelar um pedido de análise"""
        try:
            user_id = session['user_id']
            
            pedido_check = execute_query("""
                SELECT pa.id, pa.status, m.usuario_id
                FROM pedidos_analise pa
                JOIN medicos m ON pa.medico_id = m.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_check:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            pedido_status = extrair_valor_resultado(pedido_check, 1, 'status')
            medico_usuario_id = extrair_valor_resultado(pedido_check, 2, 'usuario_id')
            
            if medico_usuario_id != user_id:
                flash('Pedido não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            if pedido_status not in ['pendente', 'em_analise']:
                flash('Este pedido não pode ser cancelado no seu estado atual.', 'warning')
                return redirect(url_for('pedido_analise.ver_pedido', pedido_id=pedido_id))
            
            result = execute_query("""
                UPDATE pedidos_analise 
                SET status = 'cancelado', atualizado_em = NOW()
                WHERE id = %s
            """, (pedido_id,), commit=True)
            
            if result is not None:
                execute_query("""
                    INSERT INTO logs 
                    (usuario_id, acao, tabela_afetada, registro_id, detalhes, data_registro)
                    VALUES (%s, 'cancelar', 'pedidos_analise', %s, %s, NOW())
                """, (
                    user_id,
                    pedido_id,
                    json.dumps({'status_anterior': pedido_status})
                ), commit=True)
                
                flash('Pedido cancelado com sucesso!', 'success')
            else:
                flash('Erro ao cancelar pedido.', 'danger')
            
            return redirect(url_for('pedido_analise.meus_pedidos'))
            
        except Exception as e:
            logger.error(f"Erro ao cancelar pedido: {e}")
            flash('Erro ao cancelar pedido.', 'danger')
            return redirect(url_for('pedido_analise.ver_pedido', pedido_id=pedido_id))
    
    # ==============================
    # ROTA: DEBUG ANALISTAS
    # ==============================
    @pedido_analise_bp.route('/debug-analistas')
    @medico_required
    def debug_analistas():
        """Debug: verificar analistas"""
        try:
            analistas_raw = execute_query("""
                SELECT 
                    a.id,
                    u.nome,
                    a.especialidade,
                    a.registro_profissional,
                    a.status,
                    a.carga_horaria_semanal,
                    a.is_supervisor,
                    a.telefone,
                    a.data_contratacao,
                    (SELECT COUNT(*) 
                     FROM pedidos_analise pa 
                     WHERE pa.analista_id = a.id 
                     AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                FROM analistas a
                LEFT JOIN usuarios u ON a.usuario_id = u.id
                WHERE a.status = 'ativo'
                ORDER BY u.nome
            """, fetch=True)
            
            analistas = []
            if analistas_raw:
                for a in analistas_raw:
                    analistas.append({
                        'id': extrair_valor_resultado(a, 0, 'id'),
                        'nome': extrair_valor_resultado(a, 1, 'nome') or f'Analista {extrair_valor_resultado(a, 0, "id")}',
                        'especialidade': extrair_valor_resultado(a, 2, 'especialidade') or 'Geral',
                        'registro': extrair_valor_resultado(a, 3, 'registro_profissional') or '',
                        'status': extrair_valor_resultado(a, 4, 'status') or 'ativo',
                        'carga_horaria': extrair_valor_resultado(a, 5, 'carga_horaria_semanal', 40),
                        'is_supervisor': extrair_valor_resultado(a, 6, 'is_supervisor', 0),
                        'telefone': extrair_valor_resultado(a, 7, 'telefone') or '',
                        'data_contratacao': extrair_valor_resultado(a, 8, 'data_contratacao'),
                        'pedidos_ativos': extrair_valor_resultado(a, 9, 'pedidos_ativos', 0)
                    })
            
            return render_template('debug_analistas.html',
                                  analistas=analistas,
                                  total=len(analistas),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro no debug analistas: {e}")
            return f"Erro: {str(e)}"
    
    # ==============================
    # ROTA: API ESTATÍSTICAS
    # ==============================
    @pedido_analise_bp.route('/api/estatisticas')
    @medico_required
    def api_estatisticas():
        """API para estatísticas dos pedidos"""
        try:
            user_id = session['user_id']
            
            medico_result = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            
            if not medico_result:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            medico_id = extrair_valor_resultado(medico_result, 0, 'id')
            
            if not medico_id:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            estatisticas = execute_query("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) as pendentes,
                    SUM(CASE WHEN status = 'em_analise' THEN 1 ELSE 0 END) as em_analise,
                    SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) as concluidos,
                    SUM(CASE WHEN status = 'cancelado' THEN 1 ELSE 0 END) as cancelados
                FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            por_urgencia = execute_query("""
                SELECT 
                    urgencia,
                    COUNT(*) as quantidade
                FROM pedidos_analise 
                WHERE medico_id = %s
                GROUP BY urgencia
            """, (medico_id,), fetch=True)
            
            urgencia_dict = {}
            if por_urgencia:
                for item in por_urgencia:
                    urgencia = extrair_valor_resultado(item, 0, 'urgencia')
                    quantidade = extrair_valor_resultado(item, 1, 'quantidade', 0)
                    if urgencia:
                        urgencia_dict[urgencia] = quantidade
            
            return jsonify({
                'total': extrair_valor_resultado(estatisticas, 0, 'total', 0),
                'pendentes': extrair_valor_resultado(estatisticas, 1, 'pendentes', 0),
                'em_analise': extrair_valor_resultado(estatisticas, 2, 'em_analise', 0),
                'concluidos': extrair_valor_resultado(estatisticas, 3, 'concluidos', 0),
                'cancelados': extrair_valor_resultado(estatisticas, 4, 'cancelados', 0),
                'por_urgencia': urgencia_dict
            })
            
        except Exception as e:
            logger.error(f"Erro na API estatísticas: {e}")
            return jsonify({'error': str(e)}), 500
    
    return pedido_analise_bp
