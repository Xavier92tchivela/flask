# routes/medico/__init__.py
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
from datetime import datetime

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
        
        # Inicializar funções base
        base = init_medico_base(mysql)
        
        # ===================== FUNÇÃO AUXILIAR =====================
        def decode_bytes(value):
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                try:
                    return value.decode('utf-8')
                except:
                    return str(value)
            return value
        
        # ===================== ROTA: SALVAR RECEITA AJAX =====================
        @medico_bp.route('/receita/salvar-ajax', methods=['POST'])
        def salvar_receita_ajax():
            """Salva a receita via AJAX com medicamentos personalizados"""
            try:
                from flask import session
                import json
                
                if 'user_id' not in session:
                    return jsonify({"success": False, "error": "Não autorizado"}), 401
                
                data = request.get_json()
                if not data:
                    data = request.form.to_dict()
                
                receita_id = data.get('receita_id')
                consulta_id = data.get('consulta_id')
                medicamentos = data.get('medicamentos', [])
                observacoes = data.get('observacoes', '')
                receita_texto = data.get('receita_texto', '')
                diagnostico = data.get('diagnostico', '')
                
                # Se veio como JSON string, converter
                if isinstance(medicamentos, str):
                    try:
                        medicamentos = json.loads(medicamentos)
                    except:
                        medicamentos = []
                
                # Buscar médico_id
                medico_info = base['obter_info_medico']()
                if not medico_info:
                    return jsonify({"success": False, "error": "Médico não encontrado"}), 404
                
                medico_id = medico_info.get('id')
                
                cursor = mysql.connection.cursor()
                
                # Verificar se já existe receita
                cursor.execute("SELECT id FROM receita WHERE consulta_id = %s", (consulta_id,))
                existing = cursor.fetchone()
                
                prescricao_texto = receita_texto
                if medicamentos and len(medicamentos) > 0 and not prescricao_texto:
                    # Gerar texto a partir dos medicamentos estruturados
                    prescricao_texto = ""
                    for i, med in enumerate(medicamentos, 1):
                        prescricao_texto += f"{i}. {med.get('nome', 'Medicamento')}"
                        if med.get('apresentacao'):
                            prescricao_texto += f" - {med.get('apresentacao')}"
                        prescricao_texto += "\n"
                        if med.get('posologia'):
                            prescricao_texto += f"   Posologia: {med.get('posologia')}\n"
                        if med.get('frequencia'):
                            prescricao_texto += f"   Frequência: {med.get('frequencia')}\n"
                        if med.get('duracao'):
                            prescricao_texto += f"   Duração: {med.get('duracao')}\n"
                        if med.get('quantidade'):
                            prescricao_texto += f"   Quantidade: {med.get('quantidade')}\n"
                        if med.get('instrucoes') or med.get('observacoes'):
                            prescricao_texto += f"   Obs: {med.get('instrucoes') or med.get('observacoes')}\n"
                        prescricao_texto += "\n"
                
                if existing:
                    # Atualizar receita existente
                    cursor.execute("""
                        UPDATE receita 
                        SET diagnostico = %s,
                            prescricao = %s,
                            recomendacoes = %s,
                            medicamentos = %s,
                            atualizado_em = NOW()
                        WHERE consulta_id = %s
                    """, (diagnostico, prescricao_texto, observacoes, json.dumps(medicamentos), consulta_id))
                    receita_id = existing[0]
                else:
                    # Criar nova receita
                    cursor.execute("""
                        INSERT INTO receita 
                        (consulta_id, diagnostico, prescricao, recomendacoes, medicamentos, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'ativa', NOW())
                    """, (consulta_id, diagnostico, prescricao_texto, observacoes, json.dumps(medicamentos)))
                    receita_id = cursor.lastrowid
                
                mysql.connection.commit()
                cursor.close()
                
                # Gerar HTML da receita
                receita_html = f"""
                <div class="receita-container">
                    <h4>Receita Médica</h4>
                    <p><strong>Diagnóstico:</strong> {diagnostico}</p>
                    <p><strong>Prescrição:</strong><br>{prescricao_texto.replace(chr(10), '<br>')}</p>
                    <p><strong>Orientações:</strong><br>{observacoes.replace(chr(10), '<br>')}</p>
                </div>
                """
                
                return jsonify({
                    "success": True, 
                    "message": "Receita salva com sucesso",
                    "receita_html": receita_html,
                    "receita_id": receita_id
                })
                
            except Exception as e:
                logger.error(f"Erro ao salvar receita: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"success": False, "error": str(e)}), 500
        
        # ===================== ROTA: LISTAR INTERNADOS =====================
        @medico_bp.route('/internados')
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
                    if len(internado) > 9 and internado[9]:
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
                        'paciente_id': internado[6] if len(internado) > 6 else None,
                        'paciente_nome': decode_bytes(internado[7]) if len(internado) > 7 and internado[7] else 'Paciente',
                        'idade': idade,
                        'leito_alas': decode_bytes(internado[10]) if len(internado) > 10 and internado[10] else 'Não definido',
                        'leito_numero': internado[11] if len(internado) > 11 and internado[11] else '?',
                        'leito_tipo': decode_bytes(internado[12]) if len(internado) > 12 and internado[12] else 'Não definido'
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
        
        # ===================== ROTA: PRESCREVER MEDICAMENTO =====================
        @medico_bp.route('/prescrever-medicamento/<int:internacao_id>')
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
        
        # ===================== ROTA: SALVAR PRESCRIÇÃO =====================
        @medico_bp.route('/api/prescrever-medicamento', methods=['POST'])
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
        
        # ===================== ROTA: LISTAR PRESCRIÇÕES =====================
        @medico_bp.route('/prescricoes/<int:internacao_id>')
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
        
        # ===================== ROTA: SUSPENDER PRESCRIÇÃO =====================
        @medico_bp.route('/api/suspender-prescricao/<int:prescricao_id>', methods=['POST'])
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
        modules = [
            init_medico_dashboard(base),
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
        
        # Exportar funções
        medico_bp.obter_info_medico = base['obter_info_medico']
        medico_bp.execute_query = base['execute_query']
        medico_bp.formatar_data = base['formatar_data']
        medico_bp.calcular_idade = base['calcular_idade']
        
        # Rota de debug
        @medico_bp.route('/debug-rotas')
        def debug_rotas():
            output = "<h1>🔍 Rotas disponíveis em 'medico':</h1>"
            output += "<style>table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #ddd; padding: 8px; } th { background-color: #4CAF50; color: white; }</style>"
            output += "处 perfil<th>Endpoint</th><th>URL</th><th>Métodos</th></tr>"
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
