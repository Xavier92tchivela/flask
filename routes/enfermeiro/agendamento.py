from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash
from .utils import execute_query, enfermeiro_required
import logging
import random
import string
import uuid

logger = logging.getLogger(__name__)

agendamento_bp = Blueprint('agendamento', __name__, url_prefix='/agendamento')

# Atributo para armazenar a conexão MySQL
agendamento_bp.mysql = None

def set_mysql(mysql_instance):
    agendamento_bp.mysql = mysql_instance

def gerar_senha_temp():
    """Gera uma senha temporária aleatória"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def gerar_email_temp(nome):
    """Gera um email temporário baseado no nome"""
    nome_limpo = nome.lower().replace(' ', '_')[:20]
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{nome_limpo}_{timestamp}@temp.com"

def gerar_numero_fatura():
    """Gera um número único para a fatura"""
    ano = datetime.now().strftime('%Y')
    mes = datetime.now().strftime('%m')
    dia = datetime.now().strftime('%d')
    sequencia = random.randint(1000, 9999)
    return f"FAT-{ano}{mes}{dia}-{sequencia}"

def normalizar_genero(genero):
    """
    Normaliza o gênero para os valores ENUM da tabela pacientes:
    - 'masculino', 'feminino', 'outro'
    """
    if not genero or genero.strip() == '':
        return None
    
    genero = genero.strip().lower()
    
    if genero in ['m', 'masculino', 'masc']:
        return 'masculino'
    elif genero in ['f', 'feminino', 'fem']:
        return 'feminino'
    elif genero in ['o', 'outro', 'outros']:
        return 'outro'
    else:
        return None

@agendamento_bp.route('/')
@enfermeiro_required
def listar_agendamentos():
    """Lista todos os agendamentos feitos pelo enfermeiro"""
    agendamentos = execute_query("""
        SELECT 
            c.id,
            c.data_hora,
            c.status,
            c.observacoes,
            c.criado_em,
            p.id as paciente_id,
            u_pac.nome as paciente_nome,
            m.id as medico_id,
            u_med.nome as medico_nome,
            COALESCE(m.especialidade, 'Não informada') as especialidade,
            f.id as fatura_id,
            f.numero_fatura,
            f.status_pagamento,
            f.valor_consulta
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u_pac ON p.usuario_id = u_pac.id
        JOIN medicos m ON c.medico_id = m.id
        JOIN usuarios u_med ON m.usuario_id = u_med.id
        LEFT JOIN faturas f ON c.id = f.consulta_id
        ORDER BY c.data_hora DESC
    """, fetch=True) or []
    
    return render_template('enfermeiro/agendamento/listar.html',
                         agendamentos=agendamentos,
                         hoje=date.today())

@agendamento_bp.route('/novo', methods=['GET', 'POST'])
@enfermeiro_required
def novo_agendamento():
    """Página para criar novo agendamento de consulta"""
    if request.method == 'POST':
        # Pegar dados do formulário
        paciente_existente = request.form.get('paciente_existente')
        novo_paciente_nome = request.form.get('novo_paciente_nome')
        novo_paciente_data_nasc = request.form.get('novo_paciente_data_nasc')
        novo_paciente_genero = request.form.get('novo_paciente_genero')
        novo_paciente_telefone = request.form.get('novo_paciente_telefone')
        novo_paciente_endereco = request.form.get('novo_paciente_endereco')
        
        medico_id = request.form.get('medico_id')
        data = request.form.get('data_consulta')
        hora = request.form.get('hora_consulta')
        observacoes = request.form.get('observacoes', '')
        sintomas = request.form.get('sintomas', '')
        
        # Validar campos obrigatórios
        if not all([medico_id, data, hora]):
            flash('Médico, data e hora são obrigatórios.', 'danger')
            return redirect(url_for('enfermeiro.agendamento.novo_agendamento'))
        
        # Validar sintomas
        if not sintomas or sintomas.strip() == '':
            flash('Por favor, selecione pelo menos um sintoma.', 'danger')
            return redirect(url_for('enfermeiro.agendamento.novo_agendamento'))
        
        # Determinar paciente_id
        paciente_id = None
        paciente_nome = None
        paciente_telefone = None
        
        if paciente_existente and paciente_existente.strip():
            # Usar paciente existente
            paciente_id = int(paciente_existente)
            logger.info(f"Usando paciente existente ID: {paciente_id}")
            
            # Buscar dados do paciente
            paciente_info = execute_query("""
                SELECT u.nome, u.telefone
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,), fetch=True)
            
            if paciente_info:
                if isinstance(paciente_info[0], dict):
                    paciente_nome = paciente_info[0].get('nome')
                    paciente_telefone = paciente_info[0].get('telefone')
                else:
                    paciente_nome = paciente_info[0][0] if len(paciente_info[0]) > 0 else None
                    paciente_telefone = paciente_info[0][1] if len(paciente_info[0]) > 1 else None
        else:
            # Cadastrar novo paciente
            if not novo_paciente_nome or not novo_paciente_data_nasc:
                flash('Nome e data de nascimento são obrigatórios para novo paciente.', 'danger')
                return redirect(url_for('enfermeiro.agendamento.novo_agendamento'))
            
            try:
                genero_normalizado = normalizar_genero(novo_paciente_genero)
                logger.info(f"Gênero recebido: '{novo_paciente_genero}', normalizado: '{genero_normalizado}'")
                
                user_uuid = str(uuid.uuid4())
                email_temp = gerar_email_temp(novo_paciente_nome)
                senha_temp = gerar_senha_temp()
                senha_hash = generate_password_hash(senha_temp)
                
                cursor = agendamento_bp.mysql.connection.cursor()
                
                cursor.execute("""
                    INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo)
                    VALUES (%s, %s, %s, %s, 'paciente', TRUE)
                """, (user_uuid, novo_paciente_nome, email_temp, senha_hash))
                
                usuario_id = cursor.lastrowid
                logger.info(f"Usuário criado com ID: {usuario_id}")
                
                cursor.execute("""
                    INSERT INTO pacientes (usuario_id, data_nascimento, genero, telefone, endereco)
                    VALUES (%s, %s, %s, %s, %s)
                """, (usuario_id, novo_paciente_data_nasc, genero_normalizado,
                      novo_paciente_telefone or None, novo_paciente_endereco or None))
                
                paciente_id = cursor.lastrowid
                agendamento_bp.mysql.connection.commit()
                cursor.close()
                
                paciente_nome = novo_paciente_nome
                paciente_telefone = novo_paciente_telefone
                
                logger.info(f"Paciente criado com ID: {paciente_id}")
                flash(f'Paciente {novo_paciente_nome} cadastrado com sucesso!', 'success')
                
            except Exception as e:
                agendamento_bp.mysql.connection.rollback()
                logger.error(f"Erro ao cadastrar novo paciente: {e}")
                import traceback
                logger.error(traceback.format_exc())
                flash(f'Erro ao cadastrar novo paciente: {str(e)}', 'danger')
                return redirect(url_for('enfermeiro.agendamento.novo_agendamento'))
        
        # Combinar data e hora
        data_hora = f"{data} {hora}:00"
        
        try:
            cursor = agendamento_bp.mysql.connection.cursor()
            
            # Inserir consulta
            cursor.execute("""
                INSERT INTO consultas 
                (paciente_id, medico_id, data_hora, status, observacoes, sintomas, criado_em)
                VALUES (%s, %s, %s, 'agendada', %s, %s, NOW())
            """, (paciente_id, medico_id, data_hora, observacoes, sintomas))
            
            consulta_id = cursor.lastrowid
            agendamento_bp.mysql.connection.commit()
            
            logger.info(f"Consulta criada com ID: {consulta_id}")
            
            # ========== GERAR FATURA ==========
            valor_consulta = 2500.00
            numero_fatura = gerar_numero_fatura()
            
            # Verificar se já existe fatura para esta consulta
            cursor.execute("""
                SELECT id FROM faturas WHERE consulta_id = %s
            """, (consulta_id,))
            fatura_existente = cursor.fetchone()
            
            if not fatura_existente:
                # Inserir fatura
                cursor.execute("""
                    INSERT INTO faturas 
                    (numero_fatura, consulta_id, paciente_id, paciente_nome, paciente_telefone, 
                     data_consulta, valor_consulta, status_pagamento, data_emissao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendente', NOW())
                """, (numero_fatura, consulta_id, paciente_id, paciente_nome, paciente_telefone,
                      data_hora, valor_consulta))
                
                fatura_id = cursor.lastrowid
                agendamento_bp.mysql.connection.commit()
                
                logger.info(f"Fatura gerada: {numero_fatura} (ID: {fatura_id}) para consulta {consulta_id}")
                
                flash(f'Consulta agendada com sucesso! Fatura nº {numero_fatura} gerada no valor de {valor_consulta:,.2f} Kz', 'success')
                
                # Redirecionar para visualizar fatura
                return redirect(url_for('enfermeiro.agendamento.visualizar_fatura', consulta_id=consulta_id))
            else:
                logger.warning(f"Fatura já existe para consulta {consulta_id}")
                flash('Consulta agendada, mas a fatura já existia!', 'warning')
                return redirect(url_for('enfermeiro.agendamento.listar_agendamentos'))
            
        except Exception as e:
            agendamento_bp.mysql.connection.rollback()
            logger.error(f"Erro ao agendar consulta: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Erro ao agendar consulta. Tente novamente.', 'danger')
            return redirect(url_for('enfermeiro.agendamento.novo_agendamento'))
        finally:
            cursor.close()
    
    # GET: Carregar página
    pacientes = execute_query("""
        SELECT p.id, u.nome, u.telefone
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE u.ativo = TRUE
        ORDER BY u.nome
    """, fetch=True) or []
    
    medicos_raw = execute_query("""
        SELECT 
            m.id,
            u.nome,
            COALESCE(m.especialidade, 'Não informada') as especialidade,
            COALESCE(m.crm, '--') as crm
        FROM medicos m
        JOIN usuarios u ON m.usuario_id = u.id
        WHERE u.ativo = TRUE
        ORDER BY u.nome
    """, fetch=True) or []
    
    medicos = []
    for m in medicos_raw:
        if isinstance(m, dict):
            medicos.append(m)
        else:
            medicos.append({
                'id': m[0] if len(m) > 0 else None,
                'nome': m[1] if len(m) > 1 else 'Nome não disponível',
                'especialidade': m[2] if len(m) > 2 else 'Não informada',
                'crm': m[3] if len(m) > 3 else '--'
            })
    
    logger.info(f"Médicos encontrados: {len(medicos)}")
    hoje = date.today().isoformat()
    
    return render_template('enfermeiro/agendamento/novo.html',
                         pacientes=pacientes,
                         medicos=medicos,
                         hoje=hoje)

@agendamento_bp.route('/fatura/<int:consulta_id>')
@enfermeiro_required
def visualizar_fatura(consulta_id):
    """Visualizar fatura da consulta"""
    try:
        # Buscar dados da fatura com as colunas corretas
        fatura = execute_query("""
            SELECT 
                f.id,
                f.numero_fatura,
                f.consulta_id,
                f.paciente_id,
                f.paciente_nome,
                f.paciente_telefone,
                f.data_consulta,
                f.valor_consulta,
                f.status_pagamento,
                f.data_emissao,
                f.data_pagamento,
                f.forma_pagamento,
                c.observacoes as consulta_observacoes,
                c.sintomas,
                m.id as medico_id,
                u_med.nome as medico_nome,
                COALESCE(m.especialidade, 'Não informada') as medico_especialidade,
                COALESCE(m.crm, '--') as medico_crm
            FROM faturas f
            INNER JOIN consultas c ON f.consulta_id = c.id
            INNER JOIN medicos m ON c.medico_id = m.id
            INNER JOIN usuarios u_med ON m.usuario_id = u_med.id
            WHERE f.consulta_id = %s
        """, (consulta_id,), fetch=True)
        
        if not fatura or len(fatura) == 0:
            logger.warning(f"Fatura não encontrada para consulta {consulta_id}")
            flash('Fatura não encontrada!', 'danger')
            return redirect(url_for('enfermeiro.agendamento.listar_agendamentos'))
        
        fatura = fatura[0]
        
        # Converter para dicionário se for tupla
        if not isinstance(fatura, dict):
            fatura = {
                'id': fatura[0],
                'numero_fatura': fatura[1],
                'consulta_id': fatura[2],
                'paciente_id': fatura[3],
                'paciente_nome': fatura[4],
                'paciente_telefone': fatura[5],
                'data_consulta': fatura[6],
                'valor_consulta': fatura[7],
                'status_pagamento': fatura[8],
                'data_emissao': fatura[9],
                'data_pagamento': fatura[10],
                'forma_pagamento': fatura[11],
                'consulta_observacoes': fatura[12] if len(fatura) > 12 else '',
                'sintomas': fatura[13] if len(fatura) > 13 else '',
                'medico_id': fatura[14] if len(fatura) > 14 else None,
                'medico_nome': fatura[15] if len(fatura) > 15 else '',
                'medico_especialidade': fatura[16] if len(fatura) > 16 else '',
                'medico_crm': fatura[17] if len(fatura) > 17 else ''
            }
        
        logger.info(f"Fatura carregada: {fatura.get('numero_fatura')}")
        
        return render_template('enfermeiro/agendamento/fatura.html', fatura=fatura)
        
    except Exception as e:
        logger.error(f"Erro ao visualizar fatura: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Erro ao carregar fatura!', 'danger')
        return redirect(url_for('enfermeiro.agendamento.listar_agendamentos'))

@agendamento_bp.route('/fatura/pagar/<int:fatura_id>', methods=['POST'])
@enfermeiro_required
def pagar_fatura(fatura_id):
    """Marcar fatura como paga"""
    try:
        forma_pagamento = request.form.get('forma_pagamento', 'dinheiro')
        
        execute_query("""
            UPDATE faturas 
            SET status_pagamento = 'pago', 
                data_pagamento = NOW(),
                forma_pagamento = %s
            WHERE id = %s
        """, (forma_pagamento, fatura_id))
        
        flash('Fatura marcada como paga com sucesso!', 'success')
        
    except Exception as e:
        logger.error(f"Erro ao pagar fatura: {e}")
        flash('Erro ao processar pagamento!', 'danger')
    
    return redirect(request.referrer or url_for('enfermeiro.agendamento.listar_agendamentos'))

@agendamento_bp.route('/medico/<int:medico_id>/horarios')
@enfermeiro_required
def horarios_disponiveis(medico_id):
    """API para buscar horários disponíveis de um médico"""
    data = request.args.get('data')
    
    if not data:
        return jsonify({'error': 'Data não informada'}), 400
    
    ocupados = execute_query("""
        SELECT TIME(data_hora) as hora
        FROM consultas
        WHERE medico_id = %s AND DATE(data_hora) = %s AND status != 'cancelada'
    """, (medico_id, data), fetch=True) or []
    
    horarios_ocupados = []
    for h in ocupados:
        if isinstance(h, dict):
            hora = h.get('hora')
        else:
            hora = h[0] if h else None
        
        if hora:
            if hasattr(hora, 'strftime'):
                horarios_ocupados.append(hora.strftime('%H:%M'))
            else:
                horarios_ocupados.append(str(hora))
    
    todos_horarios = []
    for hora in range(8, 18):
        for minuto in [0, 30]:
            todos_horarios.append(f"{hora:02d}:{minuto:02d}")
    
    horarios_disponiveis = [h for h in todos_horarios if h not in horarios_ocupados]
    
    return jsonify({
        'disponiveis': horarios_disponiveis,
        'ocupados': horarios_ocupados
    })

@agendamento_bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
@enfermeiro_required
def cancelar_agendamento(consulta_id):
    """Cancela um agendamento e atualiza a fatura"""
    try:
        execute_query("""
            UPDATE consultas SET status = 'cancelada' 
            WHERE id = %s
        """, (consulta_id,))
        
        execute_query("""
            UPDATE faturas 
            SET status_pagamento = 'cancelado'
            WHERE consulta_id = %s
        """, (consulta_id,))
        
        flash('Agendamento cancelado com sucesso!', 'success')
    except Exception as e:
        logger.error(f"Erro ao cancelar agendamento: {e}")
        flash('Erro ao cancelar agendamento.', 'danger')
    
    return redirect(url_for('enfermeiro.agendamento.listar_agendamentos'))

@agendamento_bp.route('/pacientes/buscar')
@enfermeiro_required
def buscar_pacientes():
    """API para buscar pacientes por nome"""
    termo = request.args.get('q', '')
    
    if len(termo) < 3:
        return jsonify([])
    
    pacientes = execute_query("""
        SELECT p.id, u.nome, u.telefone
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE u.nome LIKE %s AND u.ativo = TRUE
        ORDER BY u.nome
        LIMIT 10
    """, (f'%{termo}%',), fetch=True) or []
    
    resultados = []
    for p in pacientes:
        if isinstance(p, dict):
            resultados.append({
                'id': p.get('id'),
                'text': f"{p.get('nome')} - {p.get('telefone') or 'Sem telefone'}",
                'nome': p.get('nome'),
                'telefone': p.get('telefone')
            })
        else:
            resultados.append({
                'id': p[0] if len(p) > 0 else None,
                'text': f"{p[1] if len(p) > 1 else 'Nome'} - {p[2] if len(p) > 2 else 'Sem telefone'}",
                'nome': p[1] if len(p) > 1 else 'Nome',
                'telefone': p[2] if len(p) > 2 else None
            })
    
    return jsonify(resultados)