from flask import render_template, session, redirect, url_for, flash
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging

logger = logging.getLogger(__name__)


@farmaceutico_bp.route('/dispensacoes')
def dispensacoes():
    """Lista de dispensacoes realizadas"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        # Buscar receitas ja dispensadas - REMOVENDO coluna m.especialidade
        dispensas_raw = execute_query_auth("""
            SELECT r.id, r.created_at, r.status, r.diagnostico,
                   p.nome as paciente_nome,
                   m.nome as medico_nome,
                   r.data_geracao_pdf,
                   r.receita_pdf_path
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN pacientes pac ON c.paciente_id = pac.id
            JOIN usuarios p ON pac.usuario_id = p.id
            JOIN medicos med ON c.medico_id = med.id
            JOIN usuarios m ON med.usuario_id = m.id
            WHERE r.status = 'dispensada'
            ORDER BY r.data_geracao_pdf DESC
            LIMIT 100
        """, fetch=True) or []
        
        # Converter para dicionarios
        dispensas = []
        for d in dispensas_raw:
            dispensas.append({
                'id': d[0],
                'created_at': d[1],
                'status': d[2],
                'diagnostico': d[3] if not isinstance(d[3], bytes) else d[3].decode('utf-8', errors='ignore'),
                'paciente_nome': d[4] if not isinstance(d[4], bytes) else d[4].decode('utf-8', errors='ignore'),
                'medico_nome': d[5] if not isinstance(d[5], bytes) else d[5].decode('utf-8', errors='ignore'),
                'data_geracao_pdf': d[6],
                'receita_pdf_path': d[7]
            })
        
        return render_template('farmaceutico/dispensacoes.html',
                             dispensas=dispensas,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro ao listar dispensacoes: {e}")
        print(f"ERRO em dispensacoes: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar dispensacoes.', 'danger')
        return redirect(url_for('farmaceutico.dashboard'))


@farmaceutico_bp.route('/dispensacao/<int:id>')
def dispensacao_detalhe(id):
    """Detalhes de uma dispensacao"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        resultado = execute_query_auth("""
            SELECT r.id, r.created_at, r.diagnostico, r.prescricao, r.recomendacoes,
                   p.nome as paciente_nome, p.telefone, p.email,
                   m.nome as medico_nome,
                   r.data_geracao_pdf, r.receita_pdf_path
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN pacientes pac ON c.paciente_id = pac.id
            JOIN usuarios p ON pac.usuario_id = p.id
            JOIN medicos med ON c.medico_id = med.id
            JOIN usuarios m ON med.usuario_id = m.id
            WHERE r.id = %s AND r.status = 'dispensada'
        """, (id,), True)
        
        if not resultado:
            flash('Dispensa nao encontrada.', 'danger')
            return redirect(url_for('farmaceutico.dispensacoes'))
        
        dispensa_raw = resultado[0]
        
        # Converter para dicionario
        dispensa = {
            'id': dispensa_raw[0],
            'created_at': dispensa_raw[1],
            'diagnostico': dispensa_raw[2] if not isinstance(dispensa_raw[2], bytes) else dispensa_raw[2].decode('utf-8', errors='ignore'),
            'prescricao': dispensa_raw[3] if not isinstance(dispensa_raw[3], bytes) else dispensa_raw[3].decode('utf-8', errors='ignore'),
            'recomendacoes': dispensa_raw[4] if not isinstance(dispensa_raw[4], bytes) else dispensa_raw[4].decode('utf-8', errors='ignore'),
            'paciente_nome': dispensa_raw[5] if not isinstance(dispensa_raw[5], bytes) else dispensa_raw[5].decode('utf-8', errors='ignore'),
            'telefone': dispensa_raw[6],
            'email': dispensa_raw[7],
            'medico_nome': dispensa_raw[8] if not isinstance(dispensa_raw[8], bytes) else dispensa_raw[8].decode('utf-8', errors='ignore'),
            'data_geracao_pdf': dispensa_raw[9],
            'receita_pdf_path': dispensa_raw[10]
        }
        
        return render_template('farmaceutico/dispensacao_detalhe.html',
                             dispensa=dispensa,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro ao ver dispensa: {e}")
        print(f"ERRO em dispensacao_detalhe: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar dispensa.', 'danger')
        return redirect(url_for('farmaceutico.dispensacoes'))