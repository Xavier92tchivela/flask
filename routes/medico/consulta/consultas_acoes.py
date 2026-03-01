# routes/medico/consulta/acoes.py
from flask import request, jsonify, flash, redirect, url_for,session
from .decorators import login_required, medico_required
from .utils import execute_query, obter_medico_id, obter_paciente_id

def register_acoes_routes(bp, mysql):
    
    @bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
    @login_required
    def cancelar_consulta(consulta_id):
        """Cancelar uma consulta"""
        usuario_tipo = session.get('user_type')
        
        # Verificar se a consulta existe
        consulta = execute_query(mysql, 
            "SELECT status FROM consultas WHERE id = %s", 
            (consulta_id,), True
        )
        
        if not consulta:
            return jsonify({'error': 'Consulta não encontrada'}), 404
        
        # Verificar permissões
        if usuario_tipo == 'paciente':
            paciente_id = obter_paciente_id(mysql, session)
            if not paciente_id:
                return jsonify({'error': 'Paciente não encontrado'}), 403
            
            consulta_paciente = execute_query(mysql,
                "SELECT id FROM consultas WHERE id = %s AND paciente_id = %s",
                (consulta_id, paciente_id), True
            )
            
            if not consulta_paciente:
                return jsonify({'error': 'Você não tem permissão para cancelar esta consulta'}), 403
        
        # Cancelar consulta
        execute_query(mysql,
            "UPDATE consultas SET status = 'cancelada' WHERE id = %s",
            (consulta_id,)
        )
        
        return jsonify({
            'success': True,
            'message': 'Consulta cancelada com sucesso!'
        })
    
    @bp.route('/<int:consulta_id>/confirmar', methods=['POST'])
    @login_required
    def confirmar_consulta(consulta_id):
        """Confirmar uma consulta"""
        usuario_tipo = session.get('user_type')
        
        if usuario_tipo not in ['medico', 'admin']:
            return jsonify({'error': 'Acesso não autorizado'}), 403
        
        execute_query(mysql,
            "UPDATE consultas SET status = 'confirmada' WHERE id = %s",
            (consulta_id,)
        )
        
        return jsonify({
            'success': True,
            'message': 'Consulta confirmada com sucesso!'
        })
    
    @bp.route('/<int:consulta_id>/realizar', methods=['POST'])
    @medico_required
    def realizar_consulta(consulta_id):
        """Marcar consulta como realizada"""
        medico_id = obter_medico_id(mysql, session)
        
        consulta_medico = execute_query(mysql,
            "SELECT id FROM consultas WHERE id = %s AND medico_id = %s",
            (consulta_id, medico_id), True
        )
        
        if not consulta_medico:
            return jsonify({'error': 'Você não tem permissão para realizar esta consulta'}), 403
        
        execute_query(mysql,
            "UPDATE consultas SET status = 'realizada' WHERE id = %s",
            (consulta_id,)
        )
        
        return jsonify({
            'success': True,
            'message': 'Consulta marcada como realizada!'
        })