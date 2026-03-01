# routes/medico/consulta/api.py
from datetime import datetime
from flask import request, jsonify,session
from .decorators import login_required
from .utils import execute_query, obter_medico_id, obter_paciente_id

def register_api_routes(bp, mysql):
    
    @bp.route('/api/disponibilidade', methods=['GET'])
    def api_disponibilidade():
        """API para verificar disponibilidade de horários"""
        medico_id = request.args.get('medico_id')
        data = request.args.get('data')
        
        if not medico_id or not data:
            return jsonify({'error': 'Parâmetros incompletos'}), 400
        
        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d')
            
            horarios_ocupados = execute_query(mysql,
                """SELECT TIME(data_hora) as hora
                FROM consultas
                WHERE medico_id = %s AND DATE(data_hora) = %s AND status != 'cancelada'""",
                (medico_id, data_obj.strftime('%Y-%m-%d')), True
            ) or []
            
            ocupados = [h[0].strftime('%H:%M') for h in horarios_ocupados]
            
            disponiveis = []
            for hora in range(8, 18):
                for minuto in [0, 30]:
                    horario = f"{hora:02d}:{minuto:02d}"
                    if horario not in ocupados:
                        disponiveis.append(horario)
            
            return jsonify({
                'disponiveis': disponiveis,
                'ocupados': ocupados
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/api/calendario')
    @login_required
    def api_calendario():
        """API para obter consultas para calendário"""
        usuario_tipo = session.get('user_type')
        
        try:
            eventos = []
            
            if usuario_tipo == 'paciente':
                paciente_id = obter_paciente_id(mysql, session)
                consultas = execute_query(mysql,
                    """SELECT c.id, m_u.nome as medico_nome, c.data_hora, c.status
                    FROM consultas c
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE c.paciente_id = %s
                    ORDER BY c.data_hora""",
                    (paciente_id,), True
                ) or []
                
                for c in consultas:
                    eventos.append({
                        'id': c[0],
                        'title': f"Consulta com Dr(a). {c[1]}",
                        'start': c[2].isoformat() if isinstance(c[2], datetime) else str(c[2]),
                        'status': c[3],
                        'className': f'consulta-{c[3]}'
                    })
                    
            elif usuario_tipo == 'medico':
                medico_id = obter_medico_id(mysql, session)
                consultas = execute_query(mysql,
                    """SELECT c.id, p_u.nome as paciente_nome, c.data_hora, c.status
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios p_u ON p.usuario_id = p_u.id
                    WHERE c.medico_id = %s
                    ORDER BY c.data_hora""",
                    (medico_id,), True
                ) or []
                
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
            return jsonify({'error': str(e)}), 500