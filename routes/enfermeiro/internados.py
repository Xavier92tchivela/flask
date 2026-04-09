# routes/enfermeiro/internados.py
from flask import Blueprint, render_template, session, flash, redirect, url_for, jsonify, request
from datetime import datetime, date
import traceback
import logging

logger = logging.getLogger(__name__)

# Cria o blueprint
internados_bp = Blueprint('internados', __name__, url_prefix='/internados')

# Variável global para o MySQL
mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL"""
    global mysql
    mysql = mysql_instance

# ===================== FUNÇÕES AUXILIARES =====================
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

def calcular_idade(data_nascimento):
    """Calcula idade a partir da data de nascimento"""
    if not data_nascimento:
        return None
    today = datetime.now().date()
    if isinstance(data_nascimento, datetime):
        birth_date = data_nascimento.date()
    else:
        birth_date = data_nascimento
    if isinstance(birth_date, str):
        try:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except:
            return None
    idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return idade

def formatar_data(data, formato='%d/%m/%Y %H:%M'):
    """Formata data de forma segura, verificando o tipo"""
    if data is None:
        return ''
    if isinstance(data, datetime):
        return data.strftime(formato)
    if isinstance(data, date):
        return data.strftime('%d/%m/%Y')
    if isinstance(data, str):
        return data
    return str(data)

def converter_valor_numerico(valor):
    """Converte valor para inteiro ou float, retorna None se vazio ou inválido"""
    if valor is None or valor == '':
        return None
    try:
        if '.' in str(valor):
            return float(valor)
        return int(valor)
    except:
        return None

# ===================== LISTAR PACIENTES INTERNADOS =====================
@internados_bp.route('/')
def listar_internados():
    """Lista todos os pacientes internados"""
    try:
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("auth.login"))
        
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT 
                i.id,
                i.numero_prontuario,
                i.data_internacao,
                i.tipo_internacao,
                i.diagnostico_inicial,
                i.observacoes,
                i.status,
                i.consulta_id,
                p.id as paciente_id,
                u.nome as paciente_nome,
                p.data_nascimento,
                p.telefone,
                l.id as leito_id,
                l.alas,
                l.numero as leito_numero,
                l.tipo as leito_tipo,
                m.id as medico_id,
                mu.nome as medico_nome,
                m.crm
            FROM internacoes i
            JOIN pacientes p ON i.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            LEFT JOIN leitos l ON i.leito_id = l.id
            LEFT JOIN medicos m ON i.medico_responsavel_id = m.id
            LEFT JOIN usuarios mu ON m.usuario_id = mu.id
            WHERE i.status = 'ativa'
            ORDER BY i.data_internacao DESC
        """
        
        cursor.execute(query)
        internacoes_raw = cursor.fetchall()
        
        internados_lista = []
        for internacao in internacoes_raw:
            idade = calcular_idade(internacao[10]) if len(internacao) > 10 else None
            
            # Buscar últimos sinais vitais
            ultimos_sinais = None
            consulta_id = internacao[7] if len(internacao) > 7 else None
            
            if consulta_id:
                try:
                    cursor.execute("""
                        SELECT pressao_arterial, frequencia_cardiaca, temperatura, 
                               saturacao_oxigenio, glicemia, data_afericao
                        FROM sinais_vitais
                        WHERE consulta_id = %s
                        ORDER BY data_afericao DESC
                        LIMIT 1
                    """, (consulta_id,))
                    
                    sinais_raw = cursor.fetchone()
                    if sinais_raw:
                        ultimos_sinais = {
                            'pressao_arterial': decode_bytes(sinais_raw[0]) if sinais_raw[0] else None,
                            'frequencia_cardiaca': sinais_raw[1],
                            'temperatura': sinais_raw[2],
                            'saturacao_oxigenio': sinais_raw[3],
                            'glicemia': sinais_raw[4],
                            'data_afericao': sinais_raw[5]
                        }
                except Exception as e:
                    print(f"Erro ao buscar sinais vitais: {e}")
            
            internados_lista.append({
                'id': internacao[0],
                'numero_prontuario': internacao[1],
                'data_internacao': internacao[2],
                'tipo_internacao': decode_bytes(internacao[3]) if isinstance(internacao[3], bytes) else internacao[3] or 'Não informado',
                'diagnostico_inicial': decode_bytes(internacao[4]) if internacao[4] else 'Não informado',
                'observacoes': decode_bytes(internacao[5]) if internacao[5] else None,
                'status': decode_bytes(internacao[6]) if isinstance(internacao[6], bytes) else internacao[6],
                'consulta_id': internacao[7],
                'paciente_id': internacao[8],
                'paciente_nome': decode_bytes(internacao[9]) if isinstance(internacao[9], bytes) else internacao[9],
                'idade': idade,
                'telefone': decode_bytes(internacao[11]) if len(internacao) > 11 and internacao[11] else None,
                'leito_id': internacao[12] if len(internacao) > 12 else None,
                'leito_alas': decode_bytes(internacao[13]) if len(internacao) > 13 and internacao[13] else 'Não definido',
                'leito_numero': internacao[14] if len(internacao) > 14 else '?',
                'leito_tipo': decode_bytes(internacao[15]) if len(internacao) > 15 and internacao[15] else 'Não definido',
                'medico_id': internacao[16] if len(internacao) > 16 else None,
                'medico_nome': decode_bytes(internacao[17]) if len(internacao) > 17 and internacao[17] else 'Não informado',
                'medico_crm': decode_bytes(internacao[18]) if len(internacao) > 18 and internacao[18] else '---',
                'ultimos_sinais': ultimos_sinais
            })
        
        cursor.close()
        
        # Contar total de internados
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM internacoes WHERE status = 'ativa'")
        total_internados = cursor.fetchone()[0] or 0
        cursor.close()
        
        return render_template(
            'enfermeiro/internados.html',
            internados_lista=internados_lista,
            total_internados=total_internados,
            user=session
        )
        
    except Exception as e:
        print(f"ERRO em listar_internados: {e}")
        print(traceback.format_exc())
        flash(str(e), "danger")
        return redirect(url_for("enfermeiro.dashboard.index"))

