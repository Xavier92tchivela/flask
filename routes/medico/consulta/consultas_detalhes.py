# routes/medico/consulta/detalhes.py
from datetime import datetime
from flask import render_template, flash, redirect, url_for, session
from .decorators import login_required
from .utils import execute_query, formatar_data, obter_medico_id, obter_paciente_id, processar_sintomas, mapear_dia_semana, mapear_mes
from .queries import get_detalhes_consulta_query, get_diagnostico_query, get_pedido_analise_query

def register_detalhes_routes(bp, mysql):
    
    def obter_detalhes_consulta(consulta_id):
        """Obtém detalhes completos de uma consulta"""
        try:
            consulta = execute_query(mysql, get_detalhes_consulta_query(), (consulta_id,), True)
            
            if not consulta:
                return None
            
            c = consulta[0]
            
            sintomas_lista = processar_sintomas(c[18] if len(c) > 18 else '')
            dia_semana_pt = mapear_dia_semana(c[19]) if len(c) > 19 and c[19] else ''
            mes_num = c[22] if len(c) > 22 else None
            mes_pt = mapear_mes(mes_num) if mes_num else ''
            
            return {
                'id': c[0],
                'medico_nome': c[1],
                'especialidade': c[2],
                'crm': c[3],
                'data_hora': c[4],
                'status': c[5],
                'observacoes': c[6],
                'receita': c[7],
                'paciente_nome': c[8],
                'data_nascimento': formatar_data(c[9], '%d/%m/%Y') if c[9] else None,
                'genero': c[10],
                'paciente_telefone': c[11],
                'paciente_endereco': c[12],
                'medico_email': c[13],
                'medico_telefone': c[14],
                'paciente_id': c[15],
                'medico_id': c[16],
                'paciente_email': c[17],
                'sintomas_lista': sintomas_lista,
                'dia_semana': dia_semana_pt,
                'data_consulta': c[20] if len(c) > 20 else '',
                'hora_consulta': str(c[21]) if len(c) > 21 and c[21] else '',
                'mes': mes_num,
                'mes_nome': mes_pt,
                'ano': c[23] if len(c) > 23 else '',
                'status_class': {
                    'agendada': 'warning',
                    'realizada': 'success',
                    'cancelada': 'danger',
                    'confirmada': 'info'
                }.get(c[5], 'secondary')
            }
        except Exception as e:
            return None
    
    @bp.route('/detalhes/<int:consulta_id>')
    @login_required
    def detalhes_consulta(consulta_id):
        """Detalhes de uma consulta específica"""
        usuario_tipo = session.get('user_type')
        
        # Obter detalhes da consulta
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('auth.index'))
        
        # Verificar permissão de acesso
        tem_acesso = False
        
        if usuario_tipo == 'admin':
            tem_acesso = True
        elif usuario_tipo == 'medico':
            medico_id = obter_medico_id(mysql, session)
            tem_acesso = consulta['medico_id'] == medico_id
        elif usuario_tipo == 'paciente':
            paciente_id = obter_paciente_id(mysql, session)
            tem_acesso = consulta['paciente_id'] == paciente_id
        
        if not tem_acesso:
            flash('Você não tem permissão para acessar esta consulta.', 'danger')
            return redirect(url_for('auth.index'))
        
        # Buscar diagnóstico
        diagnostico_raw = execute_query(mysql, get_diagnostico_query(), (consulta_id,), True)
        diagnostico_info = None
        
        if diagnostico_raw:
            d = diagnostico_raw[0]
            diagnostico_info = {
                'id': d[0],
                'tipo_exame': d[1] or 'Não especificado',
                'descricao': d[2] or '',
                'observacoes': d[3] or '',
                'resultado': d[4] or '',
                'diagnostico_preliminar': d[5] or '',
                'diagnostico_final': d[6] or '',
                'status': d[7] or 'pendente',
                'imagem_path': d[8],
                'criado_em': formatar_data(d[12]) if d[12] else '',
                'atualizado_em': formatar_data(d[13]) if d[13] else '',
                'medico_nome': d[14],
                'medico_especialidade': d[15],
                'medico_crm': d[16]
            }
        
        # Buscar pedido de análise
        pedido_raw = execute_query(mysql, get_pedido_analise_query(), (consulta_id,), True)
        pedido_info = None
        
        if pedido_raw:
            p = pedido_raw[0]
            anexos = []
            if p[11] and isinstance(p[11], str):
                try:
                    import json
                    anexos = json.loads(p[11])
                except:
                    anexos = []
            
            pedido_info = {
                'id': p[0],
                'tipo_exame': p[1] or 'Não especificado',
                'descricao': p[2] or '',
                'observacoes': p[3] or '',
                'urgencia': p[4] or 'normal',
                'status': p[5] or 'pendente',
                'data_solicitacao': formatar_data(p[6]) if p[6] else '',
                'data_conclusao': formatar_data(p[7]) if p[7] else '',
                'resultado_analise': p[8] or '',
                'diagnostico_analista': p[9] or '',
                'recomendacoes_analista': p[10] or '',
                'anexos': anexos,
                'status_aprovacao': p[12] or 'pendente',
                'observacoes_medico': p[13] or '',
                'analista_id': p[14],
                'analista_nome': p[15] or 'Não atribuído',
                'total_anexos': len(anexos)
            }
        
        # Processar sintomas para o template
        sintomas = consulta.get('sintomas_lista', [])
        
        # Buscar receitas (se houver)
        receitas = []  # Implementar se necessário
        
        return render_template('consulta/detalhes_medico.html',
                             consulta=consulta,
                             diagnostico=diagnostico_info,
                             pedido=pedido_info,
                             pedidos=[pedido_info] if pedido_info else [],
                             receitas=receitas,
                             sintomas=sintomas,
                             usuario_tipo=usuario_tipo,
                             user=session,
                             agora=datetime.now().strftime('%d/%m/%Y %H:%M'))