"""
Blueprint de consultas - Versão completa com suporte ao template detalhes_consulta.html
e campo RECEITA na tabela consultas
"""

from flask import Blueprint, jsonify, redirect, url_for, flash, render_template, session, request
from datetime import datetime, date
import logging
import json
import traceback
from utils.classificacoes import (
    classificar_pressao_arterial,
    classificar_frequencia_cardiaca,
    classificar_frequencia_respiratoria,
    classificar_temperatura,
    classificar_saturacao_oxigenio,
    classificar_glicemia,
    classificar_peso,
    interpretar_sinais_vitais,
    gerar_alerta_sinais_vitais,
    classificar_imc,
    calcular_dosagem_por_peso
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
    def convert_bytes_to_str(data):
        """Converte recursivamente bytes para string em estruturas de dados."""
        if isinstance(data, bytes):
            return data.decode('utf-8')
        elif isinstance(data, (list, tuple)):
            return [convert_bytes_to_str(item) for item in data]
        elif isinstance(data, dict):
            return {key: convert_bytes_to_str(value) for key, value in data.items()}
        else:
            return data

    def execute_query(query, params=None, fetch=False, one=False):
        """Executa queries no banco de dados"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cleaned_params = convert_bytes_to_str(params)
                cur.execute(query, cleaned_params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                converted_result = convert_bytes_to_str(result)
                if one and converted_result:
                    return converted_result[0]
                return converted_result
            else:
                mysql.connection.commit()
                cur.close()
                return True
        except Exception as e:
            logger.error(f"Database error: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if not data:
            return ''
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
    
    def obter_enfermeiro_id():
        """Obtém o ID do enfermeiro logado"""
        if session.get('user_type') != 'enfermeiro':
            return None
        
        try:
            enfermeiro = execute_query(
                "SELECT id FROM enfermeiros WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            return enfermeiro[0] if enfermeiro else None
        except:
            return None
    
    def processar_sintomas(sintomas_raw):
        """Processa string de sintomas para lista"""
        if not sintomas_raw:
            return []
        sintomas_str = str(sintomas_raw)
        return [s.strip() for s in sintomas_str.split(',') if s.strip()]
    
    def mapear_dia_semana(dia_ingles):
        """Mapeia dia da semana de inglês para português"""
        if not dia_ingles:
            return ''
        dias_map = {
            'Monday': 'Segunda',
            'Tuesday': 'Terça',
            'Wednesday': 'Quarta',
            'Thursday': 'Quinta',
            'Friday': 'Sexta',
            'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }
        return dias_map.get(str(dia_ingles), str(dia_ingles))
    
    def mapear_mes(mes_num):
        """Mapeia número do mês para nome em português abreviado"""
        if not mes_num:
            return ''
        meses_map = {
            1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
            5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
            9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
        }
        return meses_map.get(int(mes_num), '')
    
    # ========== FUNÇÕES DE CLASSIFICAÇÃO PARA CADA SINAL VITAL ==========
    
    def classificar_pressao_arterial_local(pressao_arterial):
        """
        Classifica a pressão arterial em:
        - ALTA (HIPERTENSÃO): sistólica >= 140 OU diastólica >= 90
        - BAIXA (HIPOTENSÃO): sistólica < 90 OU diastólica < 60
        - NORMAL: valores entre 90-139 e 60-89
        """
        if not pressao_arterial:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            pressao = str(pressao_arterial).replace(' ', '').replace('x', '/').replace(',', '.')
            
            if '/' in pressao:
                partes = pressao.split('/')
                if len(partes) == 2:
                    sistolica = float(partes[0])
                    diastolica = float(partes[1])
                    
                    if sistolica < 90 or diastolica < 60:
                        return {"classificacao": "HIPOTENSÃO", "status": "warning"}
                    elif sistolica >= 140 or diastolica >= 90:
                        return {"classificacao": "HIPERTENSÃO", "status": "danger"}
                    else:
                        return {"classificacao": "NORMOTENSÃO", "status": "success"}
        except Exception as e:
            logger.error(f"Erro ao classificar PA: {e}")
            pass
        
        return {"classificacao": "Não classificado", "status": "secondary"}
    
    def classificar_frequencia_cardiaca_local(fc):
        """Classifica a frequência cardíaca"""
        if not fc:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            fc = int(fc)
            if fc < 60:
                return {"classificacao": "BRADICARDIA", "status": "warning"}
            elif fc > 100:
                return {"classificacao": "TAQUICARDIA", "status": "danger"}
            else:
                return {"classificacao": "NORMAL", "status": "success"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary"}
    
    def classificar_frequencia_respiratoria_local(fr):
        """Classifica a frequência respiratória"""
        if not fr:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            fr = int(fr)
            if fr < 12:
                return {"classificacao": "BRADIPNEIA", "status": "warning"}
            elif fr > 20:
                return {"classificacao": "TAQUIPNEIA", "status": "danger"}
            else:
                return {"classificacao": "NORMAL", "status": "success"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary"}
    
    def classificar_temperatura_local(temp):
        """Classifica a temperatura"""
        if not temp:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            temp = float(temp)
            if temp < 36.1:
                return {"classificacao": "HIPOTERMIA", "status": "warning"}
            elif temp > 37.2:
                return {"classificacao": "FEBRE", "status": "danger"}
            else:
                return {"classificacao": "NORMAL", "status": "success"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary"}
    
    def classificar_saturacao_oxigenio_local(spo2):
        """Classifica a saturação de oxigênio"""
        if not spo2:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            spo2 = int(spo2)
            if spo2 < 95:
                return {"classificacao": "HIPÓXIA", "status": "danger"}
            elif spo2 <= 100:
                return {"classificacao": "NORMAL", "status": "success"}
            else:
                return {"classificacao": "VALOR INVÁLIDO", "status": "secondary"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary"}
    
    def classificar_glicemia_local(glicemia):
        """Classifica a glicemia"""
        if not glicemia:
            return {"classificacao": "Não informado", "status": "secondary"}
        
        try:
            glicemia = int(glicemia)
            if glicemia < 70:
                return {"classificacao": "HIPOGLICEMIA", "status": "warning"}
            elif glicemia > 140:
                return {"classificacao": "HIPERGLICEMIA", "status": "danger"}
            else:
                return {"classificacao": "NORMAL", "status": "success"}
        except:
            return {"classificacao": "Não classificado", "status": "secondary"}
    
    def classificar_peso_local(peso):
        """Classifica o peso (apenas informativo)"""
        if not peso:
            return None
        
        try:
            peso = float(peso)
            return {"classificacao": f"{peso} kg", "status": "info"}
        except:
            return None
    
    # ========== FUNÇÃO PRINCIPAL PARA OBTER DETALHES DA CONSULTA ==========
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
            if c[9]:
                try:
                    data_nasc = c[9]
                    if isinstance(data_nasc, datetime):
                        data_nasc = data_nasc.date()
                    elif isinstance(data_nasc, str):
                        data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                    
                    hoje = date.today()
                    idade = hoje.year - data_nasc.year
                    if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                        idade -= 1
                except Exception as e:
                    logger.error(f"Erro ao calcular idade: {e}")
                    idade = None
            
            sintomas_lista = processar_sintomas(c[18] if len(c) > 18 else '')
            dia_semana_pt = mapear_dia_semana(c[19]) if len(c) > 19 and c[19] else ''
            mes_num = c[22] if len(c) > 22 else None
            mes_pt = mapear_mes(mes_num) if mes_num else ''
            
            # Converter data_hora para objeto datetime se for string
            data_hora_obj = c[4]
            if isinstance(data_hora_obj, str):
                try:
                    data_hora_obj = datetime.strptime(data_hora_obj, '%Y-%m-%d %H:%M:%S')
                except:
                    pass

            return {
                'id': c[0],
                'medico_nome': str(c[1]) if c[1] else '',
                'especialidade': str(c[2]) if c[2] else '',
                'crm': str(c[3]) if c[3] else '',
                'data_hora': formatar_data(data_hora_obj),
                'data_hora_formatada': data_hora_obj.strftime('%Y-%m-%dT%H:%M') if isinstance(data_hora_obj, datetime) else str(data_hora_obj),
                'status': str(c[5]) if c[5] else '',
                'observacoes': str(c[6]) if c[6] else '',
                'receita': str(c[7]) if c[7] else '',
                'paciente_nome': str(c[8]) if c[8] else '',
                'paciente_idade': f"{idade} anos" if idade else None,
                'data_nascimento': formatar_data(c[9], '%d/%m/%Y') if c[9] else None,
                'genero': str(c[10]) if c[10] else 'Não informado',
                'paciente_telefone': str(c[11]) if c[11] else 'Não informado',
                'paciente_endereco': str(c[12]) if c[12] else 'Não informado',
                'medico_email': str(c[13]) if c[13] else '',
                'medico_telefone': str(c[14]) if c[14] else '',
                'paciente_id': c[15],
                'medico_id': c[16],
                'paciente_email': str(c[17]) if c[17] else '',
                'sintomas_raw': str(c[18]) if len(c) > 18 and c[18] else '',
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
            logger.error(traceback.format_exc())
            return None
    
    # ========== FUNÇÃO PARA OBTER SINAIS VITAIS ==========
    def obter_sinais_vitais(consulta_id):
        """Obtém sinais vitais da consulta com classificação"""
        try:
            query = """
                SELECT 
                    sv.id,
                    sv.pressao_arterial,
                    sv.frequencia_cardiaca,
                    sv.frequencia_respiratoria,
                    sv.temperatura,
                    sv.saturacao_oxigenio,
                    sv.glicemia,
                    sv.peso,
                    sv.data_afericao,
                    sv.observacoes,
                    u.nome as enfermeiro_nome
                FROM sinais_vitais sv
                LEFT JOIN usuarios u ON sv.enfermeiro_id = u.id
                WHERE sv.consulta_id = %s
                ORDER BY sv.data_afericao DESC
            """
            
            sinais = execute_query(query, (consulta_id,), fetch=True) or []
            
            resultados = []
            for s in sinais:
                pa_classificacao = classificar_pressao_arterial_local(s[1])
                fc_classificacao = classificar_frequencia_cardiaca_local(s[2])
                fr_classificacao = classificar_frequencia_respiratoria_local(s[3])
                temp_classificacao = classificar_temperatura_local(s[4])
                spo2_classificacao = classificar_saturacao_oxigenio_local(s[5])
                glicemia_classificacao = classificar_glicemia_local(s[6])
                peso_classificacao = classificar_peso_local(s[7]) if s[7] else None
                
                resultados.append({
                    'id': s[0],
                    'pressao_arterial': str(s[1]) if s[1] else '',
                    'pa_classificacao': pa_classificacao,
                    'frequencia_cardiaca': str(s[2]) if s[2] else '',
                    'fc_classificacao': fc_classificacao,
                    'frequencia_respiratoria': str(s[3]) if s[3] else '',
                    'fr_classificacao': fr_classificacao,
                    'temperatura': float(s[4]) if s[4] else None,
                    'temp_classificacao': temp_classificacao,
                    'saturacao_oxigenio': str(s[5]) if s[5] else '',
                    'spo2_classificacao': spo2_classificacao,
                    'glicemia': str(s[6]) if s[6] else '',
                    'glicemia_classificacao': glicemia_classificacao,
                    'peso': float(s[7]) if s[7] else None,
                    'peso_classificacao': peso_classificacao,
                    'data_afericao': s[8].strftime('%d/%m/%Y %H:%M') if s[8] else '',
                    'observacoes': str(s[9]) if s[9] else '',
                    'enfermeiro_nome': str(s[10]) if s[10] else 'Não informado'
                })
            
            return resultados
        except Exception as e:
            logger.error(f"Erro ao obter sinais vitais: {e}")
            return []
    
    # ========== FUNÇÃO PARA OBTER DIAGNÓSTICO (TABELA DIAGNOSTICO) ==========
    def obter_diagnostico(consulta_id):
        """Obtém diagnóstico da consulta na tabela diagnostico"""
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
                    d.imagem_base64,
                    d.formato_imagem,
                    d.tamanho_imagem,
                    DATE_FORMAT(d.criado_em, '%%d/%%m/%%Y %%H:%%i') as criado_em,
                    DATE_FORMAT(d.atualizado_em, '%%d/%%m/%%Y %%H:%%i') as atualizado_em
                FROM diagnostico d
                WHERE d.consulta_id = %s
                ORDER BY d.id DESC
                LIMIT 1
            """
            
            diagnostico = execute_query(query, (consulta_id,), fetch=True, one=True)
            
            if not diagnostico:
                logger.info(f"Nenhum diagnóstico encontrado para consulta {consulta_id}")
                return None
            
            d = diagnostico
            resultado = {
                'id': d[0],
                'tipo_exame': str(d[1]) if d[1] else '',
                'descricao': str(d[2]) if d[2] else '',
                'observacoes': str(d[3]) if d[3] else '',
                'resultado': str(d[4]) if d[4] else '',
                'diagnostico_preliminar': str(d[5]) if d[5] else '',
                'diagnostico_final': str(d[6]) if d[6] else '',
                'status': str(d[7]) if d[7] else 'pendente',
                'imagem_path': str(d[8]) if d[8] else '',
                'imagem_base64': d[9] if d[9] else '',
                'formato_imagem': str(d[10]) if d[10] else '',
                'tamanho_imagem': d[11] if d[11] else None,
                'criado_em': d[12] if d[12] else '',
                'atualizado_em': d[13] if d[13] else ''
            }
            
            logger.info(f"Diagnóstico encontrado para consulta {consulta_id}: status={resultado['status']}")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao obter diagnóstico: {e}")
            logger.error(traceback.format_exc())
            return None
    
    # ========== FUNÇÃO PARA OBTER PEDIDOS ==========
    def obter_pedidos(consulta_id):
        """Obtém pedidos de análise da consulta"""
        try:
            query = """
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.data_solicitacao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.data_conclusao,
                    m_u.nome as medico_nome
                FROM pedidos_analise pa
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.consulta_id = %s
                ORDER BY pa.id DESC
            """
            
            pedidos = execute_query(query, (consulta_id,), fetch=True) or []
            
            pedidos_lista = []
            for p in pedidos:
                pedidos_lista.append({
                    'id': p[0],
                    'tipo_exame': str(p[1]) if p[1] else 'Não especificado',
                    'status': str(p[2]) if p[2] else 'pendente',
                    'data_solicitacao': formatar_data(p[3]) if p[3] else '',
                    'resultado_analise': str(p[4]) if p[4] else '',
                    'diagnostico_analista': str(p[5]) if p[5] else '',
                    'data_conclusao': formatar_data(p[6]) if p[6] else '',
                    'medico_nome': str(p[7]) if p[7] else ''
                })
            
            return pedidos_lista
        except Exception as e:
            logger.error(f"Erro ao obter pedidos: {e}")
            return []
    
    # ========== FUNÇÃO PARA OBTER RECEITAS ==========
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
                    r.pdf_gerado,
                    r.data_geracao_pdf
                FROM receita r
                WHERE r.consulta_id = %s
                ORDER BY r.created_at DESC
            """
            
            receitas = execute_query(query, (consulta_id,), fetch=True) or []
            
            receitas_lista = []
            for r in receitas:
                receitas_lista.append({
                    'id': r[0],
                    'diagnostico': str(r[1]) if r[1] else '',
                    'prescricao': str(r[2]) if r[2] else '',
                    'recomendacoes': str(r[3]) if r[3] else '',
                    'status': str(r[4]) if r[4] else 'ativa',
                    'created_at': formatar_data(r[5]) if r[5] else '',
                    'receita_pdf_path': str(r[6]) if r[6] else '',
                    'pdf_gerado': bool(r[7]),
                    'data_geracao_pdf': formatar_data(r[8]) if r[8] else ''
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
                '/<id>/realizar',
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
            if session.get('user_type') == 'medico':
                return redirect(url_for('medico.consultas'))
            elif session.get('user_type') == 'paciente':
                return redirect(url_for('paciente.consultas'))
            else:
                return redirect(url_for('auth.index'))
        
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
        elif usuario_tipo == 'enfermeiro':
            tem_acesso = True
        
        if not tem_acesso:
            flash('Você não tem permissão para acessar esta consulta.', 'danger')
            if usuario_tipo == 'medico':
                return redirect(url_for('medico.dashboard'))
            elif usuario_tipo == 'paciente':
                return redirect(url_for('paciente.dashboard'))
            else:
                return redirect(url_for('auth.index'))
        
        # Buscar dados complementares
        sinais_vitais = obter_sinais_vitais(consulta_id)
        diagnostico = obter_diagnostico(consulta_id)
        pedidos = obter_pedidos(consulta_id)
        receitas = obter_receitas(consulta_id)
        sintomas = consulta.get('sintomas_lista', [])
        
        # Log para debug
        logger.info(f"Consulta {consulta_id}: {len(sinais_vitais)} sinais vitais, diagnostico={diagnostico is not None}")
        if diagnostico:
            logger.info(f"Diagnóstico: status={diagnostico.get('status')}, tipo_exame={diagnostico.get('tipo_exame')}")
        
        return render_template('consulta/detalhes_consulta.html',
                             consulta=consulta,
                             sinais_vitais=sinais_vitais,
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
            flash('Não autorizado.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
        
        try:
            execute_query(
                "UPDATE consultas SET status = 'confirmada' WHERE id = %s",
                (consulta_id,)
            )
            flash(f'Consulta #{consulta_id} confirmada com sucesso!', 'success')
        except Exception as e:
            logger.error(f"Erro ao confirmar consulta: {e}")
            flash(f'Erro ao confirmar consulta: {str(e)}', 'danger')
        
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA CANCELAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
    def cancelar_consulta(consulta_id):
        """Cancelar uma consulta"""
        if 'user_id' not in session:
            flash('Não autorizado.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
        
        try:
            execute_query(
                "UPDATE consultas SET status = 'cancelada' WHERE id = %s",
                (consulta_id,)
            )
            flash(f'Consulta #{consulta_id} cancelada com sucesso!', 'success')
        except Exception as e:
            logger.error(f"Erro ao cancelar consulta: {e}")
            flash(f'Erro ao cancelar consulta: {str(e)}', 'danger')
        
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA REALIZAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/realizar', methods=['POST'])
    def realizar_consulta(consulta_id):
        """Marcar consulta como realizada"""
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Não autorizado.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
        
        try:
            medico_id = obter_medico_id()
            consulta = execute_query(
                "SELECT medico_id FROM consultas WHERE id = %s",
                (consulta_id,), fetch=True, one=True
            )
            if not consulta or consulta[0] != medico_id:
                flash('Permissão negada.', 'danger')
                return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
            execute_query(
                "UPDATE consultas SET status = 'realizada' WHERE id = %s",
                (consulta_id,)
            )
            flash(f'Consulta #{consulta_id} realizada com sucesso!', 'success')
        except Exception as e:
            logger.error(f"Erro ao realizar consulta: {e}")
            flash(f'Erro ao realizar consulta: {str(e)}', 'danger')
        
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
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
        
        if session.get('user_type') == 'medico':
            medico_id = obter_medico_id()
            if consulta['medico_id'] != medico_id:
                flash('Você não tem permissão para editar esta consulta.', 'danger')
                return redirect(url_for('medico.consultas'))
        
        status_options = [
            ('agendada', 'Agendada'),
            ('confirmada', 'Confirmada'),
            ('realizada', 'Realizada'),
            ('cancelada', 'Cancelada')
        ]
        
        medicos = []
        pacientes = []
        if session.get('user_type') == 'admin':
            medicos = execute_query("""
                SELECT m.id, u.nome, m.especialidade
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE u.ativo = 1
                ORDER BY u.nome
            """, fetch=True) or []
            
            pacientes = execute_query("""
                SELECT p.id, u.nome
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE u.ativo = 1
                ORDER BY u.nome
            """, fetch=True) or []
        
        return render_template('consulta/editar_consulta.html',
                             consulta=consulta,
                             status_options=status_options,
                             medicos=medicos,
                             pacientes=pacientes,
                             usuario_tipo=session.get('user_type'),
                             user=session)
    
    # ========== ROTA PARA ATUALIZAR CONSULTA (POST) ==========
    @consulta_bp.route('/<int:consulta_id>/atualizar', methods=['POST'])
    def atualizar_consulta(consulta_id):
        """Atualizar uma consulta (incluindo receita)"""
        if 'user_id' not in session or session.get('user_type') not in ['medico', 'admin']:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            data = request.form.get('data')
            hora = request.form.get('hora')
            status = request.form.get('status')
            observacoes = request.form.get('observacoes', '')
            receita = request.form.get('receita', '')
            
            if session.get('user_type') == 'medico':
                medico_id = obter_medico_id()
                consulta_check = execute_query(
                    "SELECT medico_id FROM consultas WHERE id = %s",
                    (consulta_id,), fetch=True, one=True
                )
                if not consulta_check or consulta_check[0] != medico_id:
                    flash('Permissão negada.', 'danger')
                    return redirect(url_for('medico.consultas'))
            
            if session.get('user_type') == 'admin':
                medico_id = request.form.get('medico_id')
                paciente_id = request.form.get('paciente_id')
                
                if medico_id and paciente_id:
                    execute_query("""
                        UPDATE consultas 
                        SET data_hora = %s, status = %s, observacoes = %s, receita = %s,
                            medico_id = %s, paciente_id = %s
                        WHERE id = %s
                    """, (f"{data} {hora}:00", status, observacoes, receita, medico_id, paciente_id, consulta_id))
                    
                    flash('Consulta atualizada com sucesso!', 'success')
                    return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
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
            logger.error(traceback.format_exc())
            flash(f'Erro ao atualizar consulta: {str(e)}', 'danger')
            return redirect(url_for('consulta.editar_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA SALVAR SINAIS VITAIS (CORRIGIDA PARA ACEITAR MÉDICO) ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais', methods=['POST'])
    def salvar_sinais_vitais(consulta_id):
        """Salva os sinais vitais de uma consulta (enfermeiro ou médico)"""
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Não autorizado'}), 401
        
        try:
            usuario_tipo = session.get('user_type')
            user_id = session.get('user_id')
            responsavel_id = None
            
            # Buscar ID do profissional (enfermeiro ou médico)
            if usuario_tipo == 'enfermeiro':
                enfermeiro = execute_query(
                    "SELECT id FROM enfermeiros WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if enfermeiro:
                    responsavel_id = enfermeiro[0]
            elif usuario_tipo == 'medico':
                medico = execute_query(
                    "SELECT id FROM medicos WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if medico:
                    responsavel_id = medico[0]
            elif usuario_tipo == 'admin':
                # Admin pode registrar também
                responsavel_id = None
            
            # Coletar dados do formulário
            pressao_arterial = request.form.get('pressao_arterial')
            frequencia_cardiaca = request.form.get('frequencia_cardiaca')
            frequencia_respiratoria = request.form.get('frequencia_respiratoria')
            temperatura = request.form.get('temperatura')
            saturacao_oxigenio = request.form.get('saturacao_oxigenio')
            glicemia = request.form.get('glicemia')
            peso = request.form.get('peso')
            observacoes = request.form.get('observacoes', '')
            
            # Limpar valores vazios
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
            if peso == '':
                peso = None
            if observacoes == '':
                observacoes = None
            
            # Inserir sinais vitais
            if responsavel_id:
                execute_query("""
                    INSERT INTO sinais_vitais 
                    (consulta_id, enfermeiro_id, pressao_arterial, frequencia_cardiaca, 
                     frequencia_respiratoria, temperatura, saturacao_oxigenio, glicemia, 
                     peso, observacoes, data_afericao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (consulta_id, responsavel_id, pressao_arterial, frequencia_cardiaca, 
                      frequencia_respiratoria, temperatura, saturacao_oxigenio, 
                      glicemia, peso, observacoes))
            else:
                execute_query("""
                    INSERT INTO sinais_vitais 
                    (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria, 
                     temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                      temperatura, saturacao_oxigenio, glicemia, peso, observacoes))
            
            return jsonify({'success': True, 'message': 'Sinais vitais salvos com sucesso!'})
            
        except Exception as e:
            logger.error(f"Erro ao salvar sinais vitais: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ========== ROTA PARA BUSCAR SINAIS VITAIS ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais', methods=['GET'])
    def get_sinais_vitais(consulta_id):
        """Busca os sinais vitais de uma consulta"""
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Não autorizado'}), 401
        
        try:
            sinais = obter_sinais_vitais(consulta_id)
            return jsonify({'success': True, 'sinais': sinais})
        except Exception as e:
            logger.error(f"Erro ao buscar sinais vitais: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ========== API DE DISPONIBILIDADE ==========
    @consulta_bp.route('/api/disponibilidade', methods=['GET'])
    def api_disponibilidade():
        """API para verificar disponibilidade de horários"""
        medico_id = request.args.get('medico_id')
        data = request.args.get('data')
        
        if not medico_id or not data:
            return jsonify({'error': 'Parâmetros incompletos'}), 400
        
        try:
            ocupados = execute_query("""
                SELECT TIME(data_hora) as hora
                FROM consultas
                WHERE medico_id = %s AND DATE(data_hora) = %s AND status != 'cancelada'
            """, (medico_id, data), fetch=True) or []
            
            horarios_ocupados = []
            for h in ocupados:
                if h[0]:
                    if isinstance(h[0], datetime):
                        horarios_ocupados.append(h[0].strftime('%H:%M'))
                    else:
                        horarios_ocupados.append(str(h[0]))
            
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
                    data_hora = c[2].strftime('%Y-%m-%dT%H:%M:%S') if isinstance(c[2], datetime) else str(c[2])
                    eventos.append({
                        'id': c[0],
                        'title': f"Consulta Dr(a). {c[1]}",
                        'start': data_hora,
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
                    data_hora = c[2].strftime('%Y-%m-%dT%H:%M:%S') if isinstance(c[2], datetime) else str(c[2])
                    eventos.append({
                        'id': c[0],
                        'title': f"Consulta {c[1]}",
                        'start': data_hora,
                        'status': c[3],
                        'className': f'consulta-{c[3]}'
                    })
            
            return jsonify(eventos)
            
        except Exception as e:
            logger.error(f"Erro na API de calendário: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTAS PARA RECEITA DIGITAL ==========
    @consulta_bp.route('/<int:consulta_id>/receita-digital', methods=['GET'])
    def receita_digital(consulta_id):
        """Página para criar receita digital"""
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        medico_id = obter_medico_id()
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta or consulta.get('medico_id') != medico_id:
            flash('Consulta não encontrada ou você não tem permissão.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        from utils.receitas_data import MEDICAMENTOS_POR_CONDICAO
        receitas_anteriores = obter_receitas(consulta_id)
        
        return render_template('medico/receita_digital.html',
                              consulta=consulta,
                              medicamentos_por_condicao=MEDICAMENTOS_POR_CONDICAO,
                              receitas_anteriores=receitas_anteriores,
                              medico_id=medico_id,
                              formatar_data=formatar_data,
                              datetime=datetime)

    @consulta_bp.route('/<int:consulta_id>/receita-digital/salvar', methods=['POST'])
    def salvar_receita_digital(consulta_id):
        """Salva a receita digital"""
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        medico_id = obter_medico_id()
        
        try:
            diagnostico = request.form.get('diagnostico')
            observacoes_gerais = request.form.get('observacoes_gerais', '')
            
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
                    
                    if medicamento['nome']:
                        medicamentos.append(medicamento)
            
            if not medicamentos:
                flash('Adicione pelo menos um medicamento à receita.', 'warning')
                return redirect(url_for('consulta.receita_digital', consulta_id=consulta_id))
            
            prescricao_texto = ""
            for i, med in enumerate(medicamentos, 1):
                prescricao_texto += f"{i}. {med['nome']} - {med.get('apresentacao', '')}\n"
                prescricao_texto += f"   Posologia: {med.get('posologia', '')}\n"
                prescricao_texto += f"   Frequência: {med.get('frequencia', '')}\n"
                prescricao_texto += f"   Duração: {med.get('duracao', '')}\n"
                prescricao_texto += f"   Via: {med.get('via', 'Oral')}\n"
                prescricao_texto += f"   Quantidade: {med.get('quantidade', '')}\n"
                if med.get('observacoes'):
                    prescricao_texto += f"   Obs: {med['observacoes']}\n"
                prescricao_texto += "\n"
            
            execute_query("""
                INSERT INTO receita 
                (consulta_id, diagnostico, prescricao, recomendacoes, status, created_at)
                VALUES (%s, %s, %s, %s, 'ativa', NOW())
            """, (consulta_id, diagnostico, prescricao_texto, observacoes_gerais))
            
            flash('Receita digital gerada com sucesso!', 'success')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
        except Exception as e:
            logger.error(f"Erro ao salvar receita digital: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao gerar receita. Tente novamente.', 'danger')
            return redirect(url_for('consulta.receita_digital', consulta_id=consulta_id))
    
    # ========== ROTA PARA INTERNAR PACIENTE ==========
    @consulta_bp.route('/<int:consulta_id>/internar')
    def internar_paciente(consulta_id):
        """Página para internar paciente a partir da consulta"""
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        medico_id = obter_medico_id()
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta or consulta.get('medico_id') != medico_id:
            flash('Consulta não encontrada ou você não tem permissão.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        # Verificar se já existe internação
        internacao_existente = execute_query("""
            SELECT id, status FROM internacoes 
            WHERE consulta_id = %s AND status IN ('ativa', 'internado')
        """, (consulta_id,), fetch=True, one=True)
        
        if internacao_existente:
            flash(f'Paciente já está internado!', 'warning')
            return redirect(url_for('medico.internacoes.gerenciar', internacao_id=internacao_existente[0]))
        
        return render_template('medico/internar_paciente.html',
                              consulta=consulta,
                              medico_id=medico_id)
    
    logger.info("Blueprint de consultas inicializado com sucesso")
    print("[OK] Blueprint de consultas registrado (versão completa com DIAGNÓSTICO e RECEITA DIGITAL)")
    
    return consulta_bp

# Exportar a função
__all__ = ['create_consulta_blueprint']