# ===================== DETALHES DA INTERNAÇÃO =====================
@internados_bp.route('/<int:internacao_id>')
def detalhes_internacao(internacao_id):
    """Detalhes da internação"""
    try:
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("auth.login"))
        
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT 
                i.id,
                i.numero_prontuario,
                i.data_internacao,
                i.tipo_internacao,
                i.diagnostico_inicial,
                i.diagnostico_final,
                i.observacoes,
                i.status,
                i.consulta_id,
                p.id as paciente_id,
                u.nome as paciente_nome,
                p.data_nascimento,
                p.telefone,
                p.endereco,
                p.alergias,
                p.medicamentos_uso,
                p.historico_doencas,
                p.contato_emergencia,
                l.id as leito_id,
                l.alas,
                l.numero as leito_numero,
                l.tipo as leito_tipo,
                m.id as medico_id,
                mu.nome as medico_nome,
                m.crm
            FROM internacoes i
            JOIN pacientes p ON i.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            LEFT JOIN leitos l ON i.leito_id = l.id
            LEFT JOIN medicos m ON i.medico_responsavel_id = m.id
            LEFT JOIN usuarios mu ON m.usuario_id = mu.id
            WHERE i.id = %s
        """
        
        cursor.execute(query, (internacao_id,))
        internacao_raw = cursor.fetchone()
        
        if not internacao_raw:
            flash("Internação não encontrada.", "danger")
            return redirect(url_for("enfermeiro.dashboard.index"))
        
        # Buscar sinais vitais
        consulta_id = internacao_raw[8]
        sinais_vitais = []
        
        if consulta_id:
            cursor.execute("""
                SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                       temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao
                FROM sinais_vitais
                WHERE consulta_id = %s
                ORDER BY data_afericao DESC
            """, (consulta_id,))
            
            sinais_raw = cursor.fetchall()
            for s in sinais_raw:
                sinais_vitais.append({
                    'id': s[0],
                    'pressao_arterial': decode_bytes(s[1]) if s[1] else None,
                    'frequencia_cardiaca': s[2],
                    'frequencia_respiratoria': s[3],
                    'temperatura': s[4],
                    'saturacao_oxigenio': s[5],
                    'glicemia': s[6],
                    'peso': s[7],
                    'observacoes': decode_bytes(s[8]) if s[8] else None,
                    'data_afericao': s[9]
                })
        
        cursor.close()
        
        internacao = {
            'id': internacao_raw[0],
            'numero_prontuario': internacao_raw[1],
            'data_internacao': internacao_raw[2],
            'tipo_internacao': decode_bytes(internacao_raw[3]) if isinstance(internacao_raw[3], bytes) else internacao_raw[3],
            'diagnostico_inicial': decode_bytes(internacao_raw[4]) if internacao_raw[4] else None,
            'diagnostico_final': decode_bytes(internacao_raw[5]) if internacao_raw[5] else None,
            'observacoes': decode_bytes(internacao_raw[6]) if internacao_raw[6] else None,
            'status': decode_bytes(internacao_raw[7]) if isinstance(internacao_raw[7], bytes) else internacao_raw[7],
            'consulta_id': internacao_raw[8],
            'paciente_id': internacao_raw[9],
            'paciente_nome': decode_bytes(internacao_raw[10]) if isinstance(internacao_raw[10], bytes) else internacao_raw[10],
            'data_nascimento': internacao_raw[11],
            'telefone': decode_bytes(internacao_raw[12]) if internacao_raw[12] else None,
            'endereco': decode_bytes(internacao_raw[13]) if internacao_raw[13] else None,
            'alergias': decode_bytes(internacao_raw[14]) if internacao_raw[14] else None,
            'medicamentos_uso': decode_bytes(internacao_raw[15]) if internacao_raw[15] else None,
            'historico_doencas': decode_bytes(internacao_raw[16]) if internacao_raw[16] else None,
            'contato_emergencia': decode_bytes(internacao_raw[17]) if internacao_raw[17] else None,
            'leito_alas': decode_bytes(internacao_raw[19]) if internacao_raw[19] else 'Não definido',
            'leito_numero': internacao_raw[20] if internacao_raw[20] else '?',
            'leito_tipo': decode_bytes(internacao_raw[21]) if internacao_raw[21] else 'Não definido',
            'medico_nome': decode_bytes(internacao_raw[23]) if internacao_raw[23] else 'Não informado',
            'medico_crm': decode_bytes(internacao_raw[24]) if internacao_raw[24] else '---',
            'sinais_vitais': sinais_vitais
        }
        
        # Calcular idade
        if internacao['data_nascimento']:
            internacao['idade'] = calcular_idade(internacao['data_nascimento'])
        else:
            internacao['idade'] = None
        
        return render_template(
            'enfermeiro/detalhes_internacao.html',
            internacao=internacao,
            user=session
        )
        
    except Exception as e:
        print(f"ERRO em detalhes_internacao: {e}")
        print(traceback.format_exc())
        flash(str(e), "danger")
        return redirect(url_for("enfermeiro.dashboard.index"))

# ===================== REGISTRAR SINAIS VITAIS =====================
@internados_bp.route('/registrar-sinais/<int:paciente_id>/<int:internacao_id>')
def registrar_sinais_vitais(paciente_id, internacao_id):
    """Registrar sinais vitais para paciente internado"""
    try:
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("auth.login"))
        
        cursor = mysql.connection.cursor()
        
        # Buscar dados do paciente
        cursor.execute("""
            SELECT u.nome FROM pacientes p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.id = %s
        """, (paciente_id,))
        paciente = cursor.fetchone()
        
        # Buscar dados da internação
        cursor.execute("""
            SELECT numero_prontuario, consulta_id FROM internacoes 
            WHERE id = %s
        """, (internacao_id,))
        internacao = cursor.fetchone()
        cursor.close()
        
        paciente_nome = decode_bytes(paciente[0]) if paciente else "Paciente"
        numero_prontuario = internacao[0] if internacao else "N/A"
        consulta_id = internacao[1] if internacao else None
        
        return render_template(
            'enfermeiro/registrar_sinais_vitais.html',
            paciente_id=paciente_id,
            internacao_id=internacao_id,
            consulta_id=consulta_id,
            paciente_nome=paciente_nome,
            numero_prontuario=numero_prontuario,
            user=session
        )
        
    except Exception as e:
        print(f"ERRO: {e}")
        print(traceback.format_exc())
        flash(str(e), "danger")
        return redirect(url_for("enfermeiro.dashboard.index"))

# ===================== SALVAR SINAIS VITAIS =====================
@internados_bp.route('/salvar-sinais', methods=['POST'])
def salvar_sinais_vitais():
    """Salvar sinais vitais do paciente internado"""
    try:
        if 'user_id' not in session:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("auth.login"))
        
        paciente_id = request.form.get('paciente_id')
        internacao_id = request.form.get('internacao_id')
        consulta_id = request.form.get('consulta_id')
        
        # ===================== CORREÇÃO: CONVERTER VALORES VAZIOS PARA NONE =====================
        pressao_arterial = request.form.get('pressao_arterial')
        if pressao_arterial == '':
            pressao_arterial = None
        
        frequencia_cardiaca = request.form.get('frequencia_cardiaca')
        if frequencia_cardiaca == '':
            frequencia_cardiaca = None
        else:
            try:
                frequencia_cardiaca = int(frequencia_cardiaca)
            except:
                frequencia_cardiaca = None
        
        frequencia_respiratoria = request.form.get('frequencia_respiratoria')
        if frequencia_respiratoria == '':
            frequencia_respiratoria = None
        else:
            try:
                frequencia_respiratoria = int(frequencia_respiratoria)
            except:
                frequencia_respiratoria = None
        
        temperatura = request.form.get('temperatura')
        if temperatura == '':
            temperatura = None
        else:
            try:
                temperatura = float(temperatura)
            except:
                temperatura = None
        
        saturacao_oxigenio = request.form.get('saturacao_oxigenio')
        if saturacao_oxigenio == '':
            saturacao_oxigenio = None
        else:
            try:
                saturacao_oxigenio = int(saturacao_oxigenio)
            except:
                saturacao_oxigenio = None
        
        glicemia = request.form.get('glicemia')
        if glicemia == '':
            glicemia = None
        else:
            try:
                glicemia = int(glicemia)
            except:
                glicemia = None
        
        peso = request.form.get('peso')
        if peso == '':
            peso = None
        else:
            try:
                peso = float(peso)
            except:
                peso = None
        
        observacoes = request.form.get('observacoes')
        
        cursor = mysql.connection.cursor()
        
        # Inserir sinais vitais
        cursor.execute("""
            INSERT INTO sinais_vitais 
            (consulta_id, data_afericao, pressao_arterial, frequencia_cardiaca, 
             frequencia_respiratoria, temperatura, saturacao_oxigenio, 
             glicemia, peso, observacoes, enfermeiro_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (consulta_id, datetime.now(), pressao_arterial, frequencia_cardiaca,
              frequencia_respiratoria, temperatura, saturacao_oxigenio,
              glicemia, peso, observacoes, session.get('enfermeiro_id')))
        
        mysql.connection.commit()
        cursor.close()
        
        flash("Sinais vitais registrados com sucesso!", "success")
        return redirect(url_for('enfermeiro.internados.detalhes_internacao', internacao_id=internacao_id))
        
    except Exception as e:
        print(f"ERRO: {e}")
        print(traceback.format_exc())
        flash(f"Erro ao registrar sinais vitais: {str(e)}", "danger")
        return redirect(request.referrer or url_for("enfermeiro.dashboard.index"))

