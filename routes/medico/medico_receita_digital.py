# routes/medico/medico_receita_digital.py - VERSÃO COMPLETA CORRIGIDA
# TODOS OS ENDPOINTS RENOMEADOS PARA EVITAR CONFLITOS
from flask import render_template, request, redirect, url_for, flash, jsonify, Blueprint, session
from datetime import datetime
import logging
import traceback
import json

logger = logging.getLogger(__name__)

def init_medico_receita_digital(mysql, base):
    """
    Inicializa o módulo de receita digital
    """
    
    # Importar dados de medicamentos
    from utils.receitas_data import MEDICAMENTOS_POR_CONDICAO
    
    # Funções auxiliares do base
    execute_query = base.get('execute_query')
    formatar_data = base.get('formatar_data')
    obter_medico_id = base.get('obter_medico_id')
    
    if obter_medico_id is None:
        logger.warning("obter_medico_id não encontrado no base. Usando função alternativa.")
        
        def obter_medico_id():
            if 'user_id' not in session or session.get('user_type') != 'medico':
                return None
            try:
                cur = mysql.connection.cursor()
                cur.execute("SELECT id FROM medicos WHERE usuario_id = %s", (session['user_id'],))
                result = cur.fetchone()
                cur.close()
                
                if result:
                    if isinstance(result, dict):
                        return result.get('id')
                    elif isinstance(result, (tuple, list)):
                        return result[0] if len(result) > 0 else None
                return None
            except Exception as e:
                logger.error(f"Erro ao obter médico ID: {e}")
                return None
    
    # Função para obter detalhes da consulta
    obter_detalhes_consulta = base.get('obter_detalhes_consulta')
    
    if obter_detalhes_consulta is None:
        logger.warning("obter_detalhes_consulta não encontrado no base. Usando função alternativa.")
        
        def obter_detalhes_consulta(consulta_id):
            try:
                query = """
                    SELECT 
                        c.id,
                        m_u.nome as medico_nome,
                        m.especialidade,
                        m.crm,
                        c.data_hora,
                        c.status,
                        c.observacoes,
                        c.receita,
                        p_u.nome as paciente_nome,
                        p.data_nascimento,
                        p.genero,
                        p.telefone as paciente_telefone,
                        p.endereco as paciente_endereco,
                        m_u.email as medico_email,
                        m.telefone as medico_telefone,
                        p.id as paciente_id,
                        m.id as medico_id,
                        p_u.email as paciente_email,
                        c.sintomas
                    FROM consultas c 
                    JOIN medicos m ON c.medico_id = m.id 
                    JOIN usuarios m_u ON m.usuario_id = m_u.id 
                    JOIN pacientes p ON c.paciente_id = p.id 
                    JOIN usuarios p_u ON p.usuario_id = p_u.id 
                    WHERE c.id = %s
                """
                
                cur = mysql.connection.cursor()
                cur.execute(query, (consulta_id,))
                result = cur.fetchone()
                cur.close()
                
                if not result:
                    return None
                
                if isinstance(result, dict):
                    c = result
                    data_hora = c.get('data_hora')
                else:
                    c = result
                    data_hora = c[4] if len(c) > 4 else None
                
                if hasattr(data_hora, 'strftime'):
                    data_hora_formatada = data_hora.strftime('%d/%m/%Y %H:%M')
                else:
                    data_hora_formatada = str(data_hora) if data_hora else ''
                
                if isinstance(result, dict):
                    return {
                        'id': c.get('id'),
                        'medico_nome': c.get('medico_nome') or '',
                        'especialidade': c.get('especialidade') or '',
                        'crm': c.get('crm') or '',
                        'data_hora': data_hora_formatada,
                        'status': c.get('status') or '',
                        'observacoes': c.get('observacoes') or '',
                        'receita': c.get('receita') or '',
                        'paciente_nome': c.get('paciente_nome') or '',
                        'paciente_id': c.get('paciente_id'),
                        'medico_id': c.get('medico_id'),
                        'paciente_email': c.get('paciente_email') or '',
                        'sintomas_raw': c.get('sintomas') or '',
                        'status_class': {
                            'agendada': 'warning',
                            'realizada': 'success',
                            'cancelada': 'danger',
                            'confirmada': 'info'
                        }.get(c.get('status'), 'secondary')
                    }
                else:
                    return {
                        'id': c[0] if len(c) > 0 else None,
                        'medico_nome': c[1] if len(c) > 1 else '',
                        'especialidade': c[2] if len(c) > 2 else '',
                        'crm': c[3] if len(c) > 3 else '',
                        'data_hora': data_hora_formatada,
                        'status': c[5] if len(c) > 5 else '',
                        'observacoes': c[6] if len(c) > 6 else '',
                        'receita': c[7] if len(c) > 7 else '',
                        'paciente_nome': c[8] if len(c) > 8 else '',
                        'paciente_id': c[15] if len(c) > 15 else None,
                        'medico_id': c[16] if len(c) > 16 else None,
                        'paciente_email': c[17] if len(c) > 17 else '',
                        'sintomas_raw': c[18] if len(c) > 18 else '',
                        'status_class': {
                            'agendada': 'warning',
                            'realizada': 'success',
                            'cancelada': 'danger',
                            'confirmada': 'info'
                        }.get(c[5] if len(c) > 5 else '', 'secondary')
                    }
            except Exception as e:
                logger.error(f"Erro ao obter detalhes da consulta: {e}")
                logger.error(traceback.format_exc())
                return None
    
    if execute_query is None:
        logger.warning("execute_query não encontrado no base. Usando função alternativa.")
        
        def execute_query(query, params=None, fetch=False, one=False):
            try:
                cur = mysql.connection.cursor()
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                
                if fetch:
                    result = cur.fetchall()
                    if one and result:
                        result = result[0]
                else:
                    mysql.connection.commit()
                    result = None
                
                cur.close()
                return result
            except Exception as e:
                mysql.connection.rollback()
                logger.error(f"Database error: {e}")
                return None
    
    if formatar_data is None:
        def formatar_data(data, formato='%d/%m/%Y %H:%M'):
            if data is None:
                return ''
            if hasattr(data, 'strftime'):
                return data.strftime(formato)
            return str(data)
    
    def gerar_html_receita_com_medicamentos(medicamentos, observacoes):
        """Gera HTML formatado para a receita com medicamentos personalizados"""
        if not medicamentos:
            return "<p>Nenhum medicamento prescrito.</p>"
        
        html = '<div class="lista-medicamentos">'
        for i, med in enumerate(medicamentos, 1):
            html += f'''
            <div class="medicamento-item mb-3 pb-2 border-bottom">
                <div class="d-flex justify-content-between align-items-start">
                    <h6 class="mb-1 fw-bold">{i}. {med.get("nome", "Medicamento")}</h6>
                </div>
            '''
            if med.get('dosagem'):
                html += f'<div class="ms-3 mb-1"><strong>Dosagem:</strong> {med.get("dosagem")}</div>'
            if med.get('frequencia'):
                html += f'<div class="ms-3 mb-1"><strong>Frequência:</strong> {med.get("frequencia")}</div>'
            if med.get('duracao'):
                html += f'<div class="ms-3 mb-1"><strong>Duração:</strong> {med.get("duracao")}</div>'
            if med.get('quantidade'):
                html += f'<div class="ms-3 mb-1"><strong>Quantidade:</strong> {med.get("quantidade")}</div>'
            if med.get('instrucoes'):
                html += f'<div class="ms-3 mb-1"><em>Instruções: {med.get("instrucoes")}</em></div>'
            html += '</div>'
        
        if observacoes:
            html += f'''
            <div class="observacoes-receita mt-3 pt-2 border-top">
                <strong>Observações:</strong>
                <p class="mb-0 small">{observacoes}</p>
            </div>
            '''
        
        html += '</div>'
        return html
    
    # ========== ROTA PARA SALVAR RECEITA (AJAX) ==========
    def salvar_receita_ajax():
        """Salva a receita via AJAX com medicamentos personalizados"""
        try:
            if 'user_id' not in session:
                return jsonify({"success": False, "error": "Não autorizado"}), 401
            
            data = request.get_json()
            receita_id = data.get('receita_id')
            medicamentos = data.get('medicamentos', [])
            observacoes = data.get('observacoes', '')
            
            if not receita_id:
                return jsonify({"success": False, "error": "ID da receita não informado"}), 400
            
            execute_query("""
                UPDATE receita 
                SET medicamentos = %s, 
                    observacoes_receita = %s,
                    atualizado_em = NOW()
                WHERE id = %s
            """, (json.dumps(medicamentos), observacoes, receita_id))
            
            receita_html = gerar_html_receita_com_medicamentos(medicamentos, observacoes)
            
            return jsonify({
                "success": True, 
                "message": "Receita salva com sucesso",
                "receita_html": receita_html
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar receita: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========== ROTA PARA OBTER DADOS DA RECEITA ==========
    def obter_receita_json(receita_id):
        """Obtém os dados da receita para edição"""
        try:
            if 'user_id' not in session:
                return jsonify({"success": False, "error": "Não autorizado"}), 401
            
            result = execute_query("""
                SELECT id, medicamentos, observacoes_receita, diagnostico
                FROM receita 
                WHERE id = %s
            """, (receita_id,), fetch=True, one=True)
            
            if not result:
                return jsonify({"success": False, "error": "Receita não encontrada"}), 404
            
            medicamentos = []
            if result.get('medicamentos'):
                try:
                    medicamentos = json.loads(result['medicamentos'])
                except:
                    medicamentos = []
            
            return jsonify({
                "success": True,
                "medicamentos": medicamentos,
                "observacoes": result.get('observacoes_receita') or '',
                "diagnostico": result.get('diagnostico') or ''
            })
            
        except Exception as e:
            logger.error(f"Erro ao obter receita: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========== ROTA DE TESTE ==========
    def teste_receita_digital(consulta_id):
        return f"<h1>✅ Rota de teste da Receita Digital funcionando!</h1><p>Consulta ID: {consulta_id}</p>"
    
    # ========== ROTA PRINCIPAL ==========
    def criar_receita_digital(consulta_id):
        """Página para criar receita digital"""
        medico_id = obter_medico_id()
        
        if not medico_id:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        if consulta.get('medico_id') != medico_id:
            flash('Você não tem permissão para acessar esta consulta.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        return render_template('medico/receita_digital.html',
                              consulta=consulta,
                              medicamentos_por_condicao=MEDICAMENTOS_POR_CONDICAO,
                              medico_id=medico_id,
                              formatar_data=formatar_data,
                              datetime=datetime)
    
    # ========== ROTA PARA VER RECEITA GERADA ==========
    def visualizar_receita_gerada(receita_id):
        """Visualiza uma receita já gerada"""
        try:
            if 'user_id' not in session:
                flash('Faça login para acessar.', 'danger')
                return redirect(url_for('auth.login'))
            
            result = execute_query("""
                SELECT r.*, c.paciente_id, c.medico_id
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE r.id = %s
            """, (receita_id,), fetch=True, one=True)
            
            if not result:
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            medico = execute_query("""
                SELECT u.nome, m.crm, m.especialidade
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.id = %s
            """, (result.get('medico_id'),), fetch=True, one=True)
            
            paciente = execute_query("""
                SELECT u.nome, p.data_nascimento
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (result.get('paciente_id'),), fetch=True, one=True)
            
            medicamentos = []
            if result.get('medicamentos'):
                try:
                    medicamentos = json.loads(result['medicamentos'])
                except:
                    medicamentos = []
            
            idade = None
            if paciente and paciente.get('data_nascimento'):
                hoje = datetime.now().date()
                nascimento = paciente['data_nascimento']
                if hasattr(nascimento, 'date'):
                    nascimento = nascimento.date()
                idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
            
            return render_template('medico/receita_gerada.html',
                                  receita_id=receita_id,
                                  receita=result.get('prescricao', ''),
                                  observacoes_receita=result.get('observacoes_receita', ''),
                                  medicamentos=medicamentos,
                                  pedido={
                                      'id': result.get('consulta_id'),
                                      'paciente_nome': paciente.get('nome') if paciente else 'N/A',
                                      'paciente_idade': f'{idade} anos' if idade else 'N/A',
                                      'diagnostico_ia': result.get('diagnostico', ''),
                                      'sintomas_lista': []
                                  },
                                  medico={
                                      'nome': medico.get('nome') if medico else 'Dr. Desconhecido',
                                      'crm': medico.get('crm') if medico else 'N/A',
                                      'especialidade': medico.get('especialidade') if medico else 'N/A'
                                  } if medico else {},
                                  gemini_available=True,
                                  datetime=datetime,
                                  pdf_path=None)
            
        except Exception as e:
            logger.error(f"Erro ao visualizar receita: {e}")
            flash('Erro ao carregar receita.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ========== ROTA PARA EDITAR RECEITA ==========
    def editar_receita_digital(receita_id):
        """Edita uma receita existente"""
        try:
            if 'user_id' not in session:
                flash('Faça login para acessar.', 'danger')
                return redirect(url_for('auth.login'))
            
            result = execute_query("""
                SELECT r.*, c.paciente_id, c.medico_id
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE r.id = %s
            """, (receita_id,), fetch=True, one=True)
            
            if not result:
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            medico = execute_query("""
                SELECT u.nome, m.crm, m.especialidade
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.id = %s
            """, (result.get('medico_id'),), fetch=True, one=True)
            
            paciente = execute_query("""
                SELECT u.nome, p.data_nascimento
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (result.get('paciente_id'),), fetch=True, one=True)
            
            medicamentos = []
            if result.get('medicamentos'):
                try:
                    medicamentos = json.loads(result['medicamentos'])
                except:
                    medicamentos = []
            
            idade = None
            if paciente and paciente.get('data_nascimento'):
                hoje = datetime.now().date()
                nascimento = paciente['data_nascimento']
                if hasattr(nascimento, 'date'):
                    nascimento = nascimento.date()
                idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
            
            return render_template('medico/editar_receita.html',
                                  receita_id=receita_id,
                                  receita_texto=result.get('prescricao', ''),
                                  observacoes_receita=result.get('observacoes_receita', ''),
                                  diagnostico=result.get('diagnostico', ''),
                                  medicamentos=medicamentos,
                                  pedido={
                                      'id': result.get('consulta_id'),
                                      'paciente_nome': paciente.get('nome') if paciente else 'N/A',
                                      'paciente_idade': f'{idade} anos' if idade else 'N/A'
                                  },
                                  medico={
                                      'nome': medico.get('nome') if medico else 'Dr. Desconhecido',
                                      'crm': medico.get('crm') if medico else 'N/A',
                                      'especialidade': medico.get('especialidade') if medico else 'N/A'
                                  } if medico else {},
                                  datetime=datetime)
            
        except Exception as e:
            logger.error(f"Erro ao editar receita: {e}")
            flash('Erro ao carregar receita para edição.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ========== ROTA PARA SALVAR EDIÇÃO ==========
    def salvar_edicao_receita_digital(receita_id):
        """Salva as alterações feitas na receita"""
        try:
            if 'user_id' not in session:
                flash('Faça login para acessar.', 'danger')
                return redirect(url_for('auth.login'))
            
            diagnostico = request.form.get('diagnostico', '')
            prescricao = request.form.get('prescricao', '')
            observacoes = request.form.get('observacoes', '')
            
            medicamentos = []
            i = 0
            while f'medicamento_nome_{i}' in request.form:
                nome = request.form.get(f'medicamento_nome_{i}', '').strip()
                if nome:
                    medicamentos.append({
                        'nome': nome,
                        'dosagem': request.form.get(f'medicamento_dosagem_{i}', ''),
                        'frequencia': request.form.get(f'medicamento_frequencia_{i}', ''),
                        'duracao': request.form.get(f'medicamento_duracao_{i}', ''),
                        'quantidade': request.form.get(f'medicamento_quantidade_{i}', ''),
                        'instrucoes': request.form.get(f'medicamento_instrucoes_{i}', '')
                    })
                i += 1
            
            execute_query("""
                UPDATE receita 
                SET diagnostico = %s,
                    prescricao = %s,
                    observacoes_receita = %s,
                    medicamentos = %s,
                    atualizado_em = NOW()
                WHERE id = %s
            """, (diagnostico, prescricao, observacoes, json.dumps(medicamentos), receita_id))
            
            flash('✅ Receita atualizada com sucesso!', 'success')
            return redirect(url_for('medico_receita_digital.visualizar_receita_gerada', receita_id=receita_id))
            
        except Exception as e:
            logger.error(f"Erro ao salvar edição da receita: {e}")
            flash('Erro ao salvar alterações.', 'danger')
            return redirect(url_for('medico_receita_digital.editar_receita_digital', receita_id=receita_id))
    
    # ========== LISTA DE ROTAS - COM ENDPOINTS RENOMEADOS ==========
    routes = [
        {
            'rule': '/teste-receita-digital/<int:consulta_id>',
            'endpoint': 'teste_receita_digital',
            'view_func': teste_receita_digital,
            'methods': ['GET']
        },
        {
            'rule': '/consulta/<int:consulta_id>/receita-digital',
            'endpoint': 'criar_receita_digital',
            'view_func': criar_receita_digital,
            'methods': ['GET']
        },
        {
            'rule': '/receita/salvar-ajax',
            'endpoint': 'salvar_receita_ajax',
            'view_func': salvar_receita_ajax,
            'methods': ['POST']
        },
        {
            'rule': '/receita/<int:receita_id>/dados-json',
            'endpoint': 'obter_receita_json',
            'view_func': obter_receita_json,
            'methods': ['GET']
        },
        {
            'rule': '/receita/<int:receita_id>/visualizar',
            'endpoint': 'visualizar_receita_gerada',
            'view_func': visualizar_receita_gerada,
            'methods': ['GET']
        },
        {
            'rule': '/receita/<int:receita_id>/editar',
            'endpoint': 'editar_receita_digital',
            'view_func': editar_receita_digital,
            'methods': ['GET']
        },
        {
            'rule': '/receita/<int:receita_id>/salvar-edicao',
            'endpoint': 'salvar_edicao_receita_digital',
            'view_func': salvar_edicao_receita_digital,
            'methods': ['POST']
        }
    ]
    
    return {
        'routes': routes,
        'medicamentos_por_condicao': MEDICAMENTOS_POR_CONDICAO
    }
