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
            
            # Funções de classificação inline (para não depender de import)
            def classificar_pressao_arterial(pa):
                if not pa:
                    return None
                try:
                    # Formato esperado: "120/80"
                    sistole, diastole = map(int, pa.split('/'))
                    if sistole < 120 and diastole < 80:
                        return "Normal"
                    elif 120 <= sistole <= 129 and diastole < 80:
                        return "Elevada"
                    elif 130 <= sistole <= 139 or 80 <= diastole <= 89:
                        return "Hipertensão Estágio 1"
                    elif sistole >= 140 or diastole >= 90:
                        return "Hipertensão Estágio 2"
                    return "Não classificado"
                except:
                    return "Formato inválido"
            
            def classificar_frequencia_cardiaca(fc):
                if not fc:
                    return None
                try:
                    fc = int(fc)
                    if fc < 60:
                        return "Bradicardia"
                    elif 60 <= fc <= 100:
                        return "Normal"
                    else:
                        return "Taquicardia"
                except:
                    return "Não classificado"
            
            def classificar_frequencia_respiratoria(fr):
                if not fr:
                    return None
                try:
                    fr = int(fr)
                    if fr < 12:
                        return "Bradipneia"
                    elif 12 <= fr <= 20:
                        return "Normal"
                    else:
                        return "Taquipneia"
                except:
                    return "Não classificado"
            
            def classificar_temperatura(temp):
                if not temp:
                    return None
                try:
                    temp = float(temp)
                    if temp < 35.0:
                        return "Hipotermia"
                    elif 35.0 <= temp <= 37.2:
                        return "Normal"
                    elif 37.3 <= temp <= 37.7:
                        return "Febrícula"
                    elif temp > 37.7:
                        return "Febre"
                    return "Não classificado"
                except:
                    return "Não classificado"
            
            def classificar_saturacao_oxigenio(spo2):
                if not spo2:
                    return None
                try:
                    spo2 = int(spo2)
                    if spo2 >= 95:
                        return "Normal"
                    elif 90 <= spo2 <= 94:
                        return "Hipoxemia leve"
                    else:
                        return "Hipoxemia grave"
                except:
                    return "Não classificado"
            
            def classificar_glicemia(glicemia):
                if not glicemia:
                    return None
                try:
                    glicemia = int(glicemia)
                    if glicemia < 70:
                        return "Hipoglicemia"
                    elif 70 <= glicemia <= 99:
                        return "Normal (jejum)"
                    elif 100 <= glicemia <= 125:
                        return "Glicemia alterada"
                    else:
                        return "Hiperglicemia"
                except:
                    return "Não classificado"
            
            sinais_vitais = {
                'id': sinais_data[0],
                'pressao_arterial': sinais_data[1],
                'pa_classificacao': classificar_pressao_arterial(sinais_data[1]) if sinais_data[1] else None,
                'frequencia_cardiaca': sinais_data[2],
                'fc_classificacao': classificar_frequencia_cardiaca(sinais_data[2]) if sinais_data[2] else None,
                'frequencia_respiratoria': sinais_data[3],
                'fr_classificacao': classificar_frequencia_respiratoria(sinais_data[3]) if sinais_data[3] else None,
                'temperatura': float(sinais_data[4]) if sinais_data[4] else None,
                'temp_classificacao': classificar_temperatura(sinais_data[4]) if sinais_data[4] else None,
                'saturacao_oxigenio': sinais_data[5],
                'spo2_classificacao': classificar_saturacao_oxigenio(sinais_data[5]) if sinais_data[5] else None,
                'glicemia': sinais_data[6],
                'glicemia_classificacao': classificar_glicemia(sinais_data[6]) if sinais_data[6] else None,
                'peso': float(sinais_data[7]) if sinais_data[7] else None,
                'data_afericao': formatar_data(sinais_data[8], '%d/%m/%Y %H:%M') if sinais_data[8] else '',
                'observacoes': sinais_data[9] or ''
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
            
            # CORREÇÃO: Verificar tipo do retorno
            medico_result = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            
            if not medico_result:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # CORREÇÃO: Suportar dict ou tuple
            if isinstance(medico_result, dict):
                medico_id = medico_result.get('id')
            else:
                medico_id = medico_result[0] if medico_result else None
            
            if not medico_id:
                flash('Erro ao identificar médico.', 'danger')
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
                AND c.status IN ('realizada', 'agendada', 'confirmada')
                ORDER BY c.data_hora DESC
                LIMIT 15
            """, (medico_id,), fetch=True)
            
            # Buscar analistas
            analistas = execute_query("""
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
            
            print(f"[DEBUG] Analistas encontrados: {len(analistas) if analistas else 0}")
            
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
                    # CORREÇÃO: Suportar dict ou tuple
                    if isinstance(c, dict):
                        idade = calcular_idade(c.get('data_nascimento')) if c.get('data_nascimento') else None
                        consultas_list.append({
                            'id': c.get('id'),
                            'data_hora': formatar_data(c.get('data_hora')),
                            'status': c.get('status'),
                            'paciente_nome': c.get('paciente_nome') or 'Paciente',
                            'data_nascimento': formatar_data(c.get('data_nascimento'), '%d/%m/%Y') if c.get('data_nascimento') else '',
                            'idade': idade,
                            'genero': c.get('genero'),
                            'paciente_id': c.get('paciente_id'),
                            'observacoes': c.get('observacoes') or '',
                            'tem_sinais': c.get('tem_sinais') or 0
                        })
                    else:
                        # É tupla
                        idade = calcular_idade(c[4]) if len(c) > 4 and c[4] else None
                        consultas_list.append({
                            'id': c[0] if len(c) > 0 else None,
                            'data_hora': formatar_data(c[1]) if len(c) > 1 else '',
                            'status': c[2] if len(c) > 2 else '',
                            'paciente_nome': c[3] if len(c) > 3 else 'Paciente',
                            'data_nascimento': formatar_data(c[4], '%d/%m/%Y') if len(c) > 4 and c[4] else '',
                            'idade': idade,
                            'genero': c[5] if len(c) > 5 else '',
                            'paciente_id': c[6] if len(c) > 6 else None,
                            'observacoes': c[7] if len(c) > 7 else '',
                            'tem_sinais': c[8] if len(c) > 8 else 0
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
    # ROTA: CRIAR PEDIDO
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
            incluir_sinais = request.form.get('incluir_sinais') == 'on'
            
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
            
            if isinstance(medico_result, dict):
                medico_id = medico_result.get('id')
            else:
                medico_id = medico_result[0]
            
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
                    
                    observacoes_adicionais = observacoes + "\n\n" + sinais_texto if observacoes else sinais_texto
            
            # Processar analista
            analista_atribuido = None
            
            if analista_id and analista_id != 'auto':
                analista_check = execute_query(
                    "SELECT id FROM analistas WHERE id = %s AND status = 'ativo'",
                    (analista_id,), fetch=True, one=True
                )
                if analista_check:
                    if isinstance(analista_check, dict):
                        analista_atribuido = analista_check.get('id')
                    else:
                        analista_atribuido = analista_check[0]
            
            if not analista_atribuido:
                # Atribuição automática
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
                    if isinstance(analista_auto, dict):
                        analista_atribuido = analista_auto.get('id')
                    else:
                        analista_atribuido = analista_auto[0]
            
            # Processar anexos
            anexos_info = []
            if 'anexos' in request.files:
                files = request.files.getlist('anexos')
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
            
            # Inserir pedido
            pedido_id = execute_query("""
                INSERT INTO pedidos_analise 
                (consulta_id, medico_id, paciente_id, analista_id, tipo_exame, 
                 descricao, observacoes, urgencia, status, data_solicitacao,
                 anexos, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendente', NOW(), 
                        %s, NOW())
            """, (
                consulta_id, medico_id, paciente_id, analista_atribuido, tipo_exame,
                descricao.strip(), 
                observacoes_adicionais.strip() if observacoes_adicionais else None,
                urgencia,
                anexos_json
            ), commit=True)
            
            if pedido_id:
                flash('Pedido de análise criado com sucesso!', 'success')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            else:
                flash('Erro ao salvar pedido.', 'danger')
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
            
            if isinstance(medico_result, dict):
                medico_id = medico_result.get('id')
            else:
                medico_id = medico_result[0]
            
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
                    pa.paciente_id,
                    pa.consulta_id
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios up ON p.usuario_id = up.id
                WHERE pa.medico_id = %s
            """
            
            params = [medico_id]
            
            if status_filter:
                query += " AND pa.status = %s"
                params.append(status_filter)
            
            if urgencia_filter:
                query += " AND pa.urgencia = %s"
                params.append(urgencia_filter)
            
            query += " ORDER BY pa.data_solicitacao DESC LIMIT 50"
            
            pedidos = execute_query(query, params, fetch=True)
            
            pedidos_list = []
            if pedidos:
                for p in pedidos:
                    if isinstance(p, dict):
                        pedidos_list.append({
                            'id': p.get('id'),
                            'tipo_exame': p.get('tipo_exame') or 'Não especificado',
                            'status': p.get('status') or 'pendente',
                            'urgencia': p.get('urgencia') or 'normal',
                            'data_solicitacao': formatar_data(p.get('data_solicitacao')),
                            'data_conclusao': formatar_data(p.get('data_conclusao')),
                            'paciente_nome': p.get('paciente_nome') or f'Paciente {p.get("paciente_id")}',
                            'analista_nome': p.get('analista_nome') or 'Não atribuído',
                            'paciente_id': p.get('paciente_id'),
                            'consulta_id': p.get('consulta_id')
                        })
                    else:
                        pedidos_list.append({
                            'id': p[0] if len(p) > 0 else None,
                            'tipo_exame': p[1] if len(p) > 1 else 'Não especificado',
                            'status': p[2] if len(p) > 2 else 'pendente',
                            'urgencia': p[3] if len(p) > 3 else 'normal',
                            'data_solicitacao': formatar_data(p[4]) if len(p) > 4 else '',
                            'data_conclusao': formatar_data(p[5]) if len(p) > 5 else '',
                            'paciente_nome': p[6] if len(p) > 6 else f'Paciente {p[8] if len(p) > 8 else "?"}',
                            'analista_nome': p[7] if len(p) > 7 else 'Não atribuído',
                            'paciente_id': p[8] if len(p) > 8 else None,
                            'consulta_id': p[9] if len(p) > 9 else None
                        })
            
            # Estatísticas
            total = len(pedidos_list)
            pendentes = len([p for p in pedidos_list if p['status'] == 'pendente'])
            em_analise = len([p for p in pedidos_list if p['status'] == 'em_analise'])
            concluidos = len([p for p in pedidos_list if p['status'] == 'concluido'])
            cancelados = len([p for p in pedidos_list if p['status'] == 'cancelado'])
            
            return render_template('medico/meus_pedidos.html',
                                  pedidos=pedidos_list,
                                  total_pedidos=total,
                                  pedidos_pendentes=pendentes,
                                  pedidos_em_analise=em_analise,
                                  pedidos_concluidos=concluidos,
                                  pedidos_cancelados=cancelados,
                                  formatar_data=formatar_data,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao carregar meus pedidos: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedidos.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    return pedido_analise_bp
