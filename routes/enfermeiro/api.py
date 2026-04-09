from flask import Blueprint, jsonify, url_for, session
from datetime import datetime
import logging
from .utils import execute_query, enfermeiro_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Atributo para armazenar a conexão MySQL
api_bp.mysql = None

def set_mysql(mysql_instance):
    api_bp.mysql = mysql_instance

@api_bp.route('/consulta/<int:consulta_id>/detalhes')
@enfermeiro_required
def api_consulta_detalhes(consulta_id):
    logger.info(f"=== API DETALHES CONSULTA ID: {consulta_id} ===")
    
    try:
        consulta = execute_query("""
            SELECT 
                c.id,
                u.nome as paciente_nome,
                p.id as paciente_id,
                DATE_FORMAT(p.data_nascimento, '%%d/%%m/%%Y') as data_nascimento,
                p.genero,
                DATE_FORMAT(c.data_hora, '%%d/%%m/%%Y %%H:%%i') as data_hora,
                COALESCE(m_u.nome, 'Não atribuído') as medico_nome,
                c.status,
                COALESCE(c.status_triagem, 'NAO_REALIZADA') as status_triagem,
                c.sintomas,
                c.observacoes,
                CASE 
                    WHEN EXISTS (SELECT 1 FROM sinais_vitais WHERE consulta_id = c.id) THEN 1
                    ELSE 0
                END as tem_sinais_vitais,
                (SELECT id FROM sinais_vitais WHERE consulta_id = c.id LIMIT 1) as vital_id
            FROM consultas c
            INNER JOIN pacientes p ON c.paciente_id = p.id
            INNER JOIN usuarios u ON p.usuario_id = u.id
            LEFT JOIN medicos m ON c.medico_id = m.id
            LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s
        """, (consulta_id,), fetch=True, one=True)
        
        if not consulta:
            logger.warning(f"Consulta ID {consulta_id} não encontrada")
            return jsonify({'success': False, 'message': 'Consulta não encontrada'})
        
        logger.info(f"Dados encontrados: ID={consulta['id']}, Paciente={consulta['paciente_nome']}")
        
        status_cores = {
            'AGUARDANDO': 'warning',
            'agendada': 'warning',
            'EM_ATENDIMENTO': 'info',
            'REALIZADA': 'success',
            'CANCELADA': 'danger'
        }
        
        triagem_cores = {
            'REALIZADA': 'success',
            'NAO_REALIZADA': 'warning'
        }
        
        url_sinais_vitais = None
        if consulta.get('vital_id'):
            url_sinais_vitais = url_for('enfermeiro.sinais_vitais.detalhes_sinais_vitais', 
                                       vital_id=consulta['vital_id'], _external=False)
            logger.info(f"URL sinais vitais: {url_sinais_vitais}")
        
        return jsonify({
            'success': True,
            'consulta': {
                'id': consulta['id'],
                'paciente_nome': consulta['paciente_nome'],
                'paciente_id': consulta['paciente_id'],
                'data_nascimento': consulta['data_nascimento'] if consulta['data_nascimento'] else 'Não informado',
                'genero': consulta['genero'] if consulta['genero'] else 'Não informado',
                'data_hora': consulta['data_hora'],
                'medico_nome': consulta['medico_nome'],
                'status': consulta['status'],
                'status_cor': status_cores.get(consulta['status'], 'secondary'),
                'status_triagem': consulta['status_triagem'],
                'triagem_cor': triagem_cores.get(consulta['status_triagem'], 'secondary'),
                'sintomas': consulta['sintomas'] if consulta['sintomas'] else '',
                'observacoes': consulta['observacoes'] if consulta['observacoes'] else '',
                'tem_sinais_vitais': bool(consulta['tem_sinais_vitais']),
                'url_sinais_vitais': url_sinais_vitais
            }
        })
        
    except Exception as e:
        logger.error(f"Erro na API: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

@api_bp.route('/paciente/<int:paciente_id>/ultimos-sinais')
@enfermeiro_required
def api_ultimos_sinais(paciente_id):
    enfermeiro_id = session.get('enfermeiro_id')
    
    if not enfermeiro_id:
        user_id = session.get('user_id')
        result = execute_query(
            "SELECT id FROM enfermeiros WHERE usuario_id = %s", 
            (user_id,), fetch=True, one=True
        )
        if result:
            enfermeiro_id = result['id']
    
    sinais = execute_query("""
        SELECT 
            sv.data_afericao,
            sv.pressao_arterial,
            sv.frequencia_cardiaca,
            sv.temperatura,
            sv.saturacao_oxigenio
        FROM sinais_vitais sv
        INNER JOIN consultas c ON sv.consulta_id = c.id
        WHERE sv.enfermeiro_id = %s AND c.paciente_id = %s
        ORDER BY sv.data_afericao DESC
        LIMIT 5
    """, (enfermeiro_id, paciente_id), fetch=True) or []
    
    resultado = []
    for s in sinais:
        resultado.append({
            'data': s['data_afericao'].strftime('%d/%m/%Y %H:%M') if hasattr(s['data_afericao'], 'strftime') else str(s['data_afericao']),
            'pressao': s['pressao_arterial'],
            'fc': s['frequencia_cardiaca'],
            'temp': float(s['temperatura']) if s['temperatura'] else None,
            'sat': s['saturacao_oxigenio']
        })
    
    return jsonify(resultado)