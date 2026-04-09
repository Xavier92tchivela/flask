from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from .utils import execute_query, enfermeiro_required, formatar_data, formatar_data_hora

logger = logging.getLogger(__name__)

perfil_bp = Blueprint('perfil', __name__, url_prefix='/perfil')

# Atributo para armazenar a conexão MySQL
perfil_bp.mysql = None

def set_mysql(mysql_instance):
    perfil_bp.mysql = mysql_instance

# ===== FUNÇÃO AUXILIAR PARA CONVERTER BYTES =====
def garantir_string(valor):
    """Converte bytes para string se necessário"""
    if valor is None:
        return ''
    if isinstance(valor, bytes):
        try:
            return valor.decode('utf-8')
        except:
            return str(valor)
    if isinstance(valor, (int, float)):
        return str(valor)
    return str(valor) if valor is not None else ''

@perfil_bp.route('')
@enfermeiro_required
def perfil():
    enfermeiro_id = session.get('enfermeiro_id')
    
    # Se não tiver enfermeiro_id, buscar do usuário
    if not enfermeiro_id:
        user_id = session.get('user_id')
        result = execute_query(
            "SELECT id FROM enfermeiros WHERE usuario_id = %s", 
            (user_id,), fetch=True, one=True
        )
        if result:
            if isinstance(result, dict):
                enfermeiro_id = result.get('id')
            else:
                enfermeiro_id = result[0] if isinstance(result, (list, tuple)) else result
            session['enfermeiro_id'] = enfermeiro_id
    
    if not enfermeiro_id:
        flash('Enfermeiro não encontrado', 'danger')
        return redirect(url_for('auth.login'))
    
    # Buscar dados do enfermeiro
    enfermeiro = execute_query("""
        SELECT 
            e.id,
            e.coren,
            e.especialidade,
            e.data_cadastro,
            e.ativo,
            u.nome,
            u.email,
            u.telefone,
            u.foto_perfil
        FROM enfermeiros e
        INNER JOIN usuarios u ON e.usuario_id = u.id
        WHERE e.id = %s
    """, (enfermeiro_id,), fetch=True, one=True)
    
    if not enfermeiro:
        flash('Perfil não encontrado.', 'danger')
        return redirect(url_for('enfermeiro.dashboard.index'))
    
    # Converter bytes para string em todos os campos
    if isinstance(enfermeiro, dict):
        enfermeiro = {k: garantir_string(v) if not isinstance(v, (int, float, bool)) and v is not None else v 
                     for k, v in enfermeiro.items()}
    
    # Total de aferições
    total_afericoes_result = execute_query("""
        SELECT COUNT(*) as total FROM sinais_vitais WHERE enfermeiro_id = %s
    """, (enfermeiro_id,), fetch=True, one=True)
    total_afericoes = 0
    if total_afericoes_result:
        if isinstance(total_afericoes_result, dict):
            total_afericoes = total_afericoes_result.get('total', 0)
        else:
            total_afericoes = total_afericoes_result[0] if isinstance(total_afericoes_result, (list, tuple)) else total_afericoes_result
    
    # Média por dia (últimos 30 dias)
    media_dia_result = execute_query("""
        SELECT ROUND(COUNT(*) / 30, 1) as media
        FROM sinais_vitais 
        WHERE enfermeiro_id = %s 
        AND data_afericao >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """, (enfermeiro_id,), fetch=True, one=True)
    media_dia = 0
    if media_dia_result:
        if isinstance(media_dia_result, dict):
            media_dia = media_dia_result.get('media', 0)
        else:
            media_dia = media_dia_result[0] if isinstance(media_dia_result, (list, tuple)) else media_dia_result
    
    # Pacientes únicos atendidos
    pacientes_unicos_result = execute_query("""
        SELECT COUNT(DISTINCT c.paciente_id) as total
        FROM sinais_vitais sv
        INNER JOIN consultas c ON sv.consulta_id = c.id
        WHERE sv.enfermeiro_id = %s
    """, (enfermeiro_id,), fetch=True, one=True)
    pacientes_unicos = 0
    if pacientes_unicos_result:
        if isinstance(pacientes_unicos_result, dict):
            pacientes_unicos = pacientes_unicos_result.get('total', 0)
        else:
            pacientes_unicos = pacientes_unicos_result[0] if isinstance(pacientes_unicos_result, (list, tuple)) else pacientes_unicos_result
    
    # Últimas atividades
    ultimas_atividades = execute_query("""
        (SELECT 
            'Aferição' as descricao,
            CONCAT('Paciente: ', u.nome) as detalhes,
            sv.data_afericao as data,
            'primary' as cor,
            'heartbeat' as icone
        FROM sinais_vitais sv
        INNER JOIN consultas c ON sv.consulta_id = c.id
        INNER JOIN pacientes p ON c.paciente_id = p.id
        INNER JOIN usuarios u ON p.usuario_id = u.id
        WHERE sv.enfermeiro_id = %s
        ORDER BY sv.data_afericao DESC
        LIMIT 10)
        UNION ALL
        (SELECT 
            'Triagem' as descricao,
            CONCAT('Paciente: ', u.nome) as detalhes,
            c.data_hora as data,
            'success' as cor,
            'clipboard-list' as icone
        FROM consultas c
        INNER JOIN pacientes p ON c.paciente_id = p.id
        INNER JOIN usuarios u ON p.usuario_id = u.id
        WHERE c.enfermeiro_id = %s AND c.status_triagem = 'REALIZADA'
        ORDER BY c.data_hora DESC
        LIMIT 10)
        ORDER BY data DESC
        LIMIT 10
    """, (enfermeiro_id, enfermeiro_id), fetch=True) or []
    
    # Converter bytes nas atividades
    atividades_processadas = []
    for atividade in ultimas_atividades:
        if isinstance(atividade, dict):
            atividade = {k: garantir_string(v) if not isinstance(v, (int, float, bool)) and v is not None else v 
                        for k, v in atividade.items()}
        atividades_processadas.append(atividade)
    
    return render_template('enfermeiro/perfil.html',
                         enfermeiro=enfermeiro,
                         total_afericoes=total_afericoes,
                         media_afericoes_dia=media_dia,
                         pacientes_unicos=pacientes_unicos,
                         ultimas_atividades=atividades_processadas,
                         formatar_data=formatar_data,
                         formatar_data_hora=formatar_data_hora)

