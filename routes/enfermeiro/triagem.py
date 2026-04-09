from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import date
from .utils import execute_query, enfermeiro_required
import logging

logger = logging.getLogger(__name__)

triagem_bp = Blueprint('triagem', __name__, url_prefix='/triagem')

# Atributo para armazenar a conexão MySQL
triagem_bp.mysql = None

def set_mysql(mysql_instance):
    triagem_bp.mysql = mysql_instance

@triagem_bp.route('')
@enfermeiro_required
def listar_consultas_triagem():
    """Lista consultas para triagem"""
    enfermeiro_id = session.get('enfermeiro_id')
    hoje = date.today()
    
    # Buscar consultas do dia
    consultas = execute_query("""
        SELECT 
            c.id,
            u.nome as paciente_nome,
            p.id as paciente_id,
            DATE_FORMAT(c.data_hora, '%%H:%%i') as hora_chegada,
            COALESCE(c.status_triagem, 'NAO_REALIZADA') as status_triagem,
            c.status,
            CASE 
                WHEN c.status_triagem = 'REALIZADA' THEN 
                    (SELECT COUNT(*) FROM sinais_vitais WHERE consulta_id = c.id)
                ELSE 0
            END as tem_sinais_vitais
        FROM consultas c
        INNER JOIN pacientes p ON c.paciente_id = p.id
        INNER JOIN usuarios u ON p.usuario_id = u.id
        WHERE DATE(c.data_hora) = %s
        ORDER BY c.data_hora ASC
    """, (hoje,), fetch=True) or []
    
    logger.info(f"Triagem: {len(consultas)} consultas encontradas para hoje")
    
    return render_template('enfermeiro/consultas/listar.html', 
                         consultas=consultas,
                         hoje=hoje)

@triagem_bp.route('/<int:consulta_id>/realizar')
@enfermeiro_required
def realizar_triagem(consulta_id):
    """Redireciona para página de registro de sinais vitais"""
    return redirect(url_for('enfermeiro.sinais_vitais.registrar_sinais_vitais', consulta_id=consulta_id))