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
    try:
        today = datetime.now().date()
        if isinstance(data_nascimento, datetime):
            birth_date = data_nascimento.date()
        elif isinstance(data_nascimento, date):
            birth_date = data_nascimento
        elif isinstance(data_nascimento, str):
            birth_date = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
        else:
            return None
        
        idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return idade
    except Exception as e:
        logger.error(f"Erro ao calcular idade: {e}")
        return None

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
        
        # CORREÇÃO: Usar cursor com dictionary=True
        cursor = mysql.connection.cursor(dictionary=True)
        
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
            # CORREÇÃO: Acessar por nome da coluna em vez de índice
            idade = calcular_idade(internacao.get('data_nascimento'))
            
            # Buscar últimos sinais vitais
            ultimos_sinais = None
            consulta_id = internacao.get('consulta_id')
            
            if consulta_id:
                try:
                    cursor_sinais = mysql.connection.cursor(dictionary=True)
                    cursor_sinais.execute("""
                        SELECT pressao_arterial, frequencia_cardiaca, temperatura, 
                               saturacao_oxigenio, glicemia, data_afericao
                        FROM sinais_vitais
                        WHERE consulta_id = %s
                        ORDER BY data_afericao DESC
                        LIMIT 1
                    """, (consulta_id,))
                    
                    sinais_raw = cursor_sinais.fetchone()
                    cursor_sinais.close()
                    
                    if sinais_raw:
                        ultimos_sinais = {
                            'pressao_arterial': decode_bytes(sinais_raw.get('pressao_arterial')),
                            'frequencia_cardiaca': sinais_raw.get('frequencia_cardiaca'),
                            'temperatura': sinais_raw.get('temperatura'),
                            'saturacao_oxigenio': sinais_raw.get('saturacao_oxigenio'),
                            'glicemia': sinais_raw.get('glicemia'),
                            'data_afericao': sinais_raw.get('data_afericao')
                        }
                except Exception as e:
                    logger.error(f"Erro ao buscar sinais vitais: {e}")
            
            internados_lista.append({
                'id': internacao.get('id'),
                'numero_prontuario': internacao.get('numero_prontuario') or 'N/A',
                'data_internacao': internacao.get('data_internacao'),
                'tipo_internacao': decode_bytes(internacao.get('tipo_internacao')) or 'Não informado',
                'diagnostico_inicial': decode_bytes(internacao.get('diagnostico_inicial')) or 'Não informado',
                'observacoes': decode_bytes(internacao.get('observacoes')),
                'status': decode_bytes(internacao.get('status')),
                'consulta_id': internacao.get('consulta_id'),
                'paciente_id': internacao.get('paciente_id'),
                'paciente_nome': decode_bytes(internacao.get('paciente_nome')),
                'idade': idade,
                'telefone': decode_bytes(internacao.get('telefone')),
                'leito_id': internacao.get('leito_id'),
                'leito_alas': decode_bytes(internacao.get('alas')) or 'Não definido',
                'leito_numero': internacao.get('leito_numero') or '?',
                'leito_tipo': decode_bytes(internacao.get('leito_tipo')) or 'Não definido',
                'medico_id': internacao.get('medico_id'),
                'medico_nome': decode_bytes(internacao.get('medico_nome')) or 'Não informado',
                'medico_crm': decode_bytes(internacao.get('crm')) or '---',
                'ultimos_sinais': ultimos_sinais
            })
        
        cursor.close()
        
        # Contar total de internados
        cursor_count = mysql.connection.cursor(dictionary=True)
        cursor_count.execute("SELECT COUNT(*) as total FROM internacoes WHERE status = 'ativa'")
        total_result = cursor_count.fetchone()
        total_internados = total_result['total'] if total_result else 0
        cursor_count.close()
        
        return render_template(
            'enfermeiro/internados.html',
            internados_lista=internados_lista,
            total_internados=total_internados,
            user=session
        )
        
    except Exception as e:
        logger.error(f"ERRO em listar_internados: {e}")
        logger.error(traceback.format_exc())
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
        
        cursor = mysql.connection.cursor(dictionary=True)
        
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
        consulta_id = internacao_raw.get('consulta_id')
        sinais_vitais = []
        
        if consulta_id:
            cursor_sinais = mysql.connection.cursor(dictionary=True)
            cursor_sinais.execute("""
                SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                       temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao
                FROM sinais_vitais
                WHERE consulta_id = %s
                ORDER BY data_afericao DESC
            """, (consulta_id,))
            
            sinais_raw = cursor_sinais.fetchall()
            cursor_sinais.close()
            
            for s in sinais_raw:
                sinais_vitais.append({
                    'id': s.get('id'),
                    'pressao_arterial': decode_bytes(s.get('pressao_arterial')),
                    'frequencia_cardiaca': s.get('frequencia_cardiaca'),
                    'frequencia_respiratoria': s.get('frequencia_respiratoria'),
                    'temperatura': s.get('temperatura'),
                    'saturacao_oxigenio': s.get('saturacao_oxigenio'),
                    'glicemia': s.get('glicemia'),
                    'peso': s.get('peso'),
                    'observacoes': decode_bytes(s.get('observacoes')),
                    'data_afericao': s.get('data_afericao')
                })
        
        cursor.close()
        
        internacao = {
            'id': internacao_raw.get('id'),
            'numero_prontuario': internacao_raw.get('numero_prontuario'),
            'data_internacao': internacao_raw.get('data_internacao'),
            'tipo_internacao': decode_bytes(internacao_raw.get('tipo_internacao')),
            'diagnostico_inicial': decode_bytes(internacao_raw.get('diagnostico_inicial')),
            'diagnostico_final': decode_bytes(internacao_raw.get('diagnostico_final')),
            'observacoes': decode_bytes(internacao_raw.get('observacoes')),
            'status': decode_bytes(internacao_raw.get('status')),
            'consulta_id': internacao_raw.get('consulta_id'),
            'paciente_id': internacao_raw.get('paciente_id'),
            'paciente_nome': decode_bytes(internacao_raw.get('paciente_nome')),
            'data_nascimento': internacao_raw.get('data_nascimento'),
            'telefone': decode_bytes(internacao_raw.get('telefone')),
            'endereco': decode_bytes(internacao_raw.get('endereco')),
            'alergias': decode_bytes(internacao_raw.get('alergias')),
            'medicamentos_uso': decode_bytes(internacao_raw.get('medicamentos_uso')),
            'historico_doencas': decode_bytes(internacao_raw.get('historico_doencas')),
            'contato_emergencia': decode_bytes(internacao_raw.get('contato_emergencia')),
            'leito_alas': decode_bytes(internacao_raw.get('alas')) or 'Não definido',
            'leito_numero': internacao_raw.get('leito_numero') or '?',
            'leito_tipo': decode_bytes(internacao_raw.get('leito_tipo')) or 'Não definido',
            'medico_nome': decode_bytes(internacao_raw.get('medico_nome')) or 'Não informado',
            'medico_crm': decode_bytes(internacao_raw.get('crm')) or '---',
            'sinais_vitais': sinais_vitais
        }
        
        # Calcular idade
        internacao['idade'] = calcular_idade(internacao_raw.get('data_nascimento'))
        
        return render_template(
            'enfermeiro/detalhes_internacao.html',
            internacao=internacao,
            user=session
        )
        
    except Exception as e:
        logger.error(f"ERRO em detalhes_internacao: {e}")
        logger.error(traceback.format_exc())
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
        
        cursor = mysql.connection.cursor(dictionary=True)
        
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
        
        paciente_nome = decode_bytes(paciente['nome']) if paciente else "Paciente"
        numero_prontuario = internacao['numero_prontuario'] if internacao else "N/A"
        consulta_id = internacao['consulta_id'] if internacao else None
        
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
        logger.error(f"ERRO em registrar_sinais_vitais: {e}")
        logger.error(traceback.format_exc())
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
        
        # Converter valores
        pressao_arterial = request.form.get('pressao_arterial') or None
        
        frequencia_cardiaca = request.form.get('frequencia_cardiaca')
        frequencia_cardiaca = int(frequencia_cardiaca) if frequencia_cardiaca and frequencia_cardiaca.strip() else None
        
        frequencia_respiratoria = request.form.get('frequencia_respiratoria')
        frequencia_respiratoria = int(frequencia_respiratoria) if frequencia_respiratoria and frequencia_respiratoria.strip() else None
        
        temperatura = request.form.get('temperatura')
        temperatura = float(temperatura) if temperatura and temperatura.strip() else None
        
        saturacao_oxigenio = request.form.get('saturacao_oxigenio')
        saturacao_oxigenio = int(saturacao_oxigenio) if saturacao_oxigenio and saturacao_oxigenio.strip() else None
        
        glicemia = request.form.get('glicemia')
        glicemia = int(glicemia) if glicemia and glicemia.strip() else None
        
        peso = request.form.get('peso')
        peso = float(peso) if peso and peso.strip() else None
        
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
        logger.error(f"ERRO em salvar_sinais_vitais: {e}")
        logger.error(traceback.format_exc())
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
        
        cursor = mysql.connection.cursor(dictionary=True)
        
        # Verificar se a internação existe
        cursor.execute("""
            SELECT id, leito_id, consulta_id FROM internacoes 
            WHERE id = %s AND status = 'ativa'
        """, (internacao_id,))
        internacao = cursor.fetchone()
        
        if not internacao:
            cursor.close()
            return jsonify({"success": False, "error": "Internação não encontrada ou já encerrada"}), 404
        
        leito_id = internacao.get('leito_id')
        consulta_id = internacao.get('consulta_id')
        
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
        if leito_id:
            cursor.execute("UPDATE leitos SET status = 'disponivel' WHERE id = %s", (leito_id,))
        
        # Atualizar status da consulta
        if consulta_id:
            cursor.execute("UPDATE consultas SET status = 'realizada' WHERE id = %s", (consulta_id,))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({"success": True, "message": "Alta realizada com sucesso!"})
        
    except Exception as e:
        logger.error(f"ERRO em dar_alta: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
