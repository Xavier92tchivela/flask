# routes/paciente/__init__.py
"""
Blueprint do Paciente - Módulo principal

Este arquivo inicializa o blueprint do paciente com todas as suas rotas.
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """
    Inicializa e retorna o blueprint do paciente
    
    Args:
        mysql: Instância da conexão MySQL
        app: Instância do aplicativo Flask
    
    Returns:
        Blueprint configurado
    """
    
    # Criar o blueprint
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    # ========== FUNÇÃO PARA CONVERTER BYTES ==========
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
    
    # ========== FUNÇÕES AUXILIARES ==========
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if not data:
            return ''
        from datetime import datetime, date
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, date):
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
    
    def obter_paciente_id():
        """Obtém o ID do paciente logado"""
        from flask import session
        
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            result = cur.fetchone()
            cur.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Erro ao obter paciente_id: {e}")
            return None
    
    # ========== DECORATOR ==========
    from functools import wraps
    from flask import session, redirect, url_for, flash
    
    def paciente_required(f):
        """Decorator para garantir que o usuário é um paciente"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== ROTA: DASHBOARD ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        from datetime import datetime, date
        
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE p.id = %s
        """, (paciente_id,))
        paciente_info = cur.fetchone()
        
        paciente_nome = garantir_string(paciente_info[0]) if paciente_info else session.get('user_name')
        paciente_data_nasc = formatar_data(paciente_info[1], '%d/%m/%Y') if paciente_info and paciente_info[1] else None
        paciente_genero = garantir_string(paciente_info[2]) if paciente_info else None
        paciente_telefone = garantir_string(paciente_info[3]) if paciente_info else None
        paciente_endereco = garantir_string(paciente_info[4]) if paciente_info else None
        paciente_email = garantir_string(paciente_info[5]) if paciente_info else None
        
        # Buscar consultas
        cur.execute("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, 
                   c.data_hora, c.status
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC
            LIMIT 10
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        
        # Contar consultas por status
        cur.execute("""
            SELECT 
                SUM(CASE WHEN status = 'agendada' THEN 1 ELSE 0 END) as agendadas,
                SUM(CASE WHEN status = 'realizada' THEN 1 ELSE 0 END) as realizadas,
                SUM(CASE WHEN status = 'cancelada' THEN 1 ELSE 0 END) as canceladas,
                COUNT(*) as total
            FROM consultas 
            WHERE paciente_id = %s
        """, (paciente_id,))
        stats_row = cur.fetchone()
        
        consultas_agendadas = stats_row[0] if stats_row and stats_row[0] else 0
        consultas_realizadas = stats_row[1] if stats_row and stats_row[1] else 0
        consultas_canceladas = stats_row[2] if stats_row and stats_row[2] else 0
        total_consultas = stats_row[3] if stats_row and stats_row[3] else 0
        
        cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
        consultas_hoje = cur.fetchone()[0] or 0
        cur.close()
        
        consultas = []
        for c in consultas_raw:
            consultas.append({
                'id': c[0],
                'medico_nome': garantir_string(c[1]),
                'especialidade': garantir_string(c[2]),
                'data_hora': formatar_data(c[3]),
                'status': garantir_string(c[4]),
                'status_class': {
                    'agendada': 'warning',
                    'realizada': 'success',
                    'cancelada': 'danger',
                    'confirmada': 'info'
                }.get(c[4], 'secondary')
            })
        
        stats = {
            'total_consultas': total_consultas,
            'consultas_hoje': consultas_hoje
        }
        
        return render_template('paciente/dashboard.html', 
                               consultas=consultas,
                               stats=stats,
                               consultas_agendadas=consultas_agendadas,
                               consultas_realizadas=consultas_realizadas,
                               consultas_canceladas=consultas_canceladas,
                               paciente_id=paciente_id,
                               paciente_nome=paciente_nome,
                               paciente_data_nasc=paciente_data_nasc,
                               paciente_genero=paciente_genero,
                               paciente_telefone=paciente_telefone,
                               paciente_endereco=paciente_endereco,
                               paciente_email=paciente_email,
                               user=session)
    
    # ========== ROTA: MINHAS CONSULTAS ==========
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, c.data_hora, c.status
            FROM consultas c
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.paciente_id = %s
            ORDER BY c.data_hora DESC
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        cur.close()
        
        consultas_formatadas = []
        for c in consultas_raw:
            status_classes = {
                'agendada': 'warning',
                'realizada': 'success',
                'cancelada': 'danger',
                'confirmada': 'info'
            }
            
            consultas_formatadas.append({
                'id': c[0],
                'medico_nome': garantir_string(c[1]),
                'especialidade': garantir_string(c[2]),
                'data_hora': formatar_data(c[3]),
                'status': garantir_string(c[4]),
                'status_class': status_classes.get(c[4], 'secondary')
            })
        
        return render_template('paciente/consultas.html',
                               consultas=consultas_formatadas,
                               user=session)
    
    # ========== ROTA: PERFIL ==========
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        
        if request.method == 'POST':
            telefone = request.form.get('telefone', '')
            endereco = request.form.get('endereco', '')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero', '')
            alergias = request.form.get('alergias', '')
            medicamentos_uso = request.form.get('medicamentos_uso', '')
            historico_doencas = request.form.get('historico_doencas', '')
            contato_emergencia = request.form.get('contato_emergencia', '')
            
            try:
                cur = mysql.connection.cursor()
                cur.execute("""
                    UPDATE pacientes 
                    SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s,
                        alergias=%s, medicamentos_uso=%s, historico_doencas=%s, contato_emergencia=%s
                    WHERE id=%s
                """, (telefone, endereco, data_nascimento, genero,
                      alergias, medicamentos_uso, historico_doencas, contato_emergencia, paciente_id))
                mysql.connection.commit()
                cur.close()
                flash('Perfil atualizado com sucesso!', 'success')
            except Exception as e:
                logger.error(f"Erro ao atualizar perfil: {e}")
                flash('Erro ao atualizar perfil.', 'danger')
            
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email,
                   p.alergias, p.medicamentos_uso, p.historico_doencas, p.contato_emergencia
            FROM pacientes p
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE p.id = %s
        """, (paciente_id,))
        info = cur.fetchone()
        cur.close()
        
        return render_template('paciente/perfil.html',
                               paciente_nome=garantir_string(info[0]) if info else '',
                               data_nascimento=info[1] if info else None,
                               genero=garantir_string(info[2]) if info else '',
                               telefone=garantir_string(info[3]) if info else '',
                               endereco=garantir_string(info[4]) if info else '',
                               email=garantir_string(info[5]) if info else '',
                               alergias=garantir_string(info[6]) if info else '',
                               medicamentos_uso=garantir_string(info[7]) if info else '',
                               historico_doencas=garantir_string(info[8]) if info else '',
                               contato_emergencia=garantir_string(info[9]) if info else '',
                               user=session)
    
    return paciente_bp
