# routes/enfermeiro/medicamentos.py
from flask import Blueprint, render_template, session, flash, redirect, url_for, request, jsonify
from datetime import datetime, date, timedelta, time
import traceback
import logging

logger = logging.getLogger(__name__)

medicamentos_bp = Blueprint('medicamentos', __name__, url_prefix='/medicamentos')

# Variável global para o MySQL
mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL"""
    global mysql
    mysql = mysql_instance

def decode_bytes(value):
    """Decodifica bytes para string UTF-8"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    return value

def get_enfermeiro_id():
    """Obtém o ID do enfermeiro logado"""
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM enfermeiros WHERE usuario_id = %s", (session.get('user_id'),))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None
    except:
        return None

def converter_para_time(valor):
    """Converte timedelta ou time para time"""
    if valor is None:
        return None
    if isinstance(valor, time):
        return valor
    if isinstance(valor, timedelta):
        # Converter timedelta para time
        total_seconds = int(valor.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return time(hours, minutes)
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor, '%H:%M:%S').time()
        except:
            try:
                return datetime.strptime(valor, '%H:%M').time()
            except:
                return None
    return None

def formatar_hora(valor):
    """Formata hora de forma segura"""
    if valor is None:
        return None
    if isinstance(valor, timedelta):
        total_seconds = int(valor.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(valor, time):
        return valor.strftime('%H:%M')
    if isinstance(valor, str):
        return valor[:5] if len(valor) >= 5 else valor
    return None

# ===================== LISTAR MEDICAMENTOS POR INTERNAÇÃO =====================
@medicamentos_bp.route('/internacao/<int:internacao_id>')
def listar_por_internacao(internacao_id):
    """Lista medicamentos prescritos para uma internação"""
    try:
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("auth.login"))
        
        cursor = mysql.connection.cursor()
        
        # Buscar dados da internação
        cursor.execute("""
            SELECT i.id, i.numero_prontuario, u.nome as paciente_nome,
                   p.data_nascimento, i.data_internacao
            FROM internacoes i
            JOIN pacientes p ON i.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE i.id = %s AND i.status = 'ativa'
        """, (internacao_id,))
        
        internacao = cursor.fetchone()
        
        if not internacao:
            flash("Internação não encontrada.", "danger")
            return redirect(url_for("enfermeiro.internados.listar_internados"))
        
        # Calcular idade
        idade = None
        if internacao[3]:
            today = datetime.now().date()
            birth_date = internacao[3]
            if isinstance(birth_date, datetime):
                birth_date = birth_date.date()
            idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        internacao_dados = {
            'id': internacao[0],
            'prontuario': internacao[1],
            'paciente_nome': decode_bytes(internacao[2]) if isinstance(internacao[2], bytes) else internacao[2],
            'idade': idade,
            'data_internacao': internacao[4]
        }
        
        # Buscar medicamentos prescritos
        cursor.execute("""
            SELECT 
                mp.id,
                mp.medicamento,
                mp.dosagem,
                mp.via,
                mp.frequencia,
                mp.horario_inicio,
                mp.horario_fim,
                mp.data_inicio,
                mp.data_fim,
                mp.observacoes,
                mp.status,
                u.nome as medico_nome
            FROM medicamentos_prescritos mp
            LEFT JOIN medicos m ON mp.medico_id = m.id
            LEFT JOIN usuarios u ON m.usuario_id = u.id
            WHERE mp.internacao_id = %s
            ORDER BY mp.status DESC, mp.data_inicio DESC
        """, (internacao_id,))
        
        medicamentos_raw = cursor.fetchall()
        
        medicamentos = []
        for med in medicamentos_raw:
            # Buscar administrações
            cursor.execute("""
                SELECT id, data_hora_administracao, administrado, observacoes
                FROM administracao_medicamentos
                WHERE medicamento_prescrito_id = %s
                ORDER BY data_hora_administracao DESC
            """, (med[0],))
            
            administracoes = cursor.fetchall()
            
            administracoes_lista = []
            for adm in administracoes:
                administracoes_lista.append({
                    'id': adm[0],
                    'data_hora': adm[1],
                    'administrado': bool(adm[2]),
                    'observacoes': decode_bytes(adm[3]) if adm[3] else None
                })
            
            # Calcular próximos horários
            proximos_horarios = []
            if med[4] and med[5] and med[6] and med[7]:
                hoje = datetime.now()
                data_inicio = med[7]
                if isinstance(data_inicio, datetime):
                    data_inicio = data_inicio.date()
                
                data_fim = med[8] if med[8] else hoje.date() + timedelta(days=30)
                if isinstance(data_fim, datetime):
                    data_fim = data_fim.date()
                
                if data_inicio <= hoje.date() <= data_fim:
                    # Converter horários para time
                    horario_inicio = converter_para_time(med[5])
                    horario_fim = converter_para_time(med[6])
                    frequencia = med[4].lower()
                    
                    # Determinar intervalos baseado na frequência
                    intervalos = []
                    if '8/8' in frequencia or '8 em 8' in frequencia:
                        intervalos = [8, 16]
                    elif '12/12' in frequencia or '12 em 12' in frequencia:
                        intervalos = [12, 24]
                    elif '6/6' in frequencia or '6 em 6' in frequencia:
                        intervalos = [6, 12, 18]
                    elif '24/24' in frequencia or '1x' in frequencia:
                        intervalos = [24]
                    elif '12' in frequencia:
                        intervalos = [12, 24]
                    else:
                        intervalos = [12]
                    
                    # Gerar horários para hoje
                    for horas in intervalos:
                        horario = datetime.combine(hoje.date(), datetime.min.time()) + timedelta(hours=horas)
                        horario_time = horario.time()
                        
                        if horario_inicio and horario_fim:
                            if horario_time >= horario_inicio and horario_time <= horario_fim:
                                ja_administrado = any(
                                    adm['data_hora'].date() == horario.date() and 
                                    abs((adm['data_hora'] - horario).total_seconds()) < 3600
                                    for adm in administracoes_lista
                                )
                                if not ja_administrado and horario > datetime.now():
                                    proximos_horarios.append(horario.strftime('%H:%M'))
            
            # Usar a função formatar_hora para os horários
            horario_inicio_str = formatar_hora(med[5]) if med[5] else None
            horario_fim_str = formatar_hora(med[6]) if med[6] else None
            
            medicamentos.append({
                'id': med[0],
                'medicamento': decode_bytes(med[1]) if isinstance(med[1], bytes) else med[1],
                'dosagem': decode_bytes(med[2]) if isinstance(med[2], bytes) else med[2],
                'via': decode_bytes(med[3]) if isinstance(med[3], bytes) else med[3],
                'frequencia': decode_bytes(med[4]) if isinstance(med[4], bytes) else med[4],
                'horario_inicio': horario_inicio_str,
                'horario_fim': horario_fim_str,
                'data_inicio': med[7].strftime('%d/%m/%Y') if med[7] else None,
                'data_fim': med[8].strftime('%d/%m/%Y') if med[8] else 'Indeterminado',
                'observacoes': decode_bytes(med[9]) if med[9] else None,
                'status': decode_bytes(med[10]) if isinstance(med[10], bytes) else med[10],
                'medico_nome': decode_bytes(med[11]) if med[11] else 'Não informado',
                'administracoes': administracoes_lista,
                'proximos_horarios': proximos_horarios[:3]
            })
        
        cursor.close()
        
        # Estatísticas
        total_ativos = sum(1 for m in medicamentos if m['status'] == 'ativa')
        total_suspensos = sum(1 for m in medicamentos if m['status'] == 'suspensa')
        total_finalizados = sum(1 for m in medicamentos if m['status'] == 'finalizada')
        
        # Administrações do dia
        hoje_str = datetime.now().date()
        administracoes_hoje = sum(
            1 for m in medicamentos 
            for a in m['administracoes'] 
            if a['data_hora'].date() == hoje_str and a['administrado']
        )
        
        return render_template('enfermeiro/medicamentos_lista.html',
                               internacao=internacao_dados,
                               medicamentos=medicamentos,
                               total_ativos=total_ativos,
                               total_suspensos=total_suspensos,
                               total_finalizados=total_finalizados,
                               administracoes_hoje=administracoes_hoje,
                               user=session)
        
    except Exception as e:
        print(f"ERRO: {e}")
        print(traceback.format_exc())
        flash(str(e), "danger")
        return redirect(url_for("enfermeiro.dashboard.index"))

