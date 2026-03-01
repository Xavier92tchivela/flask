# routes/medico/medico_perfil.py
from flask import render_template, request, flash, redirect, url_for, session
import logging

logger = logging.getLogger(__name__)

def init_medico_perfil(base):  # 👈 RENOMEADO DE init_perfil PARA init_medico_perfil
    """Inicializa rotas de perfil"""
    
    # Extrair funções do base
    execute_query = base['execute_query']
    obter_info_medico = base['obter_info_medico']
    medico_required = base['medico_required']
    calcular_idade = base['calcular_idade']
    formatar_data = base['formatar_data']
    
    # ========== ROTA: PERFIL ==========
    @medico_required
    def perfil():
        medico_info = obter_info_medico()
        if not medico_info:
            flash('Médico não encontrado.', 'danger')
            return redirect(url_for('medico.dashboard'))
        
        if not isinstance(medico_info, dict):
            medico_info = {'nome': 'Erro', 'especialidade': 'Erro', 'crm': '', 'email': '', 'telefone': ''}
        
        # Estatísticas completas
        estatisticas = {
            'total_consultas': 0,
            'consultas_mes': 0,
            'pacientes_atendidos': 0,
            'total_pedidos': 0,
            'pedidos_pendentes': 0,
            'pedidos_concluidos': 0,
            'resultados_pendentes': 0,
            'total_receitas': 0
        }
        
        medico_id = medico_info.get('id')
        
        if medico_id and medico_id > 0:
            # Total de consultas
            total = execute_query("SELECT COUNT(*) FROM consultas WHERE medico_id = %s",
                                 (medico_id,), fetch=True, one=True)
            if total:
                estatisticas['total_consultas'] = total[0]
            
            # Consultas do mês
            mes = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND MONTH(data_hora) = MONTH(CURDATE())
                AND YEAR(data_hora) = YEAR(CURDATE())
            """, (medico_id,), fetch=True, one=True)
            if mes:
                estatisticas['consultas_mes'] = mes[0]
            
            # Pacientes únicos
            pacientes = execute_query("""
                SELECT COUNT(DISTINCT paciente_id) FROM consultas WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            if pacientes:
                estatisticas['pacientes_atendidos'] = pacientes[0]
            
            # Total de pedidos
            pedidos = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            if pedidos:
                estatisticas['total_pedidos'] = pedidos[0]
            
            # Pedidos pendentes
            pendentes = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            if pendentes:
                estatisticas['pedidos_pendentes'] = pendentes[0]
            
            # Pedidos concluídos
            concluidos = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido'
            """, (medico_id,), fetch=True, one=True)
            if concluidos:
                estatisticas['pedidos_concluidos'] = concluidos[0]
            
            # Resultados pendentes de revisão
            resultados = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            if resultados:
                estatisticas['resultados_pendentes'] = resultados[0]
            
            # Total de receitas
            receitas = execute_query("""
                SELECT COUNT(*) FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE c.medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            if receitas:
                estatisticas['total_receitas'] = receitas[0]
        
        return render_template('medico/perfil.html',
                             medico=medico_info,
                             estatisticas=estatisticas,
                             user=session)
    
    # ========== ROTA: ATUALIZAR PERFIL ==========
    @medico_required
    def atualizar_perfil():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.perfil'))
            
            user_id = medico_info.get('usuario_id')
            if not user_id:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('medico.perfil'))
            
            nome = request.form.get('nome')
            email = request.form.get('email')
            telefone = request.form.get('telefone')
            especialidade = request.form.get('especialidade')
            crm = request.form.get('crm')
            
            if not nome or not email or not especialidade or not crm:
                flash('Preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('medico.perfil'))
            
            execute_query("""
                UPDATE usuarios SET nome=%s, email=%s, telefone=%s WHERE id=%s
            """, (nome, email, telefone, user_id))
            
            medico = execute_query("""
                SELECT id FROM medicos WHERE usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if medico:
                execute_query("""
                    UPDATE medicos SET especialidade=%s, crm=%s WHERE usuario_id=%s
                """, (especialidade, crm, user_id))
            else:
                execute_query("""
                    INSERT INTO medicos (usuario_id, especialidade, crm, status)
                    VALUES (%s, %s, %s, 'ativo')
                """, (user_id, especialidade, crm))
            
            flash('Perfil atualizado com sucesso!', 'success')
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            flash('Erro ao atualizar perfil.', 'danger')
        
        return redirect(url_for('medico.perfil'))
    
    return {
        'routes': [
            {'rule': '/perfil', 'view_func': perfil, 'methods': ['GET']},
            {'rule': '/atualizar-perfil', 'view_func': atualizar_perfil, 'methods': ['POST']}
        ]
    }

# 👈 EXPORTAR A FUNÇÃO COM O NOME CORRETO
__all__ = ['init_medico_perfil']