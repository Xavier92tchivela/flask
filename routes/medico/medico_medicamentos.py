# routes/medico/medico_medicamentos.py

from datetime import datetime, date, timedelta, time
import traceback
import logging
from flask import Flask, redirect, url_for, flash, render_template, session, jsonify, request

logger = logging.getLogger(__name__)

def init_medico_medicamentos(mysql, base):
    """Inicializa módulo de medicamentos para médico"""
    
    obter_info_medico = base['obter_info_medico']
    
    def decode_bytes(value):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode('utf-8')
            except:
                return str(value)
        return value
    
    def calcular_idade(data_nascimento):
        if not data_nascimento:
            return None
        today = datetime.now().date()
        if isinstance(data_nascimento, datetime):
            birth_date = data_nascimento.date()
        else:
            birth_date = data_nascimento
        idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return idade
    
    def formatar_data_segura(valor):
        """Formata data de forma segura - SEMPRE retorna string"""
        if valor is None:
            return '-'
        
        try:
            # Se for datetime ou date
            if isinstance(valor, (datetime, date)):
                return valor.strftime('%d/%m/%Y')
            
            # Se for string
            if isinstance(valor, str):
                # Tenta converter para datetime
                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(valor, fmt)
                        return dt.strftime('%d/%m/%Y')
                    except:
                        continue
                return valor
            
            # Qualquer outro tipo, tenta converter para string
            return str(valor)
        except Exception as e:
            logger.error(f"Erro ao formatar data {valor}: {e}")
            return '-'
    
    def formatar_hora_segura(valor):
        """Formata hora de forma segura - SEMPRE retorna string"""
        if valor is None:
            return '-'
        
        try:
            # Se for timedelta (MAIOR CAUSA DO ERRO)
            if isinstance(valor, timedelta):
                total_seconds = int(valor.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return f"{hours:02d}:{minutes:02d}"
            
            # Se for time
            if isinstance(valor, time):
                return valor.strftime('%H:%M')
            
            # Se for datetime
            if isinstance(valor, datetime):
                return valor.strftime('%H:%M')
            
            # Se for string
            if isinstance(valor, str):
                # Remove milissegundos
                if '.' in valor:
                    valor = valor.split('.')[0]
                
                # Se tem dois pontos, extrai HH:MM
                if ':' in valor:
                    parts = valor.split(':')
                    if len(parts) >= 2:
                        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
                
                # Se tem formato HHMM
                if len(valor) == 4 and valor.isdigit():
                    return f"{valor[:2]}:{valor[2:]}"
                
                return valor
            
            # Fallback
            return str(valor)[:5]
        except Exception as e:
            logger.error(f"Erro ao formatar hora {valor}: {e}")
            return '-'
    
    def formatar_data_hora_segura(valor):
        """Formata data e hora de forma segura"""
        if valor is None:
            return '-'
        
        try:
            if isinstance(valor, datetime):
                return valor.strftime('%d/%m/%Y %H:%M')
            
            if isinstance(valor, date):
                return valor.strftime('%d/%m/%Y')
            
            if isinstance(valor, str):
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        dt = datetime.strptime(valor, fmt)
                        return dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        continue
                return valor
            
            return str(valor)
        except Exception as e:
            logger.error(f"Erro ao formatar data/hora {valor}: {e}")
            return '-'
    
    routes = []
    
    # ===================== ROTA: LISTAR INTERNADOS =====================
    def listar_internados_medico():
        try:
            medico_info = obter_info_medico()
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
                idade = calcular_idade(internado[9]) if internado[9] else None
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
    
    routes.append({'rule': '/internados', 'view_func': listar_internados_medico, 'methods': ['GET']})
    
    # ===================== ROTA: PRESCREVER MEDICAMENTO =====================
    def prescrever_medicamento(internacao_id):
        try:
            medico_info = obter_info_medico()
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
    
    routes.append({'rule': '/prescrever-medicamento/<int:internacao_id>', 'view_func': prescrever_medicamento, 'methods': ['GET']})
    
    # ===================== ROTA: LISTAR PRESCRIÇÕES (COMPLETAMENTE CORRIGIDA) =====================
    def listar_prescricoes(internacao_id):
        try:
            medico_info = obter_info_medico()
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
                try:
                    prescricao = {
                        'id': p[0],
                        'medicamento': decode_bytes(p[1]) if p[1] else '-',
                        'dosagem': decode_bytes(p[2]) if p[2] else '-',
                        'via': decode_bytes(p[3]) if p[3] else '-',
                        'frequencia': decode_bytes(p[4]) if p[4] else '-',
                        'horario_inicio': formatar_hora_segura(p[5]),
                        'horario_fim': formatar_hora_segura(p[6]),
                        'data_inicio': formatar_data_segura(p[7]),
                        'data_fim': formatar_data_segura(p[8]) if p[8] else 'Indeterminado',
                        'observacoes': decode_bytes(p[9]) if p[9] else None,
                        'status': decode_bytes(p[10]) if p[10] else 'ativa',
                        'created_at': formatar_data_hora_segura(p[11])
                    }
                    prescricoes.append(prescricao)
                except Exception as e:
                    logger.error(f"Erro ao processar prescrição {p[0] if p else 'unknown'}: {e}")
                    continue
            
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
    
    routes.append({'rule': '/listar_prescricoes/<int:internacao_id>', 'view_func': listar_prescricoes, 'methods': ['GET']})
    
    # ===================== ROTA: SALVAR PRESCRIÇÃO =====================
    def salvar_prescricao():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({"success": False, "error": "Não autorizado"}), 401
            
            data = request.get_json()
            internacao_id = data.get('internacao_id')
            medicamento = data.get('medicamento', '').strip()
            dosagem = data.get('dosagem', '').strip()
            via = data.get('via', '').strip()
            frequencia = data.get('frequencia', '').strip()
            horario_inicio = data.get('horario_inicio')
            horario_fim = data.get('horario_fim')
            data_inicio = data.get('data_inicio')
            data_fim = data.get('data_fim')
            observacoes = data.get('observacoes', '').strip()
            
            # Validações
            if not all([internacao_id, medicamento, dosagem, via, frequencia, data_inicio]):
                return jsonify({"success": False, "error": "Preencha todos os campos obrigatórios"}), 400
            
            # Converter valores vazios para None
            horario_inicio = horario_inicio if horario_inicio and str(horario_inicio).strip() else None
            horario_fim = horario_fim if horario_fim and str(horario_fim).strip() else None
            data_fim = data_fim if data_fim and str(data_fim).strip() else None
            observacoes = observacoes if observacoes else None
            
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO medicamentos_prescritos 
                (internacao_id, consulta_id, medicamento, dosagem, via, frequencia, 
                 horario_inicio, horario_fim, data_inicio, data_fim, 
                 observacoes, status, medico_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ativa', %s)
            """, (
                internacao_id,
                None,
                medicamento,
                dosagem,
                via,
                frequencia,
                horario_inicio,
                horario_fim,
                data_inicio,
                data_fim,
                observacoes,
                medico_info['id']
            ))
            
            mysql.connection.commit()
            cursor.close()
            
            return jsonify({"success": True, "message": "Medicamento prescrito com sucesso!"})
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    routes.append({'rule': '/api/prescrever-medicamento', 'view_func': salvar_prescricao, 'methods': ['POST']})
    
    # ===================== ROTA: SUSPENDER PRESCRIÇÃO =====================
    def suspender_prescricao(prescricao_id):
        try:
            medico_info = obter_info_medico()
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
            return jsonify({"success": False, "error": str(e)}), 500
    
    routes.append({'rule': '/api/suspender-prescricao/<int:prescricao_id>', 'view_func': suspender_prescricao, 'methods': ['POST']})
    
    return {'routes': routes}