# routes/medico/medico_receita_digital.py - VERSÃO COMPLETA CORRIGIDA
from flask import render_template, request, redirect, url_for, flash, jsonify, Blueprint
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

def init_medico_receita_digital(mysql, base):
    """
    Inicializa o módulo de receita digital
    """
    
    # Importar dados de medicamentos
    from utils.receitas_data import MEDICAMENTOS_POR_CONDICAO
    
    # Funções auxiliares do base - usar get para evitar KeyError
    execute_query = base.get('execute_query')
    obter_medico_id = base.get('obter_medico_id')
    obter_detalhes_consulta = base.get('obter_detalhes_consulta')
    formatar_data = base.get('formatar_data')
    
    # CORREÇÃO: Criar uma versão segura de obter_medico_id se não existir
    if obter_medico_id is None:
        logger.warning("obter_medico_id não encontrado no base. Usando função alternativa.")
        
        def obter_medico_id():
            """Função alternativa para obter ID do médico logado"""
            from flask import session
            if 'user_id' not in session or session.get('user_type') != 'medico':
                return None
            
            try:
                cur = mysql.connection.cursor()
                cur.execute("SELECT id FROM medicos WHERE usuario_id = %s", (session['user_id'],))
                result = cur.fetchone()
                cur.close()
                
                # CORREÇÃO: Verificar se result é tupla ou dict
                if result:
                    if isinstance(result, dict):
                        return result.get('id')
                    elif isinstance(result, (tuple, list)):
                        return result[0] if len(result) > 0 else None
                return None
            except Exception as e:
                logger.error(f"Erro ao obter médico ID: {e}")
                return None
    
    # Se execute_query não estiver disponível, criar uma versão simples
    if execute_query is None:
        logger.warning("execute_query não encontrado no base. Usando função alternativa.")
        
        def execute_query(query, params=None, fetch=False, one=False):
            """Função alternativa para executar queries"""
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
                logger.error(traceback.format_exc())
                return None
    
    # Se obter_detalhes_consulta não estiver disponível, criar uma versão simples
    if obter_detalhes_consulta is None:
        logger.warning("obter_detalhes_consulta não encontrado no base. Usando função alternativa.")
        
        def obter_detalhes_consulta(consulta_id):
            """Função alternativa para obter detalhes da consulta"""
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
                c = cur.fetchone()
                cur.close()
                
                if not c:
                    return None
                
                # Formatar data
                data_hora = c[4]
                if hasattr(data_hora, 'strftime'):
                    data_hora_formatada = data_hora.strftime('%d/%m/%Y %H:%M')
                else:
                    data_hora_formatada = str(data_hora)
                
                return {
                    'id': c[0],
                    'medico_nome': c[1],
                    'especialidade': c[2],
                    'crm': c[3],
                    'data_hora': data_hora_formatada,
                    'status': c[5],
                    'observacoes': c[6] or '',
                    'receita': c[7] or '',
                    'paciente_nome': c[8],
                    'paciente_id': c[15],
                    'medico_id': c[16],
                    'paciente_email': c[17],
                    'sintomas_raw': c[18] if len(c) > 18 else '',
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(c[5], 'secondary')
                }
            except Exception as e:
                logger.error(f"Erro ao obter detalhes da consulta: {e}")
                return None
    
    # Se formatar_data não estiver disponível, criar uma versão simples
    if formatar_data is None:
        logger.warning("formatar_data não encontrado no base. Usando função alternativa.")
        
        def formatar_data(data, formato='%d/%m/%Y %H:%M'):
            """Função alternativa para formatar data"""
            if data is None:
                return ''
            
            if hasattr(data, 'strftime'):
                return data.strftime(formato)
            elif isinstance(data, str):
                try:
                    from datetime import datetime
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(data, fmt).strftime(formato)
                        except ValueError:
                            continue
                except:
                    pass
            return str(data)
    
    def gerar_html_receita(consulta, diagnostico, medicamentos, observacoes_gerais):
        """Gera HTML formatado para a receita"""
        
        data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        html = f'''
        <div class="receita-container" style="font-family: 'Courier New', monospace; max-width: 800px; margin: 0 auto; padding: 20px; background: white; border: 1px solid #28a745; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                <h2 style="color: #28a745; margin: 0;">RECEITA MÉDICA</h2>
                <p style="color: #666; font-size: 12px;">Documento Digital</p>
            </div>
            
            <div style="margin-bottom: 20px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                <p><strong>Paciente:</strong> {consulta.get('paciente_nome', '')}</p>
                <p><strong>Data:</strong> {data_atual}</p>
                <p><strong>Médico:</strong> Dr. {consulta.get('medico_nome', '')} - CRM: {consulta.get('crm', '')}</p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h4 style="color: #28a745; border-left: 4px solid #28a745; padding-left: 10px;">DIAGNÓSTICO</h4>
                <p style="padding: 10px; background: #f8f9fa; border-radius: 5px;">{diagnostico}</p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h4 style="color: #28a745; border-left: 4px solid #28a745; padding-left: 10px;">MEDICAMENTOS PRESCRITOS</h4>
        '''
        
        for i, med in enumerate(medicamentos, 1):
            html += f'''
                <div style="margin-bottom: 15px; padding: 10px; border-left: 3px solid #28a745; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <p><strong>{i}. {med.get('nome', '')}</strong> {med.get('apresentacao', '')}</p>
                    <p style="margin-left: 20px;"><strong>Posologia:</strong> {med.get('posologia', '')}</p>
                    <p style="margin-left: 20px;"><strong>Frequência:</strong> {med.get('frequencia', '')}</p>
                    <p style="margin-left: 20px;"><strong>Duração:</strong> {med.get('duracao', '')}</p>
                    <p style="margin-left: 20px;"><strong>Via:</strong> {med.get('via', 'Oral')}</p>
                    <p style="margin-left: 20px;"><strong>Quantidade:</strong> {med.get('quantidade', '')}</p>
            '''
            if med.get('observacoes'):
                html += f'<p style="margin-left: 20px; color: #666;"><em>Obs: {med["observacoes"]}</em></p>'
            html += '</div>'
        
        if observacoes_gerais:
            html += f'''
            <div style="margin-top: 20px;">
                <h4 style="color: #28a745; border-left: 4px solid #28a745; padding-left: 10px;">OBSERVAÇÕES</h4>
                <p style="padding: 10px; background: #f8f9fa; border-radius: 5px;">{observacoes_gerais}</p>
            </div>
            '''
        
        html += f'''
            <div style="margin-top: 40px; text-align: center;">
                <p style="border-top: 1px dashed #28a745; padding-top: 20px;">__________________________________</p>
                <p><strong>Dr. {consulta.get('medico_nome', '')}</strong></p>
                <p>CRM: {consulta.get('crm', '')}</p>
                <p style="color: #666; font-size: 11px;">Documento digital válido em todo território nacional</p>
            </div>
        </div>
        '''
        
        return html
    
    # ========== FUNÇÃO AUXILIAR PARA EXTRAIR VALOR ==========
    def extrair_valor_resultado(resultado, indice=0, chave=None, padrao=None):
        """Extrai valor de forma segura de dict ou tuple/list"""
        if resultado is None:
            return padrao
        
        if isinstance(resultado, dict):
            if chave:
                return resultado.get(chave, padrao)
            valores = list(resultado.values())
            return valores[0] if valores else padrao
        
        if isinstance(resultado, (tuple, list)):
            if len(resultado) > indice:
                return resultado[indice]
            return padrao
        
        return resultado if resultado is not None else padrao
    
    # ========== ROTA DE TESTE ==========
    def teste_receita(consulta_id):
        """Rota de teste para verificar se o módulo está funcionando"""
        return f"<h1>✅ Rota de teste da Receita Digital funcionando!</h1><p>Consulta ID: {consulta_id}</p><p><a href='/medico/consultas'>Voltar</a></p>"
    
    # ========== ROTA PRINCIPAL ==========
    def receita_digital(consulta_id):
        """Página para criar receita digital"""
        medico_id = obter_medico_id()
        
        if not medico_id:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta or consulta.get('medico_id') != medico_id:
            flash('Consulta não encontrada ou você não tem permissão.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        return render_template('medico/receita_digital.html',
                              consulta=consulta,
                              medicamentos_por_condicao=MEDICAMENTOS_POR_CONDICAO,
                              medico_id=medico_id,
                              formatar_data=formatar_data,
                              datetime=datetime)
    
    # ========== ROTA PARA SALVAR RECEITA DIGITAL ==========
    def salvar_receita_digital(consulta_id):
        """Salva a receita digital na tabela receita"""
        medico_id = obter_medico_id()
        
        if not medico_id:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            diagnostico = request.form.get('diagnostico')
            observacoes_gerais = request.form.get('observacoes_gerais', '')
            
            # Processar medicamentos
            medicamentos = []
            prefix = 'medicamentos['
            
            for key in request.form.keys():
                if key.startswith(prefix) and key.endswith('][nome]'):
                    index = key.replace(prefix, '').replace('][nome]', '')
                    
                    medicamento = {
                        'nome': request.form.get(f'medicamentos[{index}][nome]', ''),
                        'apresentacao': request.form.get(f'medicamentos[{index}][apresentacao]', ''),
                        'posologia': request.form.get(f'medicamentos[{index}][posologia]', ''),
                        'frequencia': request.form.get(f'medicamentos[{index}][frequencia]', ''),
                        'duracao': request.form.get(f'medicamentos[{index}][duracao]', ''),
                        'via': request.form.get(f'medicamentos[{index}][via]', 'Oral'),
                        'quantidade': request.form.get(f'medicamentos[{index}][quantidade]', ''),
                        'observacoes': request.form.get(f'medicamentos[{index}][observacoes]', '')
                    }
                    
                    # Só adicionar se tiver nome
                    if medicamento['nome']:
                        medicamentos.append(medicamento)
            
            if not medicamentos:
                flash('Adicione pelo menos um medicamento à receita.', 'warning')
                return redirect(url_for('medico_receita_digital.receita_digital', consulta_id=consulta_id))
            
            # Buscar dados da consulta
            consulta = obter_detalhes_consulta(consulta_id)
            
            # Gerar HTML da receita
            receita_html = gerar_html_receita(consulta, diagnostico, medicamentos, observacoes_gerais)
            
            # Gerar texto da prescrição para a tabela receita
            prescricao_texto = ""
            for i, med in enumerate(medicamentos, 1):
                prescricao_texto += f"{i}. {med.get('nome', '')} - {med.get('apresentacao', '')}\n"
                prescricao_texto += f"   Posologia: {med.get('posologia', '')}\n"
                prescricao_texto += f"   Frequência: {med.get('frequencia', '')}\n"
                prescricao_texto += f"   Duração: {med.get('duracao', '')}\n"
                prescricao_texto += f"   Via: {med.get('via', 'Oral')}\n"
                prescricao_texto += f"   Quantidade: {med.get('quantidade', '')}\n"
                if med.get('observacoes'):
                    prescricao_texto += f"   Obs: {med['observacoes']}\n"
                prescricao_texto += "\n"
            
            # Salvar na tabela RECEITA
            result = execute_query("""
                INSERT INTO receita 
                (consulta_id, diagnostico, prescricao, recomendacoes, status, created_at)
                VALUES (%s, %s, %s, %s, 'ativa', NOW())
            """, (consulta_id, diagnostico, prescricao_texto, observacoes_gerais))
            
            # Também atualizar o campo receita da consulta com o HTML formatado
            execute_query("""
                UPDATE consultas 
                SET receita = %s,
                    diagnostico_texto = %s,
                    atualizado_em = NOW()
                WHERE id = %s AND medico_id = %s
            """, (receita_html, diagnostico, consulta_id, medico_id))
            
            flash('✅ Receita digital gerada com sucesso!', 'success')
            
            # CORREÇÃO: Redirecionar para a rota correta de detalhes da consulta
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
        except Exception as e:
            logger.error(f"Erro ao salvar receita digital: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao gerar receita. Tente novamente.', 'danger')
            return redirect(url_for('medico_receita_digital.receita_digital', consulta_id=consulta_id))
    
    # Lista de rotas do módulo
    routes = [
        {
            'rule': '/teste-receita/<int:consulta_id>',
            'endpoint': 'teste_receita',
            'view_func': teste_receita,
            'methods': ['GET']
        },
        {
            'rule': '/consulta/<int:consulta_id>/receita-digital',
            'endpoint': 'receita_digital',
            'view_func': receita_digital,
            'methods': ['GET']
        },
        {
            'rule': '/consulta/<int:consulta_id>/receita-digital/salvar',
            'endpoint': 'salvar_receita_digital',
            'view_func': salvar_receita_digital,
            'methods': ['POST']
        }
    ]
    
    return {
        'routes': routes,
        'medicamentos_por_condicao': MEDICAMENTOS_POR_CONDICAO
    }