@perfil_bp.route('/atualizar', methods=['POST'])
@enfermeiro_required
def atualizar_perfil():
    enfermeiro_id = session.get('enfermeiro_id')
    telefone = request.form.get('telefone')
    especialidade = request.form.get('especialidade')
    
    # Atualizar telefone no usuário
    execute_query("""
        UPDATE usuarios u
        INNER JOIN enfermeiros e ON u.id = e.usuario_id
        SET u.telefone = %s
        WHERE e.id = %s
    """, (telefone, enfermeiro_id))
    
    # Atualizar especialidade no enfermeiro
    execute_query("""
        UPDATE enfermeiros
        SET especialidade = %s
        WHERE id = %s
    """, (especialidade, enfermeiro_id))
    
    flash('Perfil atualizado com sucesso!', 'success')
    return redirect(url_for('enfermeiro.perfil.perfil'))

@perfil_bp.route('/alterar-senha', methods=['POST'])
@enfermeiro_required
def alterar_senha():
    user_id = session.get('user_id')
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    
    # Verificar senha atual
    usuario = execute_query("""
        SELECT senha FROM usuarios WHERE id = %s
    """, (user_id,), fetch=True, one=True)
    
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('enfermeiro.perfil.perfil'))
    
    # Extrair senha do resultado
    senha_hash = None
    if isinstance(usuario, dict):
        senha_hash = usuario.get('senha')
    else:
        senha_hash = usuario[0] if isinstance(usuario, (list, tuple)) else usuario
    
    if not senha_hash or not check_password_hash(senha_hash, senha_atual):
        flash('Senha atual incorreta.', 'danger')
        return redirect(url_for('enfermeiro.perfil.perfil'))
    
    # Atualizar senha
    nova_senha_hash = generate_password_hash(nova_senha)
    execute_query("""
        UPDATE usuarios SET senha = %s WHERE id = %s
    """, (nova_senha_hash, user_id))
    
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('enfermeiro.perfil.perfil'))