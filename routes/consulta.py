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
            if medico:
                if isinstance(medico, dict):
                    return medico.get('id')
                return medico[0] if len(medico) > 0 else None
            return None
        except Exception as e:
            logger.error(f"Erro ao obter medico_id: {e}")
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
            if paciente:
                if isinstance(paciente, dict):
                    return paciente.get('id')
                return paciente[0] if len(paciente) > 0 else None
            return None
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
            if enfermeiro:
                if isinstance(enfermeiro, dict):
                    return enfermeiro.get('id')
                return enfermeiro[0] if len(enfermeiro) > 0 else None
            return None
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
        if not peso:
            return None
        
        try:
            peso = float(peso)
            return {"classificacao": f"{peso} kg", "status": "info"}
        except:
            return None
    
    # ========== FUNÇÃO PARA OBTER SINAIS VITAIS ==========
    def obter_sinais_vitais(consulta_id):
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
    
    # ========== FUNÇÃO PARA OBTER DIAGNÓSTICO ==========
    def obter_diagnostico(consulta_id):
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
    
    # ========== FUNÇÃO PRINCIPAL PARA OBTER DETALHES DA CONSULTA (CORRIGIDA) ==========
    def obter_detalhes_consulta(consulta_id):
        """Obtém detalhes completos de uma consulta - CORRIGIDO com todos os campos"""
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
                    c.diagnostico_texto,
                    c.diagnostico_ia,
                    c.resultado_exames,
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
                logger.warning(f"Consulta {consulta_id} não encontrada")
                return None
            
            medico_id_valor = None
            paciente_id_valor = None
            
            if isinstance(consulta, dict):
                # Caso seja dicionário
                medico_id_valor = consulta.get('medico_id')
                paciente_id_valor = consulta.get('paciente_id')
                
                # Se veio None, buscar diretamente do banco
                if medico_id_valor is None:
                    logger.warning(f"medico_id não encontrado no dicionário para consulta {consulta_id}")
                    result = execute_query(
                        "SELECT medico_id FROM consultas WHERE id = %s",
                        (consulta_id,), fetch=True, one=True
                    )
                    if result:
                        medico_id_valor = result[0] if isinstance(result, (tuple, list)) else result.get('medico_id')
                        logger.info(f"medico_id recuperado diretamente: {medico_id_valor}")
                
                # Calcular idade
                idade = None
                data_nasc = consulta.get('data_nascimento')
                if data_nasc:
                    try:
                        if isinstance(data_nasc, datetime):
                            data_nasc = data_nasc.date()
                        elif isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                        
                        hoje = date.today()
                        idade_calc = hoje.year - data_nasc.year
                        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                            idade_calc -= 1
                        idade = idade_calc
                    except Exception as e:
                        logger.error(f"Erro ao calcular idade: {e}")
                
                return {
                    'id': consulta.get('id'),
                    'medico_nome': str(consulta.get('medico_nome', '')),
                    'especialidade': str(consulta.get('especialidade', '')),
                    'crm': str(consulta.get('crm', '')),
                    'data_hora': formatar_data(consulta.get('data_hora')),
                    'data_hora_formatada': consulta.get('data_hora').strftime('%Y-%m-%dT%H:%M') if isinstance(consulta.get('data_hora'), datetime) else str(consulta.get('data_hora', '')),
                    'status': str(consulta.get('status', '')),
                    'observacoes': str(consulta.get('observacoes', '')),
                    'receita': str(consulta.get('receita', '')),
                    'paciente_nome': str(consulta.get('paciente_nome', '')),
                    'paciente_idade': f"{idade} anos" if idade else None,
                    'data_nascimento': formatar_data(consulta.get('data_nascimento'), '%d/%m/%Y') if consulta.get('data_nascimento') else None,
                    'genero': str(consulta.get('genero', 'Não informado')),
                    'paciente_telefone': str(consulta.get('paciente_telefone', 'Não informado')),
                    'paciente_endereco': str(consulta.get('paciente_endereco', 'Não informado')),
                    'medico_email': str(consulta.get('medico_email', '')),
                    'medico_telefone': str(consulta.get('medico_telefone', '')),
                    'paciente_id': paciente_id_valor,
                    'medico_id': medico_id_valor,
                    'paciente_email': str(consulta.get('paciente_email', '')),
                    'sintomas_raw': str(consulta.get('sintomas', '')),
                    'sintomas_lista': processar_sintomas(consulta.get('sintomas', '')),
                    'diagnostico_texto': str(consulta.get('diagnostico_texto', '')),
                    'diagnostico_ia': str(consulta.get('diagnostico_ia', '')),
                    'resultado_exames': str(consulta.get('resultado_exames', '')),
                    'dia_semana': mapear_dia_semana(consulta.get('dia_semana', '')),
                    'data_consulta': consulta.get('data_consulta').strftime('%Y-%m-%d') if isinstance(consulta.get('data_consulta'), datetime) else str(consulta.get('data_consulta', '')),
                    'hora_consulta': str(consulta.get('hora_consulta', '')),
                    'mes': consulta.get('mes'),
                    'mes_nome': mapear_mes(consulta.get('mes')) if consulta.get('mes') else '',
                    'ano': consulta.get('ano'),
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(consulta.get('status'), 'secondary')
                }
            
            else:
                # Caso seja tupla/lista
                num_fields = len(consulta) if consulta else 0
                
                # Extrair IDs
                paciente_id_valor = consulta[15] if num_fields > 15 else None
                medico_id_valor = consulta[16] if num_fields > 16 else None
                
                # Se medico_id veio None, buscar diretamente
                if medico_id_valor is None:
                    logger.warning(f"medico_id não encontrado na tupla para consulta {consulta_id}")
                    result = execute_query(
                        "SELECT medico_id FROM consultas WHERE id = %s",
                        (consulta_id,), fetch=True, one=True
                    )
                    if result:
                        medico_id_valor = result[0] if isinstance(result, (tuple, list)) else result.get('medico_id')
                        logger.info(f"medico_id recuperado diretamente: {medico_id_valor}")
                
                # Calcular idade
                idade = None
                if num_fields > 9 and consulta[9]:
                    try:
                        data_nasc = consulta[9]
                        if isinstance(data_nasc, datetime):
                            data_nasc = data_nasc.date()
                        elif isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                        
                        hoje = date.today()
                        idade_calc = hoje.year - data_nasc.year
                        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                            idade_calc -= 1
                        idade = idade_calc
                    except Exception as e:
                        logger.error(f"Erro ao calcular idade: {e}")
                
                # Processar sintomas
                sintomas_raw = ''
                if num_fields > 18 and consulta[18]:
                    sintomas_raw = str(consulta[18])
                sintomas_lista = processar_sintomas(sintomas_raw)
                
                # Processar campos de diagnóstico (índices 20, 21, 22)
                diagnostico_texto = ''
                if num_fields > 20 and consulta[20]:
                    diagnostico_texto = str(consulta[20])
                
                diagnostico_ia = ''
                if num_fields > 21 and consulta[21]:
                    diagnostico_ia = str(consulta[21])
                
                resultado_exames = ''
                if num_fields > 22 and consulta[22]:
                    resultado_exames = str(consulta[22])
                
                # Processar dia da semana (índice 23)
                dia_semana_pt = ''
                if num_fields > 23 and consulta[23]:
                    dia_semana_pt = mapear_dia_semana(consulta[23])
                
                # Processar mês (índice 26)
                mes_num = None
                if num_fields > 26 and consulta[26]:
                    mes_num = consulta[26]
                mes_pt = mapear_mes(mes_num) if mes_num else ''
                
                # Converter data_hora
                data_hora_obj = consulta[4] if num_fields > 4 else None
                if isinstance(data_hora_obj, str):
                    try:
                        data_hora_obj = datetime.strptime(data_hora_obj, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                
                # Processar data_consulta (índice 24)
                data_consulta_str = ''
                if num_fields > 24 and consulta[24]:
                    if isinstance(consulta[24], datetime):
                        data_consulta_str = consulta[24].strftime('%Y-%m-%d')
                    else:
                        data_consulta_str = str(consulta[24])
                
                # Processar hora_consulta (índice 25)
                hora_consulta_str = ''
                if num_fields > 25 and consulta[25]:
                    hora_consulta_str = str(consulta[25])
                
                # Processar ano (índice 27)
                ano_val = None
                if num_fields > 27 and consulta[27]:
                    ano_val = consulta[27]
                
                return {
                    'id': consulta[0] if num_fields > 0 else None,
                    'medico_nome': str(consulta[1]) if num_fields > 1 and consulta[1] else '',
                    'especialidade': str(consulta[2]) if num_fields > 2 and consulta[2] else '',
                    'crm': str(consulta[3]) if num_fields > 3 and consulta[3] else '',
                    'data_hora': formatar_data(data_hora_obj),
                    'data_hora_formatada': data_hora_obj.strftime('%Y-%m-%dT%H:%M') if isinstance(data_hora_obj, datetime) else str(data_hora_obj),
                    'status': str(consulta[5]) if num_fields > 5 and consulta[5] else '',
                    'observacoes': str(consulta[6]) if num_fields > 6 and consulta[6] else '',
                    'receita': str(consulta[7]) if num_fields > 7 and consulta[7] else '',
                    'paciente_nome': str(consulta[8]) if num_fields > 8 and consulta[8] else '',
                    'paciente_idade': f"{idade} anos" if idade else None,
                    'data_nascimento': formatar_data(consulta[9], '%d/%m/%Y') if num_fields > 9 and consulta[9] else None,
                    'genero': str(consulta[10]) if num_fields > 10 and consulta[10] else 'Não informado',
                    'paciente_telefone': str(consulta[11]) if num_fields > 11 and consulta[11] else 'Não informado',
                    'paciente_endereco': str(consulta[12]) if num_fields > 12 and consulta[12] else 'Não informado',
                    'medico_email': str(consulta[13]) if num_fields > 13 and consulta[13] else '',
                    'medico_telefone': str(consulta[14]) if num_fields > 14 and consulta[14] else '',
                    'paciente_id': paciente_id_valor,
                    'medico_id': medico_id_valor,
                    'paciente_email': str(consulta[17]) if num_fields > 17 and consulta[17] else '',
                    'sintomas_raw': sintomas_raw,
                    'sintomas_lista': sintomas_lista,
                    'diagnostico_texto': diagnostico_texto,
                    'diagnostico_ia': diagnostico_ia,
                    'resultado_exames': resultado_exames,
                    'dia_semana': dia_semana_pt,
                    'data_consulta': data_consulta_str,
                    'hora_consulta': hora_consulta_str,
                    'mes': mes_num,
                    'mes_nome': mes_pt,
                    'ano': ano_val,
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(consulta[5] if num_fields > 5 else '', 'secondary')
                }
                
        except Exception as e:
            logger.error(f"Erro ao obter detalhes da consulta: {e}")
            logger.error(traceback.format_exc())
            return None
    
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
        """Detalhes de uma consulta específica"""
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        usuario_tipo = session.get('user_type')
        
        # Obter detalhes da consulta
        consulta = obter_detalhes_consulta(consulta_id)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            if usuario_tipo == 'medico':
                return redirect(url_for('medico.consultas'))
            elif usuario_tipo == 'paciente':
                return redirect(url_for('paciente.consultas'))
            else:
                return redirect(url_for('auth.index'))
        
        # LOG para debug
        print(f"\n[DEBUG] Consulta {consulta_id}: medico_id={consulta.get('medico_id')}, paciente_id={consulta.get('paciente_id')}")
        
        # Verificar permissão de acesso - CORRIGIDO
        tem_acesso = False
        
        if usuario_tipo == 'admin':
            tem_acesso = True
        elif usuario_tipo == 'medico':
            medico_id = obter_medico_id()
            consulta_medico_id = consulta.get('medico_id')
            
            # CORREÇÃO: Comparar como inteiros
            if consulta_medico_id and medico_id:
                try:
                    if int(consulta_medico_id) == int(medico_id):
                        tem_acesso = True
                        print(f"[DEBUG] Acesso concedido: médico {medico_id} é o responsável")
                    else:
                        print(f"[DEBUG] Acesso negado: médico {medico_id} vs consulta_medico_id {consulta_medico_id}")
                except (ValueError, TypeError) as e:
                    print(f"[DEBUG] Erro na comparação: {e}")
            else:
                print(f"[DEBUG] Acesso negado: medico_id={medico_id}, consulta_medico_id={consulta_medico_id}")
                
        elif usuario_tipo == 'paciente':
            paciente_id = obter_paciente_id()
            consulta_paciente_id = consulta.get('paciente_id')
            
            if consulta_paciente_id and paciente_id and int(consulta_paciente_id) == int(paciente_id):
                tem_acesso = True
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
    
    # ========== ROTA PARA SALVAR SINAIS VITAIS ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais', methods=['POST'])
    def salvar_sinais_vitais(consulta_id):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Não autorizado'}), 401
        
        try:
            usuario_tipo = session.get('user_type')
            enfermeiro_id = None
            
            if usuario_tipo == 'enfermeiro':
                enfermeiro_id = obter_enfermeiro_id()
            
            pressao_arterial = request.form.get('pressao_arterial')
            frequencia_cardiaca = request.form.get('frequencia_cardiaca')
            frequencia_respiratoria = request.form.get('frequencia_respiratoria')
            temperatura = request.form.get('temperatura')
            saturacao_oxigenio = request.form.get('saturacao_oxigenio')
            glicemia = request.form.get('glicemia')
            peso = request.form.get('peso')
            observacoes = request.form.get('observacoes', '')
            
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
            
            if enfermeiro_id:
                execute_query("""
                    INSERT INTO sinais_vitais 
                    (consulta_id, enfermeiro_id, pressao_arterial, frequencia_cardiaca, 
                     frequencia_respiratoria, temperatura, saturacao_oxigenio, glicemia, 
                     peso, observacoes, data_afericao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (consulta_id, enfermeiro_id, pressao_arterial, frequencia_cardiaca, 
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
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ========== ROTA PARA BUSCAR SINAIS VITAIS ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais', methods=['GET'])
    def get_sinais_vitais(consulta_id):
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
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
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
    
    logger.info("Blueprint de consultas inicializado com sucesso")
    print("[OK] Blueprint de consultas registrado (versão completa com DIAGNÓSTICO e RECEITA DIGITAL)")
    
    return consulta_bp

# Exportar a função
__all__ = ['create_consulta_blueprint']
