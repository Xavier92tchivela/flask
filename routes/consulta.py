"""
Blueprint de consultas - Versão completa com suporte ao template detalhes_consulta.html
e campo PESO nos sinais vitais
"""

from flask import Blueprint, jsonify, redirect, url_for, flash, render_template, session, request
from datetime import datetime
import logging
import json
# Adicione no topo do arquivo
from utils.classificacoes import (
    classificar_pressao_arterial,
    classificar_frequencia_cardiaca,
    classificar_frequencia_respiratoria,
    classificar_temperatura,
    classificar_saturacao_oxigenio,
    classificar_glicemia,
    classificar_peso  # 👈 NOVA CLASSIFICAÇÃO DE PESO
)

logger = logging.getLogger(__name__)

def create_consulta_blueprint(mysql):
    """
    Cria e retorna o blueprint de consultas
    
    Args:
        mysql: Conexão com MySQL
        
    Returns:
        Blueprint configurado
    """
    logger.info("Inicializando blueprint de consultas")
    
    consulta_bp = Blueprint('consulta', __name__, url_prefix='/consulta')
    
    # ========== FUNÇÕES AUXILIARES ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Executa queries no banco de dados"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                if one and result:
                    return result[0]
                return result
            else:
                mysql.connection.commit()
                cur.close()
                return True
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, str):
            try:
                if 'T' in data:
                    return datetime.fromisoformat(data.replace('Z', '+00:00')).strftime(formato)
                else:
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(data, fmt).strftime(formato)
                        except ValueError:
                            continue
                    return data
            except:
                return data
        return str(data)
    
    def obter_medico_id():
        """Obtém o ID do médico logado"""
        if session.get('user_type') != 'medico':
            return None
        
        try:
            medico = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            return medico[0] if medico else None
        except:
            return None
    
    def obter_paciente_id():
        """Obtém o ID do paciente logado"""
        if session.get('user_type') != 'paciente':
            return None
        
        try:
            paciente = execute_query(
                "SELECT id FROM pacientes WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            return paciente[0] if paciente else None
        except:
            return None
    
    def processar_sintomas(sintomas_raw):
        """Processa string de sintomas para lista"""
        if not sintomas_raw:
            return []
        return [s.strip() for s in sintomas_raw.split(',') if s.strip()]
    
    def mapear_dia_semana(dia_ingles):
        """Mapeia dia da semana de inglês para português"""
        dias_map = {
            'Monday': 'Segunda-feira',
            'Tuesday': 'Terça-feira',
            'Wednesday': 'Quarta-feira',
            'Thursday': 'Quinta-feira',
            'Friday': 'Sexta-feira',
            'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }
        return dias_map.get(dia_ingles, dia_ingles)
    
    def mapear_mes(mes_num):
        """Mapeia número do mês para nome em português"""
        meses_map = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        return meses_map.get(mes_num, '')
    
    # ========== FUNÇÕES DE CLASSIFICAÇÃO PARA CADA SINAL VITAL ==========
    
    def classificar_pressao_arterial(pressao_arterial):
        """
        Classifica a pressão arterial em:
        - ALTA (HIPERTENSÃO): sistólica >= 140 OU diastólica >= 90
        - BAIXA (HIPOTENSÃO): sistólica < 90 OU diastólica < 60
        - NORMAL: valores entre 90-139 e 60-89
        """
        if not pressao_arterial:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            # Limpar a string e extrair os valores
            pressao = pressao_arterial.replace(' ', '').replace('x', '/').replace(',', '.')
            
            if '/' in pressao:
                partes = pressao.split('/')
                if len(partes) == 2:
                    sistolica = float(partes[0])
                    diastolica = float(partes[1])
                    
                    # HIPOTENSÃO (BAIXA)
                    if sistolica < 90 or diastolica < 60:
                        return {"classificacao": "HIPOTENSÃO", "status": "warning", "cor": "Amarelo"}
                    # HIPERTENSÃO (ALTA)
                    elif sistolica >= 140 or diastolica >= 90:
                        return {"classificacao": "HIPERTENSÃO", "status": "danger", "cor": "Vermelho"}
                    # NORMOTENSÃO (NORMAL)
                    else:
                        return {"classificacao": "NORMOTENSÃO", "status": "success", "cor": "Verde"}
        except Exception as e:
            logger.error(f"Erro ao classificar PA: {e}")
            pass
        
        return {"classificacao": "Não classificado", "status": "secondary", "cor": "Cinza"}
    
    def classificar_frequencia_cardiaca(fc):
        """
        Classifica a frequência cardíaca em:
        - ALTA (TAQUICARDIA): > 100 bpm
        - BAIXA (BRADICARDIA): < 60 bpm
        - NORMAL: 60-100 bpm
        """
        if not fc:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            fc = int(fc)
            if fc < 60:
                return {"classificacao": "BRADICARDIA", "status": "warning", "cor": "Amarelo"}
            elif fc > 100:
                return {"classificacao": "TAQUICARDIA", "status": "danger", "cor": "Vermelho"}
            else:
                return {"classificacao": "NORMAL", "status": "success", "cor": "Verde"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary", "cor": "Cinza"}
    
    def classificar_frequencia_respiratoria(fr):
        """
        Classifica a frequência respiratória em:
        - ALTA (TAQUIPNEIA): > 20 rpm
        - BAIXA (BRADIPNEIA): < 12 rpm
        - NORMAL: 12-20 rpm
        """
        if not fr:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            fr = int(fr)
            if fr < 12:
                return {"classificacao": "BRADIPNEIA", "status": "warning", "cor": "Amarelo"}
            elif fr > 20:
                return {"classificacao": "TAQUIPNEIA", "status": "danger", "cor": "Vermelho"}
            else:
                return {"classificacao": "NORMAL", "status": "success", "cor": "Verde"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary", "cor": "Cinza"}
    
    def classificar_temperatura(temp):
        """
        Classifica a temperatura em:
        - ALTA (FEBRE): > 37.2°C
        - BAIXA (HIPOTERMIA): < 36.1°C
        - NORMAL: 36.1°C - 37.2°C
        """
        if not temp:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            temp = float(temp)
            if temp < 36.1:
                return {"classificacao": "HIPOTERMIA", "status": "warning", "cor": "Amarelo"}
            elif temp > 37.2:
                return {"classificacao": "FEBRE", "status": "danger", "cor": "Vermelho"}
            else:
                return {"classificacao": "NORMAL", "status": "success", "cor": "Verde"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary", "cor": "Cinza"}
    
    def classificar_saturacao_oxigenio(spo2):
        """
        Classifica a saturação de oxigênio em:
        - BAIXA (HIPÓXIA): < 95%
        - NORMAL: >= 95%
        """
        if not spo2:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            spo2 = int(spo2)
            if spo2 < 95:
                return {"classificacao": "HIPÓXIA", "status": "danger", "cor": "Vermelho"}
            elif spo2 <= 100:
                return {"classificacao": "NORMAL", "status": "success", "cor": "Verde"}
            else:
                return {"classificacao": "VALOR INVÁLIDO", "status": "secondary", "cor": "Cinza"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary", "cor": "Cinza"}
    
    def classificar_glicemia(glicemia):
        """
        Classifica a glicemia em:
        - ALTA (HIPERGLICEMIA): > 140 mg/dL (pós-prandial) ou > 99 mg/dL (jejum)
        - BAIXA (HIPOGLICEMIA): < 70 mg/dL
        - NORMAL: 70-140 mg/dL (considerando valor genérico)
        """
        if not glicemia:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            glicemia = int(glicemia)
            if glicemia < 70:
                return {"classificacao": "HIPOGLICEMIA", "status": "warning", "cor": "Amarelo"}
            elif glicemia > 140:
                return {"classificacao": "HIPERGLICEMIA", "status": "danger", "cor": "Vermelho"}
            else:
                return {"classificacao": "NORMAL", "status": "success", "cor": "Verde"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary", "cor": "Cinza"}
    
    def obter_detalhes_consulta(consulta_id):
        """Obtém detalhes completos de uma consulta"""
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
                    c.sintomas,
                    DAYNAME(c.data_hora) as dia_semana,
                    DATE(c.data_hora) as data_consulta,
                    TIME(c.data_hora) as hora_consulta,
                    MONTH(c.data_hora) as mes,
                    YEAR(c.data_hora) as ano
                FROM consultas c 
                JOIN medicos m ON c.medico_id = m.id 
                JOIN usuarios m_u ON m.usuario_id = m_u.id 
                JOIN pacientes p ON c.paciente_id = p.id 
                JOIN usuarios p_u ON p.usuario_id = p_u.id 
                WHERE c.id = %s
            """
            
            consulta = execute_query(query, (consulta_id,), fetch=True, one=True)
            
            if not consulta:
                return None
            
            c = consulta
            
            # Calcular idade
            idade = None
            if c[9]:  # data_nascimento
                try:
                    if isinstance(c[9], datetime):
                        data_nasc = c[9]
                    else:
                        data_nasc = datetime.strptime(str(c[9]), '%Y-%m-%d')
                    idade = datetime.now().year - data_nasc.year
                    if datetime.now().month < data_nasc.month or (datetime.now().month == data_nasc.month and datetime.now().day < data_nasc.day):
                        idade -= 1
                except:
                    idade = None
            
            sintomas_lista = processar_sintomas(c[18] if len(c) > 18 else '')
            dia_semana_pt = mapear_dia_semana(c[19]) if len(c) > 19 and c[19] else ''
            mes_num = c[22] if len(c) > 22 else None
            mes_pt = mapear_mes(mes_num) if mes_num else ''
            
            return {
                'id': c[0],
                'medico_nome': c[1],
                'especialidade': c[2],
                'crm': c[3],
                'data_hora': formatar_data(c[4]),
                'data_hora_formatada': c[4].strftime('%Y-%m-%dT%H:%M') if isinstance(c[4], datetime) else str(c[4]),
                'status': c[5],
                'observacoes': c[6] or '',
                'receita': c[7] or '',
                'paciente_nome': c[8],
                'paciente_idade': f"{idade} anos" if idade else None,
                'data_nascimento': formatar_data(c[9], '%d/%m/%Y') if c[9] else None,
                'genero': 'Masculino' if c[10] == 'M' else 'Feminino' if c[10] == 'F' else (c[10] or 'Não informado'),
                'paciente_telefone': c[11] or 'Não informado',
                'paciente_endereco': c[12] or 'Não informado',
                'medico_email': c[13],
                'medico_telefone': c[14] or '',
                'paciente_id': c[15],
                'medico_id': c[16],
                'paciente_email': c[17],
                'sintomas_raw': c[18] if len(c) > 18 else '',
                'sintomas_lista': sintomas_lista,
                'dia_semana': dia_semana_pt,
                'data_consulta': c[20].strftime('%Y-%m-%d') if isinstance(c[20], datetime) else str(c[20]) if c[20] else '',
                'hora_consulta': str(c[21]) if c[21] and len(c) > 21 else '',
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
            logger.error(f"Erro ao obter detalhes da consulta: {e}")
            return None
    
    def obter_diagnostico(consulta_id):
        """Obtém diagnóstico da consulta"""
        try:
            query = """
                SELECT 
                    d.id,
                    d.tipo_exame,
                    d.descricao,
                    d.observacoes,
                    d.resultado,
                    d.diagnostico_preliminar,
                    d.diagnostico_final,
                    d.status,
                    d.imagem_path,
                    d.criado_em,
                    d.atualizado_em,
                    m_u.nome as medico_nome,
                    m.especialidade,
                    m.crm
                FROM diagnostico d
                JOIN consultas c ON d.consulta_id = c.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE d.consulta_id = %s
                ORDER BY d.id DESC
                LIMIT 1
            """
            
            diagnostico = execute_query(query, (consulta_id,), fetch=True, one=True)
            
            if not diagnostico:
                return None
            
            d = diagnostico
            return {
                'id': d[0],
                'tipo_exame': d[1] or 'Não especificado',
                'descricao': d[2] or '',
                'observacoes': d[3] or '',
                'resultado': d[4] or '',
                'diagnostico_preliminar': d[5] or '',
                'diagnostico_final': d[6] or '',
                'status': d[7] or 'pendente',
                'imagem_path': d[8],
                'criado_em': formatar_data(d[9]) if d[9] else '',
                'atualizado_em': formatar_data(d[10]) if d[10] else '',
                'medico_nome': d[11],
                'medico_especialidade': d[12],
                'medico_crm': d[13]
            }
        except Exception as e:
            logger.error(f"Erro ao obter diagnóstico: {e}")
            return None
    
    def obter_pedidos(consulta_id):
        """Obtém pedidos de análise da consulta"""
        try:
            query = """
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.anexos,
                    pa.status_aprovacao,
                    pa.observacoes_medico,
                    a.id as analista_id,
                    ua.nome as analista_nome,
                    a.especialidade as analista_especialidade
                FROM pedidos_analise pa
                LEFT JOIN analistas a ON pa.analista_id = a.id
                LEFT JOIN usuarios ua ON a.usuario_id = ua.id
                WHERE pa.consulta_id = %s
                ORDER BY pa.id DESC
            """
            
            pedidos = execute_query(query, (consulta_id,), fetch=True) or []
            
            pedidos_lista = []
            for p in pedidos:
                anexos = []
                if p[8] and isinstance(p[8], str):
                    try:
                        anexos = json.loads(p[8])
                    except:
                        anexos = []
                
                pedidos_lista.append({
                    'id': p[0],
                    'tipo_exame': p[1] or 'Não especificado',
                    'status': p[2] or 'pendente',
                    'data_solicitacao': formatar_data(p[3]) if p[3] else '',
                    'data_conclusao': formatar_data(p[4]) if p[4] else '',
                    'resultado_analise': p[5] or '',
                    'diagnostico_analista': p[6] or '',
                    'recomendacoes_analista': p[7] or '',
                    'anexos': anexos,
                    'total_anexos': len(anexos),
                    'status_aprovacao': p[9] or 'pendente',
                    'observacoes_medico': p[10] or '',
                    'analista_id': p[11],
                    'analista_nome': p[12] or 'Não atribuído',
                    'analista_especialidade': p[13] or ''
                })
            
            return pedidos_lista
        except Exception as e:
            logger.error(f"Erro ao obter pedidos: {e}")
            return []
    
    def obter_receitas(consulta_id):
        """Obtém receitas da consulta"""
        try:
            query = """
                SELECT 
                    r.id,
                    r.diagnostico,
                    r.prescricao,
                    r.recomendacoes,
                    r.status,
                    r.created_at,
                    r.receita_pdf_path,
                    r.pdf_gerado
                FROM receita r
                WHERE r.consulta_id = %s
                ORDER BY r.created_at DESC
            """
            
            receitas = execute_query(query, (consulta_id,), fetch=True) or []
            
            receitas_lista = []
            for r in receitas:
                receitas_lista.append({
                    'id': r[0],
                    'diagnostico': r[1] or '',
                    'prescricao': r[2] or '',
                    'recomendacoes': r[3] or '',
                    'status': r[4] or 'ativa',
                    'created_at': formatar_data(r[5]) if r[5] else '',
                    'receita_pdf_path': r[6] or '',
                    'pdf_gerado': bool(r[7])
                })
            
            return receitas_lista
        except Exception as e:
            logger.error(f"Erro ao obter receitas: {e}")
            return []
    
    # ========== ROTA DE TESTE ==========
    @consulta_bp.route('/')
    def index():
        return jsonify({
            'status': 'ok',
            'message': 'Blueprint de consultas funcionando',
            'endpoints': [
                '/<id>',
                '/<id>/confirmar',
                '/<id>/cancelar',
                '/<id>/editar',
                '/<id>/atualizar',
                '/<id>/sinais-vitais',
                '/api/disponibilidade',
                '/api/calendario'
            ]
        })
    
    # ========== ROTA PRINCIPAL: DETALHES DA CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>')
    def detalhes_consulta(consulta_id):
        """
        Detalhes de uma consulta específica
        Rota compatível com o template: /consulta/32
        """
        # Verificar se o usuário está logado
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Obter detalhes da consulta
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('medico.dashboard'))
        
        # Verificar permissão de acesso
        usuario_tipo = session.get('user_type')
        tem_acesso = False
        
        if usuario_tipo == 'admin':
            tem_acesso = True
        elif usuario_tipo == 'medico':
            medico_id = obter_medico_id()
            tem_acesso = consulta['medico_id'] == medico_id
        elif usuario_tipo == 'paciente':
            paciente_id = obter_paciente_id()
            tem_acesso = consulta['paciente_id'] == paciente_id
        
        if not tem_acesso:
            flash('Você não tem permissão para acessar esta consulta.', 'danger')
            if usuario_tipo == 'medico':
                return redirect(url_for('medico.dashboard'))
            elif usuario_tipo == 'paciente':
                return redirect(url_for('paciente.dashboard'))
            else:
                return redirect(url_for('auth.index'))
        
        # Buscar diagnóstico
        diagnostico = obter_diagnostico(consulta_id)
        
        # Buscar pedidos de análise
        pedidos = obter_pedidos(consulta_id)
        
        # Buscar receitas
        receitas = obter_receitas(consulta_id)
        
        # Processar sintomas
        sintomas = consulta.get('sintomas_lista', [])
        
        return render_template('consulta/detalhes_consulta.html',
                             consulta=consulta,
                             diagnostico=diagnostico,
                             pedidos=pedidos,
                             receitas=receitas,
                             sintomas=sintomas,
                             usuario_tipo=usuario_tipo,
                             user=session,
                             agora=datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    # ========== ROTA PARA CONFIRMAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/confirmar', methods=['POST'])
    def confirmar_consulta(consulta_id):
        """Confirmar uma consulta"""
        if 'user_id' not in session or session.get('user_type') not in ['medico', 'admin']:
            return jsonify({'error': 'Não autorizado'}), 401
        
        try:
            execute_query(
                "UPDATE consultas SET status = 'confirmada' WHERE id = %s",
                (consulta_id,)
            )
            return jsonify({
                'success': True,
                'message': f'Consulta #{consulta_id} confirmada com sucesso'
            })
        except Exception as e:
            logger.error(f"Erro ao confirmar consulta: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA PARA CANCELAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
    def cancelar_consulta(consulta_id):
        """Cancelar uma consulta"""
        if 'user_id' not in session:
            return jsonify({'error': 'Não autorizado'}), 401
        
        try:
            # Verificar permissão
            if session.get('user_type') == 'paciente':
                paciente_id = obter_paciente_id()
                consulta = execute_query(
                    "SELECT paciente_id FROM consultas WHERE id = %s",
                    (consulta_id,), fetch=True, one=True
                )
                if not consulta or consulta[0] != paciente_id:
                    return jsonify({'error': 'Permissão negada'}), 403
            
            execute_query(
                "UPDATE consultas SET status = 'cancelada' WHERE id = %s",
                (consulta_id,)
            )
            return jsonify({
                'success': True,
                'message': f'Consulta #{consulta_id} cancelada com sucesso'
            })
        except Exception as e:
            logger.error(f"Erro ao cancelar consulta: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA PARA REALIZAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/realizar', methods=['POST'])
    def realizar_consulta(consulta_id):
        """Marcar consulta como realizada"""
        if 'user_id' not in session or session.get('user_type') != 'medico':
            return jsonify({'error': 'Não autorizado'}), 401
        
        try:
            medico_id = obter_medico_id()
            consulta = execute_query(
                "SELECT medico_id FROM consultas WHERE id = %s",
                (consulta_id,), fetch=True, one=True
            )
            if not consulta or consulta[0] != medico_id:
                return jsonify({'error': 'Permissão negada'}), 403
            
            execute_query(
                "UPDATE consultas SET status = 'realizada' WHERE id = %s",
                (consulta_id,)
            )
            return jsonify({
                'success': True,
                'message': f'Consulta #{consulta_id} realizada com sucesso'
            })
        except Exception as e:
            logger.error(f"Erro ao realizar consulta: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA PARA EDITAR CONSULTA (GET) ==========
    @consulta_bp.route('/<int:consulta_id>/editar', methods=['GET'])
    def editar_consulta(consulta_id):
        """Página de edição de consulta"""
        if 'user_id' not in session or session.get('user_type') not in ['medico', 'admin']:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        consulta = obter_detalhes_consulta(consulta_id)
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        # Verificar permissão
        if session.get('user_type') == 'medico':
            medico_id = obter_medico_id()
            if consulta['medico_id'] != medico_id:
                flash('Você não tem permissão para editar esta consulta.', 'danger')
                return redirect(url_for('medico.consultas'))
        
        # Status disponíveis
        status_options = [
            ('agendada', 'Agendada'),
            ('confirmada', 'Confirmada'),
            ('realizada', 'Realizada'),
            ('cancelada', 'Cancelada')
        ]
        
        return render_template('consulta/editar.html',
                             consulta=consulta,
                             status_options=status_options,
                             usuario_tipo=session.get('user_type'),
                             user=session)
    
    # ========== ROTA PARA ATUALIZAR CONSULTA (POST) ==========
    @consulta_bp.route('/<int:consulta_id>/atualizar', methods=['POST'])
    def atualizar_consulta(consulta_id):
        """Atualizar uma consulta"""
        if 'user_id' not in session or session.get('user_type') not in ['medico', 'admin']:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            # Pegar dados do formulário
            data = request.form.get('data')
            hora = request.form.get('hora')
            status = request.form.get('status')
            observacoes = request.form.get('observacoes', '')
            receita = request.form.get('receita', '')
            
            # Combinar data e hora
            if data and hora:
                data_hora = f"{data} {hora}:00"
                
                execute_query("""
                    UPDATE consultas 
                    SET data_hora = %s, status = %s, observacoes = %s, receita = %s
                    WHERE id = %s
                """, (data_hora, status, observacoes, receita, consulta_id))
            else:
                execute_query("""
                    UPDATE consultas 
                    SET status = %s, observacoes = %s, receita = %s
                    WHERE id = %s
                """, (status, observacoes, receita, consulta_id))
            
            flash('Consulta atualizada com sucesso!', 'success')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
        except Exception as e:
            logger.error(f"Erro ao atualizar consulta: {e}")
            flash(f'Erro ao atualizar consulta: {str(e)}', 'danger')
            return redirect(url_for('consulta.editar_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA SALVAR SINAIS VITAIS (COM PESO) ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais', methods=['POST'])
    def salvar_sinais_vitais(consulta_id):
        """Salva os sinais vitais de uma consulta, incluindo peso"""
        if 'user_id' not in session or session.get('user_type') != 'medico':
            return jsonify({'error': 'Não autorizado'}), 401
        
        try:
            # Verificar se o médico tem permissão
            medico_id = obter_medico_id()
            consulta = execute_query(
                "SELECT medico_id FROM consultas WHERE id = %s",
                (consulta_id,), fetch=True, one=True
            )
            if not consulta or consulta[0] != medico_id:
                return jsonify({'error': 'Permissão negada'}), 403
            
            # Pegar dados do formulário
            pressao_arterial = request.form.get('pressao_arterial')
            frequencia_cardiaca = request.form.get('frequencia_cardiaca')
            frequencia_respiratoria = request.form.get('frequencia_respiratoria')
            temperatura = request.form.get('temperatura')
            saturacao_oxigenio = request.form.get('saturacao_oxigenio')
            glicemia = request.form.get('glicemia')
            peso = request.form.get('peso')  # 👈 NOVO CAMPO PESO
            observacoes = request.form.get('observacoes', '')
            
            # Converter strings vazias para None
            if pressao_arterial == '':
                pressao_arterial = None
            if frequencia_cardiaca == '':
                frequencia_cardiaca = None
            if frequencia_respiratoria == '':
                frequencia_respiratoria = None
            if temperatura == '':
                temperatura = None
            if saturacao_oxigenio == '':
                saturacao_oxigenio = None
            if glicemia == '':
                glicemia = None
            if peso == '':  # 👈 NOVO CAMPO
                peso = None
            
            # Inserir no banco com o campo peso
            execute_query("""
                INSERT INTO sinais_vitais 
                (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria, 
                 temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                  temperatura, saturacao_oxigenio, glicemia, peso, observacoes))
            
            return jsonify({
                'success': True,
                'message': 'Sinais vitais (incluindo peso) salvos com sucesso!'
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar sinais vitais: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA PARA BUSCAR SINAIS VITAIS (COM PESO) ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais', methods=['GET'])
    def get_sinais_vitais(consulta_id):
        """Busca os sinais vitais de uma consulta, incluindo peso"""
        if 'user_id' not in session:
            return jsonify({'error': 'Não autorizado'}), 401
        
        try:
            # Verificar permissão
            usuario_tipo = session.get('user_type')
            tem_acesso = False
            
            if usuario_tipo == 'admin':
                tem_acesso = True
            elif usuario_tipo == 'medico':
                medico_id = obter_medico_id()
                consulta = execute_query(
                    "SELECT medico_id FROM consultas WHERE id = %s",
                    (consulta_id,), fetch=True, one=True
                )
                tem_acesso = consulta and consulta[0] == medico_id
            elif usuario_tipo == 'paciente':
                paciente_id = obter_paciente_id()
                consulta = execute_query(
                    "SELECT paciente_id FROM consultas WHERE id = %s",
                    (consulta_id,), fetch=True, one=True
                )
                tem_acesso = consulta and consulta[0] == paciente_id
            
            if not tem_acesso:
                return jsonify({'error': 'Permissão negada'}), 403
            
            # Incluir campo peso na consulta
            sinais = execute_query("""
                SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                       temperatura, saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
                FROM sinais_vitais
                WHERE consulta_id = %s
                ORDER BY data_afericao DESC
            """, (consulta_id,), fetch=True) or []
            
            resultados = []
            for s in sinais:
                # Classificar cada sinal vital individualmente
                pa_classificacao = classificar_pressao_arterial(s[1])
                fc_classificacao = classificar_frequencia_cardiaca(s[2])
                fr_classificacao = classificar_frequencia_respiratoria(s[3])
                temp_classificacao = classificar_temperatura(s[4])
                spo2_classificacao = classificar_saturacao_oxigenio(s[5])
                glicemia_classificacao = classificar_glicemia(s[6])
                peso_classificacao = classificar_peso(s[7]) if s[7] else None  # 👈 NOVA CLASSIFICAÇÃO DE PESO
                
                resultados.append({
                    'id': s[0],
                    'pressao_arterial': s[1],
                    'pa_classificacao': pa_classificacao,
                    'frequencia_cardiaca': s[2],
                    'fc_classificacao': fc_classificacao,
                    'frequencia_respiratoria': s[3],
                    'fr_classificacao': fr_classificacao,
                    'temperatura': float(s[4]) if s[4] else None,
                    'temp_classificacao': temp_classificacao,
                    'saturacao_oxigenio': s[5],
                    'spo2_classificacao': spo2_classificacao,
                    'glicemia': s[6],
                    'glicemia_classificacao': glicemia_classificacao,
                    'peso': float(s[7]) if s[7] else None,  # 👈 NOVO CAMPO PESO
                    'peso_classificacao': peso_classificacao,  # 👈 CLASSIFICAÇÃO DO PESO
                    'data_afericao': s[8].strftime('%d/%m/%Y %H:%M') if s[8] else '',
                    'observacoes': s[9] or ''
                })
            
            return jsonify({'success': True, 'sinais': resultados})
            
        except Exception as e:
            logger.error(f"Erro ao buscar sinais vitais: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API DE DISPONIBILIDADE ==========
    @consulta_bp.route('/api/disponibilidade', methods=['GET'])
    def api_disponibilidade():
        """API para verificar disponibilidade de horários"""
        medico_id = request.args.get('medico_id')
        data = request.args.get('data')
        
        if not medico_id or not data:
            return jsonify({'error': 'Parâmetros incompletos'}), 400
        
        try:
            # Buscar horários ocupados
            ocupados = execute_query("""
                SELECT TIME(data_hora) as hora
                FROM consultas
                WHERE medico_id = %s AND DATE(data_hora) = %s AND status != 'cancelada'
            """, (medico_id, data), fetch=True) or []
            
            horarios_ocupados = [h[0].strftime('%H:%M') for h in ocupados if h[0]]
            
            # Horários disponíveis (8h às 18h, de hora em hora)
            horarios_disponiveis = []
            for hora in range(8, 18):
                for minuto in [0, 30]:
                    horario = f"{hora:02d}:{minuto:02d}"
                    if horario not in horarios_ocupados:
                        horarios_disponiveis.append(horario)
            
            return jsonify({
                'disponiveis': horarios_disponiveis,
                'ocupados': horarios_ocupados
            })
            
        except Exception as e:
            logger.error(f"Erro na API de disponibilidade: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API DE CALENDÁRIO ==========
    @consulta_bp.route('/api/calendario')
    def api_calendario():
        """API para obter consultas para calendário"""
        if 'user_id' not in session:
            return jsonify([])
        
        try:
            usuario_tipo = session.get('user_type')
            eventos = []
            
            if usuario_tipo == 'paciente':
                paciente_id = obter_paciente_id()
                consultas = execute_query("""
                    SELECT c.id, m_u.nome as medico_nome, c.data_hora, c.status
                    FROM consultas c
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE c.paciente_id = %s
                """, (paciente_id,), fetch=True) or []
                
                for c in consultas:
                    eventos.append({
                        'id': c[0],
                        'title': f"Consulta com Dr(a). {c[1]}",
                        'start': c[2].isoformat() if isinstance(c[2], datetime) else str(c[2]),
                        'status': c[3],
                        'className': f'consulta-{c[3]}'
                    })
                    
            elif usuario_tipo == 'medico':
                medico_id = obter_medico_id()
                consultas = execute_query("""
                    SELECT c.id, p_u.nome as paciente_nome, c.data_hora, c.status
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios p_u ON p.usuario_id = p_u.id
                    WHERE c.medico_id = %s
                """, (medico_id,), fetch=True) or []
                
                for c in consultas:
                    eventos.append({
                        'id': c[0],
                        'title': f"Consulta com {c[1]}",
                        'start': c[2].isoformat() if isinstance(c[2], datetime) else str(c[2]),
                        'status': c[3],
                        'className': f'consulta-{c[3]}'
                    })
            
            return jsonify(eventos)
            
        except Exception as e:
            logger.error(f"Erro na API de calendário: {e}")
            return jsonify({'error': str(e)}), 500
    
    logger.info("Blueprint de consultas inicializado com sucesso")
    print("[OK] Blueprint de consultas registrado (versão completa com PESO)")
    
    return consulta_bp

# Exportar a função
__all__ = ['create_consulta_blueprint']