# ===================== DAR ALTA =====================
@internados_bp.route('/<int:internacao_id>/alta', methods=['POST'])
def dar_alta(internacao_id):
    """Dar alta ao paciente internado"""
    try:
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Não autorizado"}), 401
        
        data = request.get_json()
        diagnostico_final = data.get('diagnostico_final', '')
        observacoes_alta = data.get('observacoes_alta', '')
        
        cursor = mysql.connection.cursor()
        
        # Verificar se a internação existe
        cursor.execute("""
            SELECT id, leito_id, consulta_id FROM internacoes 
            WHERE id = %s AND status = 'ativa'
        """, (internacao_id,))
        internacao = cursor.fetchone()
        
        if not internacao:
            cursor.close()
            return jsonify({"success": False, "error": "Internação não encontrada ou já encerrada"}), 404
        
        leito_id = internacao[1]
        consulta_id = internacao[2]
        
        # Atualizar internação
        cursor.execute("""
            UPDATE internacoes 
            SET status = 'alta', 
                data_alta = %s,
                diagnostico_final = %s,
                observacoes = %s
            WHERE id = %s
        """, (datetime.now(), diagnostico_final, observacoes_alta, internacao_id))
        
        # Liberar leito
        cursor.execute("UPDATE leitos SET status = 'disponivel' WHERE id = %s", (leito_id,))
        
        # Atualizar status da consulta
        if consulta_id:
            cursor.execute("UPDATE consultas SET status = 'realizada' WHERE id = %s", (consulta_id,))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({"success": True, "message": "Alta realizada com sucesso!"})
        
    except Exception as e:
        print(f"ERRO em dar_alta: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500