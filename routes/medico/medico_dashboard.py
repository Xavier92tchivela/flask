# routes/medico/__init__.py (VERSÃO CORRIGIDA - SEM ROTA DUPLICADA)
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
import logging
import traceback
from .base import init_medico_base
from .medico_dashboard import init_medico_dashboard
from .medico_pedidos import init_medico_pedidos
from .medico_perfil import init_medico_perfil
from .medico_consultas import init_medico_consultas
from .medico_pacientes import init_medico_pacientes
from .medico_api import init_medico_api
from .medico_debug import init_medico_debug
from .medico_receitas import init_medico_receitas
from .consulta import create_consulta_blueprint
from .medico_receita_digital import init_medico_receita_digital
from datetime import datetime, date
from functools import wraps

logger = logging.getLogger(__name__)

def init_medico(mysql, client, gemini_available, MODEL_NAME, app, receita_service=None):
    """
    Inicializa e retorna o blueprint completo do médico
    """
    try:
        print("\n" + "="*50)
        print("INICIALIZANDO BLUEPRINT MÉDICO")
        print("="*50)
        
        medico_bp = Blueprint('medico', __name__, url_prefix='/medico')
        
        # ===================== FUNÇÕES AUXILIARES =====================
        def garantir_string(valor):
            """Converte bytes para string"""
            if valor is None:
                return ''
            if isinstance(valor, bytes):
                try:
                    return valor.decode('utf-8')
                except:
                    return str(valor)
            return str(valor)
        
        def formatar_data(data, formato='%d/%m/%Y %H:%M'):
            """Formata data"""
            if not data:
                return ''
            if isinstance(data, (datetime, date)):
                return data.strftime(formato)
            return str(data)
        
        def obter_medico_id():
            """Busca o ID do médico baseado no usuário logado"""
            if session.get('medico_id'):
                return session['medico_id']
            
            if 'user_id' not in session:
                return None
            
            try:
                cur = mysql.connection.cursor()
                cur.execute("SELECT id FROM medicos WHERE usuario_id = %s", (session['user_id'],))
                resultado = cur.fetchone()
                cur.close()
                
                if resultado:
                    medico_id = resultado[0]
                    session['medico_id'] = medico_id
                    return medico_id
                return None
            except Exception as e:
                logger.error(f"Erro ao obter medico_id: {e}")
                return None
        
        # ===================== DECORADOR DE AUTENTICAÇÃO =====================
        def medico_required(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    flash('Faça login para acessar.', 'warning')
                    return redirect(url_for('auth.login'))
                if session.get('user_type') != 'medico':
                    flash('Acesso restrito a médicos.', 'danger')
                    return redirect(url_for('auth.login'))
                return f(*args, **kwargs)
            return decorated_function
        
        # Inicializar funções base
        base = init_medico_base(mysql)
        
        # ADICIONAR AS FUNÇÕES AO BASE PARA OS MÓDULOS ACESSAREM
        base['medico_required'] = medico_required
        base['garantir_string'] = garantir_string
        base['formatar_data'] = formatar_data
        base['obter_medico_id'] = obter_medico_id
        
        # ===================== FUNÇÃO AUXILIAR DECODE BYTES =====================
        def decode_bytes(value):
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                try:
                    return value.decode('utf-8')
                except:
                    return str(value)
            return value
        
        # ===================== ROTAS (EXCETO DASHBOARD - JÁ NO MÓDULO) =====================
        
        # ROTA: LISTAR INTERNADOS
        @medico_bp.route('/internados')
        @medico_required
        def internados():
            """Lista pacientes internados do médico"""
            try:
                medico_info = base['obter_info_medico']()
                if not medico_info:
                    flash("Médico não encontrado.", "danger")
                    return redirect(url_for("auth.login"))
                
                medico_id = medico_info.get('id')
                
                cursor = mysql.connection.cursor()
                
                cursor.execute("""
                    SELECT 
                        i.id,
                        i.numero_prontuario,
                        i.data_internacao,
                        i.tipo_internacao,
                        i.diagnostico_inicial,
                        i.status,
                        i.leito_id,
                        p.id as paciente_id,
                        u.nome as paciente_nome,
                        p.data_nascimento,
                        l.alas,
                        l.numero as leito_numero,
                        l.tipo as leito_tipo
                    FROM internacoes i
                    JOIN pacientes p ON i.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    LEFT JOIN leitos l ON i.leito_id = l.id
                    WHERE i.medico_responsavel_id = %s AND i.status = 'ativa'
                    ORDER BY i.data_internacao DESC
                """, (medico_id,))
                
                internados = cursor.fetchall()
                
                cursor.execute("SELECT COUNT(*) FROM leitos WHERE status = 'ocupado'")
                leitos_ocupados = cursor.fetchone()[0] or 0
                
                cursor.execute("SELECT COUNT(*) FROM leitos")
                total_leitos = cursor.fetchone()[0] or 0
                cursor.close()
                
                internados_lista = []
                for internado in internados:
                    idade = None
                    if internado[9]:
                        data_nasc = internado[9]
                        if isinstance(data_nasc, datetime):
                            birth_date = data_nasc.date()
                        else:
                            birth_date = data_nasc
                        today = datetime.now().date()
                        idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    
                    internados_lista.append({
                        'id': internado[0],
                        'numero_prontuario': internado[1],
                        'data_internacao': internado[2],
                        'tipo_internacao': decode_bytes(internado[3]) if internado[3] else 'Não informado',
                        'diagnostico_inicial': decode_bytes(internado[4]) if internado[4] else 'Não informado',
                        'status': internado[5],
                        'paciente_id': internado[6],
                        'paciente_nome': decode_bytes(internado[7]) if internado[7] else 'Paciente',
                        'idade': idade,
                        'leito_alas': decode_bytes(internado[10]) if internado[10] else 'Não definido',
                        'leito_numero': internado[11] if internado[11] else '?',
                        'leito_tipo': decode_bytes(internado[12]) if internado[12] else 'Não definido'
                    })
                
                return render_template(
                    'medico/internados.html',
                    pacientes_internados_lista=internados_lista,
                    leitos_ocupados=leitos_ocupados,
                    total_leitos=total_leitos,
                    user=session
                )
                
            except Exception as e:
                logger.error(f"Erro: {e}")
                logger.error(traceback.format_exc())
                flash(str(e), "danger")
                return redirect(url_for("medico.dashboard"))
        
        # ROTA: PRESCREVER MEDICAMENTO
        @medico_bp.route('/prescrever-medicamento/<int:internacao_id>')
        @medico_required
        def prescrever_medicamento(internacao_id):
            """Página para prescrever medicamento"""
            try:
                medico_info = base['obter_info_medico']()
                if not medico_info:
                    flash("Médico não encontrado.", "danger")
                    return redirect(url_for("auth.login"))
                
                cursor = mysql.connection.cursor()
                
                cursor.execute("""
                    SELECT i.id, i.numero_prontuario, u.nome as paciente_nome,
                           p.data_nascimento
                    FROM internacoes i
                    JOIN pacientes p ON i.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE i.id = %s AND i.medico_responsavel_id = %s
                """, (internacao_id, medico_info['id']))
                
                internacao = cursor.fetchone()
                cursor.close()
                
                if not internacao:
                    flash("Internação não encontrada.", "danger")
                    return redirect(url_for("medico.internados"))
                
                hoje = datetime.now().strftime('%Y-%m-%d')
                
                return render_template(
                    'medico/prescrever_medicamento.html',
                    internacao=internacao,
                    internacao_id=internacao_id,
                    hoje=hoje,
                    user=session
                )
                
            except Exception as e:
                logger.error(f"Erro: {e}")
                logger.error(traceback.format_exc())
                flash(str(e), "danger")
                return redirect(url_for("medico.dashboard"))
        
        # ROTA: SALVAR PRESCRIÇÃO
        @medico_bp.route('/api/prescrever-medicamento', methods=['POST'])
        @medico_required
        def salvar_prescricao():
            """Salvar prescrição de medicamento"""
            try:
                medico_info = base['obter_info_medico']()
                if not medico_info:
                    return jsonify({"success": False, "error": "Não autorizado"}), 401
                
                data = request.get_json()
                internacao_id = data.get('internacao_id')
                medicamento = data.get('medicamento')
                dosagem = data.get('dosagem')
                via = data.get('via')
                frequencia = data.get('frequencia')
                horario_inicio = data.get('horario_inicio')
                horario_fim = data.get('horario_fim')
                data_inicio = data.get('data_inicio')
                data_fim = data.get('data_fim')
                observacoes = data.get('observacoes', '')
                
                if not all([internacao_id, medicamento, dosagem, via, frequencia, data_inicio]):
                    return jsonify({"success": False, "error": "Preencha todos os campos obrigatórios"}), 400
                
                cursor = mysql.connection.cursor()
                
                cursor.execute("""
                    INSERT INTO medicamentos_prescritos 
                    (internacao_id, medicamento, dosagem, via, frequencia, 
                     horario_inicio, horario_fim, data_inicio, data_fim, 
                     observacoes, status, medico_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ativa', %s)
                """, (internacao_id, medicamento, dosagem, via, frequencia,
                      horario_inicio, horario_fim, data_inicio, data_fim,
                      observacoes, medico_info['id']))
                
                mysql.connection.commit()
                cursor.close()
                
                return jsonify({"success": True, "message": "Medicamento prescrito com sucesso!"})
                
            except Exception as e:
                logger.error(f"Erro: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"success": False, "error": str(e)}), 500
        
        # ROTA: LISTAR PRESCRIÇÕES
        @medico_bp.route('/prescricoes/<int:internacao_id>')
        @medico_required
        def listar_prescricoes(internacao_id):
            """Lista medicamentos prescritos para um paciente internado"""
            try:
                medico_info = base['obter_info_medico']()
                if not medico_info:
                    flash("Médico não encontrado.", "danger")
                    return redirect(url_for("auth.login"))
                
                cursor = mysql.connection.cursor()
                
                cursor.execute("""
                    SELECT i.id, i.numero_prontuario, u.nome as paciente_nome
                    FROM internacoes i
                    JOIN pacientes p ON i.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE i.id = %s AND i.medico_responsavel_id = %s
                """, (internacao_id, medico_info['id']))
                
                internacao = cursor.fetchone()
                
                if not internacao:
                    flash("Internação não encontrada.", "danger")
                    return redirect(url_for("medico.internados"))
                
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
                        mp.created_at
                    FROM medicamentos_prescritos mp
                    WHERE mp.internacao_id = %s
                    ORDER BY mp.created_at DESC
                """, (internacao_id,))
                
                prescricoes_raw = cursor.fetchall()
                cursor.close()
                
                prescricoes = []
                for p in prescricoes_raw:
                    prescricoes.append({
                        'id': p[0],
                        'medicamento': decode_bytes(p[1]) if p[1] else '-',
                        'dosagem': decode_bytes(p[2]) if p[2] else '-',
                        'via': decode_bytes(p[3]) if p[3] else '-',
                        'frequencia': decode_bytes(p[4]) if p[4] else '-',
                        'horario_inicio': p[5].strftime('%H:%M') if p[5] else '-',
                        'horario_fim': p[6].strftime('%H:%M') if p[6] else '-',
                        'data_inicio': p[7].strftime('%d/%m/%Y') if p[7] else '-',
                        'data_fim': p[8].strftime('%d/%m/%Y') if p[8] else 'Indeterminado',
                        'observacoes': decode_bytes(p[9]) if p[9] else None,
                        'status': decode_bytes(p[10]) if p[10] else 'ativa',
                        'created_at': p[11].strftime('%d/%m/%Y %H:%M') if p[11] else '-'
                    })
                
                return render_template(
                    'medico/prescricoes.html',
                    internacao_id=internacao_id,
                    internacao=internacao,
                    prescricoes=prescricoes,
                    user=session
                )
                
            except Exception as e:
                logger.error(f"Erro: {e}")
                logger.error(traceback.format_exc())
                flash(str(e), "danger")
                return redirect(url_for("medico.dashboard"))
        
        # ROTA: SUSPENDER PRESCRIÇÃO
        @medico_bp.route('/api/suspender-prescricao/<int:prescricao_id>', methods=['POST'])
        @medico_required
        def suspender_prescricao(prescricao_id):
            """Suspender uma prescrição de medicamento"""
            try:
                medico_info = base['obter_info_medico']()
                if not medico_info:
                    return jsonify({"success": False, "error": "Não autorizado"}), 401
                
                cursor = mysql.connection.cursor()
                cursor.execute("""
                    UPDATE medicamentos_prescritos 
                    SET status = 'suspensa' 
                    WHERE id = %s
                """, (prescricao_id,))
                
                mysql.connection.commit()
                cursor.close()
                
                return jsonify({"success": True, "message": "Prescrição suspensa com sucesso!"})
                
            except Exception as e:
                logger.error(f"Erro: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"success": False, "error": str(e)}), 500
        
        # ===================== LISTA DE MÓDULOS EXISTENTES =====================
        # O módulo init_medico_dashboard vai registrar a rota /dashboard
        modules = [
            init_medico_dashboard(base),  # Este vai registrar a rota /dashboard
            init_medico_pedidos(base, gemini_available),
            init_medico_perfil(base),
            init_medico_consultas(base),
            init_medico_pacientes(mysql, base),
            init_medico_api(mysql, base),
            init_medico_debug(base),
        ]
        
        # Inicializar módulo de receitas
        if receita_service:
            try:
                receitas_module = init_medico_receitas(mysql, base, receita_service, gemini_available)
                modules.append(receitas_module)
                logger.info(f"Módulo de receitas inicializado com sucesso!")
            except Exception as e:
                logger.error(f"Erro ao inicializar módulo de receitas: {e}")
        
        # Inicializar módulo de receita digital
        try:
            receita_digital_module = init_medico_receita_digital(mysql, base)
            modules.append(receita_digital_module)
            logger.info(f"Módulo de receita digital inicializado com sucesso!")
        except Exception as e:
            logger.error(f"Erro ao inicializar módulo de receita digital: {e}")
        
        # Registrar rotas dos módulos
        total_rotas = 0
        for idx, module in enumerate(modules):
            logger.info(f"Registrando rotas do módulo {idx+1}/{len(modules)} - {len(module['routes'])} rotas")
            for route in module['routes']:
                medico_bp.add_url_rule(**route)
                total_rotas += 1
        
        logger.info(f"Total de {total_rotas} rotas registradas no blueprint médico")
        
        # Registrar blueprint de consultas detalhadas
        try:
            consulta_detalhes_bp = create_consulta_blueprint(mysql)
            medico_bp.register_blueprint(consulta_detalhes_bp)
            logger.info("Blueprint de consultas detalhadas registrado")
        except Exception as e:
            logger.error(f"Erro ao registrar blueprint de consultas: {e}")
        
        # Exportar funções para uso em templates
        medico_bp.obter_info_medico = base['obter_info_medico']
        medico_bp.execute_query = base['execute_query']
        medico_bp.formatar_data = base['formatar_data']
        medico_bp.calcular_idade = base['calcular_idade']
        
        # Rota de debug
        @medico_bp.route('/debug-rotas')
        def debug_rotas():
            output = "<h1>🔍 Rotas disponíveis em 'medico':</h1>"
            output += "<style>table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #ddd; padding: 8px; } th { background-color: #4CAF50; color: white; }</style>"
            output += "<tr><th>Endpoint</th><th>URL</th><th>Métodos</th></tr>"
            for rule in app.url_map.iter_rules():
                if str(rule).startswith('/medico/'):
                    output += f"<tr><td>{rule.endpoint}</td><td>{rule}</td><td>{', '.join(rule.methods)}</td></tr>"
            output += "</table><br><a href='/medico/dashboard'>Voltar ao Dashboard</a>"
            return output
        
        logger.info("Blueprint médico inicializado com sucesso!")
        print("="*50)
        
        return medico_bp
        
    except Exception as e:
        logger.error(f"Erro ao inicializar blueprint médico: {e}")
        logger.error(traceback.format_exc())
        raise

__all__ = ['init_medico']