# ===================== ADMINISTRAR MEDICAMENTO =====================
@medicamentos_bp.route('/administrar/<int:medicamento_id>', methods=['POST'])
def administrar_medicamento(medicamento_id):
    """Registra administração de medicamento"""
    try:
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Não autorizado"}), 401
        
        enfermeiro_id = get_enfermeiro_id()
        if not enfermeiro_id:
            return jsonify({"success": False, "error": "Enfermeiro não encontrado"}), 404
        
        data = request.get_json()
        horario = data.get('horario')
        observacoes = data.get('observacoes', '')
        
        if not horario:
            return jsonify({"success": False, "error": "Horário não informado"}), 400
        
        data_hora = datetime.strptime(horario, '%Y-%m-%d %H:%M')
        
        cursor = mysql.connection.cursor()
        
        # Verificar se o medicamento existe e está ativo
        cursor.execute("""
            SELECT id, internacao_id, medicamento, dosagem, via
            FROM medicamentos_prescritos 
            WHERE id = %s AND status = 'ativa'
        """, (medicamento_id,))
        
        medicamento = cursor.fetchone()
        
        if not medicamento:
            cursor.close()
            return jsonify({"success": False, "error": "Medicamento não encontrado ou inativo"}), 404
        
        # Verificar se já foi administrado neste horário
        cursor.execute("""
            SELECT id FROM administracao_medicamentos
            WHERE medicamento_prescrito_id = %s 
            AND DATE(data_hora_administracao) = DATE(%s)
            AND HOUR(data_hora_administracao) = HOUR(%s)
        """, (medicamento_id, data_hora, data_hora))
        
        if cursor.fetchone():
            cursor.close()
            return jsonify({"success": False, "error": "Medicamento já administrado neste horário"}), 400
        
        # Registrar administração
        cursor.execute("""
            INSERT INTO administracao_medicamentos 
            (medicamento_prescrito_id, internacao_id, data_hora_administracao, 
             administrado, enfermeiro_id, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (medicamento_id, medicamento[1], data_hora, True, enfermeiro_id, observacoes))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({
            "success": True, 
            "message": f"{medicamento[2]} {medicamento[3]} administrado com sucesso!",
            "medicamento": medicamento[2],
            "dosagem": medicamento[3],
            "via": medicamento[4],
            "horario": data_hora.strftime('%H:%M')
        })
        
    except Exception as e:
        print(f"ERRO: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

# ===================== HISTÓRICO DE ADMINISTRAÇÕES =====================
@medicamentos_bp.route('/historico/<int:internacao_id>')
def historico_administracoes(internacao_id):
    """Histórico de administrações de medicamentos"""
    try:
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("auth.login"))
        
        cursor = mysql.connection.cursor()
        
        # Buscar dados da internação
        cursor.execute("""
            SELECT i.id, i.numero_prontuario, u.nome as paciente_nome
            FROM internacoes i
            JOIN pacientes p ON i.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE i.id = %s
        """, (internacao_id,))
        
        internacao = cursor.fetchone()
        
        if not internacao:
            flash("Internação não encontrada.", "danger")
            return redirect(url_for("enfermeiro.internados.listar_internados"))
        
        # Buscar histórico de administrações
        cursor.execute("""
            SELECT 
                am.id,
                am.data_hora_administracao,
                am.administrado,
                am.observacoes,
                mp.medicamento,
                mp.dosagem,
                mp.via,
                e.nome as enfermeiro_nome
            FROM administracao_medicamentos am
            JOIN medicamentos_prescritos mp ON am.medicamento_prescrito_id = mp.id
            LEFT JOIN enfermeiros enf ON am.enfermeiro_id = enf.id
            LEFT JOIN usuarios e ON enf.usuario_id = e.id
            WHERE am.internacao_id = %s
            ORDER BY am.data_hora_administracao DESC
        """, (internacao_id,))
        
        administracoes = cursor.fetchall()
        cursor.close()
        
        administracoes_lista = []
        for adm in administracoes:
            administracoes_lista.append({
                'id': adm[0],
                'data_hora': adm[1],
                'administrado': bool(adm[2]),
                'observacoes': decode_bytes(adm[3]) if adm[3] else None,
                'medicamento': decode_bytes(adm[4]) if isinstance(adm[4], bytes) else adm[4],
                'dosagem': decode_bytes(adm[5]) if isinstance(adm[5], bytes) else adm[5],
                'via': decode_bytes(adm[6]) if isinstance(adm[6], bytes) else adm[6],
                'enfermeiro_nome': decode_bytes(adm[7]) if adm[7] else 'Não informado'
            })
        
        internacao_dados = {
            'id': internacao[0],
            'prontuario': internacao[1],
            'paciente_nome': decode_bytes(internacao[2]) if isinstance(internacao[2], bytes) else internacao[2]
        }
        
        return render_template('enfermeiro/medicamentos_historico.html',
                               internacao=internacao_dados,
                               administracoes=administracoes_lista,
                               user=session)
        
    except Exception as e:
        print(f"ERRO: {e}")
        print(traceback.format_exc())
        flash(str(e), "danger")
        return redirect(url_for("enfermeiro.dashboard.index"))