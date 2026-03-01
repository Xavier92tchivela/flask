# routes/paciente.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_mysqldb import MySQL
import os
from datetime import datetime, timedelta
import traceback
import logging
from functools import wraps
import re
import html
from bs4 import BeautifulSoup  # precisa instalar: pip install beautifulsoup4

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """Inicializa e retorna o blueprint do paciente"""
    
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    # ========== DECORATORS ==========
    def paciente_required(f):
        """Decorator para garantir que o usuário é um paciente"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÕES AUXILIARES ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Função auxiliar para executar queries no banco de dados"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                if one and result:
                    result = result[0]  # Retorna apenas o primeiro resultado
            else:
                mysql.connection.commit()
                result = None
            
            cur.close()
            return result
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            logger.error(traceback.format_exc())
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
    
    def obter_paciente_id():
        """Obtém o ID do paciente logado"""
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        
        paciente = execute_query(
            "SELECT id FROM pacientes WHERE usuario_id = %s", 
            (session['user_id'],), fetch=True
        )
        
        return paciente[0][0] if paciente else None
    
    # ============================
    # FUNÇÕES PARA RECEITAS
    # ============================
    
    def obter_receitas_paciente(paciente_id, limit=None):
        """Obtém todas as receitas do paciente"""
        query = """
            SELECT 
                r.id,
                r.consulta_id,
                r.diagnostico,
                r.prescricao,
                r.recomendacoes,
                r.status,
                r.created_at,
                r.receita_pdf_path,
                r.pdf_gerado,
                r.data_geracao_pdf,
                c.data_hora as consulta_data,
                CONCAT('Dr. ', m_u.nome) as medico_nome,
                m.especialidade
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.paciente_id = %s
            ORDER BY r.created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return execute_query(query, (paciente_id,), fetch=True) or []
    
    def obter_receita_por_id(receita_id, paciente_id):
        """Obtém uma receita específica verificando se pertence ao paciente"""
        result = execute_query("""
            SELECT 
                r.id,
                r.consulta_id,
                r.diagnostico,
                r.prescricao,
                r.recomendacoes,
                r.status,
                r.created_at,
                r.receita_pdf_path,
                r.pdf_gerado,
                r.data_geracao_pdf,
                c.data_hora as consulta_data,
                CONCAT('Dr. ', m_u.nome) as medico_nome,
                m.especialidade,
                m.crm
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE r.id = %s AND c.paciente_id = %s
        """, (receita_id, paciente_id), fetch=True, one=True)
        
        return result
    
    def limpar_receita_bonita(html_content):
        """Limpa a receita permitindo tags seguras para exibir formatação bonita e atrativa"""
        if not html_content or html_content.strip() == '':
            return '<div class="receita-vazia text-center py-5"><i class="fas fa-file-medical fa-3x text-muted mb-3"></i><p class="text-muted">Nenhuma receita disponível</p></div>'
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove scripts e styles perigosos
            for tag in soup(["script", "style", "iframe", "frame", "frameset", "object", "embed"]):
                tag.decompose()
            
            # Permite tags seguras com classes CSS para estilização
            permitidas = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                         'ul', 'ol', 'li', 'b', 'i', 'strong', 'em', 
                         'br', 'hr', 'div', 'span', 'table', 'tr', 
                         'td', 'th', 'thead', 'tbody', 'a', 'img',
                         'blockquote', 'code', 'pre']
            
            for tag in soup.find_all(True):
                if tag.name not in permitidas:
                    tag.unwrap()  # Remove a tag mas mantém o conteúdo
                else:
                    # Adiciona classes CSS baseadas no tipo de tag
                    if tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        tag['class'] = tag.get('class', []) + ['receita-titulo', 'text-primary', 'mt-4', 'mb-3']
                    
                    elif tag.name == 'p':
                        tag['class'] = tag.get('class', []) + ['receita-paragrafo', 'mb-3']
                    
                    elif tag.name in ['ul', 'ol']:
                        tag['class'] = tag.get('class', []) + ['receita-lista', 'list-group', 'mb-3']
                    
                    elif tag.name == 'li':
                        tag['class'] = tag.get('class', []) + ['receita-item', 'list-group-item', 'border-0', 'py-2', 'px-0']
                    
                    elif tag.name in ['strong', 'b']:
                        tag['class'] = tag.get('class', []) + ['receita-destaque', 'font-weight-bold', 'text-dark']
                    
                    elif tag.name == 'table':
                        tag['class'] = tag.get('class', []) + ['receita-tabela', 'table', 'table-sm', 'table-bordered', 'table-hover', 'mt-3']
                    
                    elif tag.name in ['td', 'th']:
                        tag['class'] = tag.get('class', []) + ['align-middle']
                    
                    elif tag.name == 'blockquote':
                        tag['class'] = tag.get('class', []) + ['receita-citacao', 'blockquote', 'border-left', 'border-primary', 'pl-3', 'py-2', 'my-3']
                    
                    # Remove atributos inseguros
                    safe_attributes = ['class', 'id', 'href', 'src', 'alt', 'title', 'target']
                    attrs = dict(tag.attrs)
                    for attr in attrs:
                        if attr not in safe_attributes:
                            del tag[attr]
            
            # Adiciona ícones para elementos específicos
            texto = str(soup)
            
            # Destaca informações importantes com ícones
            palavras_chave = {
                'dose': 'fa-prescription-bottle-alt',
                'mg': 'fa-weight',
                'ml': 'fa-tint',
                'comprimido': 'fa-tablet-alt',
                'cápsula': 'fa-capsules',
                'gotas': 'fa-tint',
                'xarope': 'fa-wine-bottle',
                'pomada': 'fa-tube',
                'tomar': 'fa-utensils',
                'aplicar': 'fa-hand-paper',
                'antes': 'fa-clock',
                'depois': 'fa-clock',
                'durante': 'fa-clock'
            }
            
            for palavra, icone in palavras_chave.items():
                if palavra in texto.lower():
                    texto = texto.replace(palavra, f'<span class="receita-palavra-chave"><i class="fas {icone} mr-1"></i>{palavra}</span>')
            
            # Adiciona container bonito
            texto = f'''
            <div class="receita-container card border-0 shadow-sm">
                <div class="card-header receita-cabecalho bg-primary text-white">
                    <h5 class="mb-0 d-flex align-items-center">
                        <i class="fas fa-prescription mr-2"></i>
                        <span>Receita Médica</span>
                    </h5>
                </div>
                <div class="card-body receita-corpo">
                    {texto}
                </div>
                <div class="card-footer receita-rodape text-muted small">
                    <i class="fas fa-info-circle mr-1"></i> Esta receita foi emitida digitalmente.
                </div>
            </div>
            '''
            
            # Limpa espaços extras
            texto = re.sub(r'\s+', ' ', texto)
            texto = texto.replace('&nbsp;', ' ').strip()
            
            return texto if texto else '<div class="alert alert-warning">Receita não disponível em formato legível.</div>'
            
        except Exception as e:
            logger.error(f"Erro ao limpar receita: {e}")
            logger.error(traceback.format_exc())
            # Fallback: retorna o conteúdo original com escape
            return f'<div class="receita-simples p-3 border rounded">{html.escape(html_content)}</div>'
    
    def formatar_resumo_receita(html_content, max_length=120):
        """Cria um resumo bonito da receita para listagens"""
        if not html_content or html_content.strip() == '':
            return '<span class="text-muted"><i class="fas fa-file-medical-alt mr-1"></i>Sem receita</span>'
        
        try:
            # Remove tags HTML para resumo
            soup = BeautifulSoup(html_content, 'html.parser')
            texto = soup.get_text().strip()
            
            if not texto:
                return '<span class="text-muted"><i class="fas fa-file-medical-alt mr-1"></i>Receita vazia</span>'
            
            # Limita o tamanho
            if len(texto) > max_length:
                texto = texto[:max_length] + '...'
            
            # Conta medicamentos (aproximado)
            medicamentos = len(re.findall(r'\b\d+\s*(mg|ml|g|comprimidos?|cápsulas?|gotas?)\b', texto, re.IGNORECASE))
            
            # Cria resumo com ícone
            icone = 'fa-prescription-bottle-alt' if medicamentos > 0 else 'fa-file-medical-alt'
            return f'<span class="receita-resumo"><i class="fas {icone} mr-1"></i>{texto}</span>'
            
        except Exception as e:
            logger.error(f"Erro ao formatar resumo: {e}")
            return html_content[:max_length] + '...'
    
    # ========== ROTAS ==========
    
    # Dashboard do paciente
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        # Informações do paciente
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE p.id = %s
        """, (paciente_id,))
        paciente_info = cur.fetchone()
        cur.close()
        
        paciente_nome = paciente_info[0] if paciente_info else session.get('user_name')
        paciente_data_nasc = formatar_data(paciente_info[1], '%d/%m/%Y') if paciente_info and paciente_info[1] else None
        paciente_genero = paciente_info[2] if paciente_info else None
        paciente_telefone = paciente_info[3] if paciente_info else None
        paciente_endereco = paciente_info[4] if paciente_info else None
        paciente_email = paciente_info[5] if paciente_info else None
        
        # Últimas consultas
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, 
                   c.data_hora, c.status, c.receita
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC
            LIMIT 10
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        cur.close()
        
        consultas = []
        for c in consultas_raw:
            receita_resumo = formatar_resumo_receita(c[5]) if c[5] else None
            consultas.append({
                'id': c[0],
                'medico_nome': c[1],
                'especialidade': c[2],
                'data_hora': formatar_data(c[3]),
                'status': c[4],
                'receita': receita_resumo,
                'status_class': {
                    'agendada': 'warning',
                    'realizada': 'success',
                    'cancelada': 'danger',
                    'confirmada': 'info'
                }.get(c[4], 'secondary')
            })
        
        # Últimas receitas
        receitas_raw = obter_receitas_paciente(paciente_id, limit=5)
        receitas = []
        for r in receitas_raw:
            receitas.append({
                'id': r[0],
                'consulta_id': r[1],
                'medico_nome': r[11],
                'especialidade': r[12],
                'consulta_data': formatar_data(r[10], '%d/%m/%Y'),
                'created_at': formatar_data(r[6], '%d/%m/%Y'),
                'pdf_gerado': r[8],
                'receita_pdf_path': r[7]
            })
        
        # Estatísticas
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s", (paciente_id,))
        total_consultas = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
        consultas_hoje = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM receita r JOIN consultas c ON r.consulta_id = c.id WHERE c.paciente_id = %s", (paciente_id,))
        total_receitas = cur.fetchone()[0] or 0
        cur.close()
        
        stats = {
            'total_consultas': total_consultas,
            'consultas_hoje': consultas_hoje,
            'total_receitas': total_receitas
        }
        
        return render_template('paciente/dashboard.html', 
                               consultas=consultas,
                               receitas=receitas,
                               stats=stats,
                               paciente_id=paciente_id,
                               paciente_nome=paciente_nome,
                               paciente_data_nasc=paciente_data_nasc,
                               paciente_genero=paciente_genero,
                               paciente_telefone=paciente_telefone,
                               paciente_endereco=paciente_endereco,
                               paciente_email=paciente_email,
                               user=session)
    
    # Minhas consultas
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, m.crm, c.data_hora, c.status, c.receita
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
            receita_resumo = formatar_resumo_receita(c[6]) if c[6] else formatar_resumo_receita('')
            
            status_classes = {
                'agendada': 'warning',
                'realizada': 'success',
                'cancelada': 'danger',
                'confirmada': 'info'
            }
            
            consultas_formatadas.append({
                'id': c[0],
                'medico_nome': c[1],
                'especialidade': c[2],
                'crm': c[3],
                'data_hora': formatar_data(c[4]),
                'data_short': formatar_data(c[4], '%d/%m/%Y'),
                'hora': formatar_data(c[4], '%H:%M'),
                'status': c[5],
                'status_class': status_classes.get(c[5], 'secondary'),
                'receita': receita_resumo,
                'receita_raw': c[6]
            })
        
        return render_template('paciente/consultas.html',
                               consultas=consultas_formatadas,
                               user=session,
                               user_type='paciente')
    
    # Minhas receitas
    @paciente_bp.route('/receitas')
    @paciente_required
    def minhas_receitas():
        """Lista todas as receitas do paciente"""
        paciente_id = obter_paciente_id()
        receitas_raw = obter_receitas_paciente(paciente_id)
        
        receitas = []
        for r in receitas_raw:
            # Formatar diagnóstico e prescrição para resumo
            diagnostico_resumo = formatar_resumo_receita(r[2], 100) if r[2] else ''
            prescricao_resumo = formatar_resumo_receita(r[3], 100) if r[3] else ''
            
            receitas.append({
                'id': r[0],
                'consulta_id': r[1],
                'diagnostico': r[2],
                'prescricao': r[3],
                'recomendacoes': r[4],
                'status': r[5],
                'created_at': formatar_data(r[6], '%d/%m/%Y %H:%M'),
                'receita_pdf_path': r[7],
                'pdf_gerado': r[8],
                'data_geracao_pdf': formatar_data(r[9], '%d/%m/%Y %H:%M') if r[9] else None,
                'consulta_data': formatar_data(r[10], '%d/%m/%Y'),
                'medico_nome': r[11],
                'especialidade': r[12],
                'diagnostico_resumo': diagnostico_resumo,
                'prescricao_resumo': prescricao_resumo,
                'status_class': 'success' if r[5] == 'ativa' else 'secondary'
            })
        
        return render_template('paciente/receitas.html',
                               receitas=receitas,
                               user=session,
                               user_type='paciente')
    
    # Visualizar receita específica
    @paciente_bp.route('/receitas/<int:receita_id>')
    @paciente_required
    def visualizar_receita(receita_id):
        """Visualiza uma receita específica"""
        paciente_id = obter_paciente_id()
        receita = obter_receita_por_id(receita_id, paciente_id)
        
        if not receita:
            flash('Receita não encontrada ou você não tem acesso.', 'danger')
            return redirect(url_for('paciente.minhas_receitas'))
        
        # Formatar conteúdo HTML das receitas
        diagnostico_html = limpar_receita_bonita(receita[2]) if receita[2] else ''
        prescricao_html = limpar_receita_bonita(receita[3]) if receita[3] else ''
        recomendacoes_html = limpar_receita_bonita(receita[4]) if receita[4] else ''
        
        return render_template('paciente/visualizar_receita.html',
                               receita=receita,
                               diagnostico_html=diagnostico_html,
                               prescricao_html=prescricao_html,
                               recomendacoes_html=recomendacoes_html,
                               formatar_data=formatar_data,
                               user=session,
                               user_type='paciente')
    
    # Download do PDF da receita
    @paciente_bp.route('/receitas/<int:receita_id>/download')
    @paciente_required
    def download_receita_pdf(receita_id):
        """Faz o download do PDF da receita"""
        paciente_id = obter_paciente_id()
        receita = obter_receita_por_id(receita_id, paciente_id)
        
        if not receita:
            flash('Receita não encontrada ou você não tem acesso.', 'danger')
            return redirect(url_for('paciente.minhas_receitas'))
        
        pdf_path = receita[7]  # receita_pdf_path
        if not pdf_path or not os.path.exists(pdf_path):
            flash('Arquivo PDF não encontrado.', 'danger')
            return redirect(url_for('paciente.visualizar_receita', receita_id=receita_id))
        
        try:
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f'receita_{receita_id}.pdf',
                mimetype='application/pdf'
            )
        except Exception as e:
            logger.error(f"Erro ao baixar PDF: {e}")
            flash('Erro ao baixar o arquivo PDF.', 'danger')
            return redirect(url_for('paciente.visualizar_receita', receita_id=receita_id))
    
    # Agendar consulta - VERSÃO COM SINTOMAS
    @paciente_bp.route('/agendar', methods=['GET', 'POST'])
    @paciente_required
    def agendar_consulta():
        paciente_id = obter_paciente_id()
        
        if request.method == 'POST':
            medico_id = request.form.get('medico_id')
            data_consulta = request.form.get('data_consulta')
            hora_consulta = request.form.get('hora_consulta')
            observacoes = request.form.get('observacoes', '')
            sintomas = request.form.get('sintomas', '')  # 👈 CAPTURAR SINTOMAS
            
            data_hora_str = f"{data_consulta} {hora_consulta}"
            
            try:
                cur = mysql.connection.cursor()
                cur.execute("SELECT id FROM medicos WHERE id = %s", (medico_id,))
                medico = cur.fetchone()
                
                if not medico:
                    flash('Médico não encontrado.', 'danger')
                    return redirect(url_for('paciente.agendar_consulta'))
                
                # Insere a consulta COM SINTOMAS
                cur.execute("""
                    INSERT INTO consultas 
                    (paciente_id, medico_id, data_hora, status, observacoes, sintomas)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (paciente_id, medico_id, data_hora_str, 'agendada', observacoes, sintomas))
                mysql.connection.commit()
                cur.close()
                
                flash('Consulta agendada com sucesso!', 'success')
                return redirect(url_for('paciente.minhas_consultas'))
                
            except Exception as e:
                mysql.connection.rollback()
                logger.error(f"Erro ao agendar consulta: {e}")
                flash('Erro ao agendar consulta. Tente novamente.', 'danger')
                return redirect(url_for('paciente.agendar_consulta'))
        
        # GET: Mostrar formulário de agendamento
        cur = mysql.connection.cursor()
        
        cur.execute("""
            SELECT m.id, u.nome, m.especialidade, m.crm
            FROM medicos m
            JOIN usuarios u ON m.usuario_id = u.id
            WHERE u.ativo = 1
            ORDER BY u.nome
        """)
        medicos = cur.fetchall()
        
        horarios = []
        for hora in range(8, 18):
            for minuto in ['00', '30']:
                horarios.append(f"{hora:02d}:{minuto}")
        
        data_minima = datetime.now().strftime('%Y-%m-%d')
        data_maxima = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        cur.close()
        
        return render_template('paciente/agendar_consulta.html',
                               medicos=medicos,
                               horarios=horarios,
                               data_minima=data_minima,
                               data_maxima=data_maxima,
                               user=session,
                               user_type='paciente')
    
    # ========== ROTA CORRIGIDA: DETALHES DA CONSULTA COM RECEITAS ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        """Detalhes da consulta com receitas da tabela receita"""
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        
        # Buscar detalhes da consulta
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, m.crm, c.data_hora, c.status,
                   c.observacoes, c.receita, c.sintomas, p_u.nome, p.data_nascimento, p.genero
            FROM consultas c
            JOIN medicos m ON m.id = c.medico_id
            JOIN usuarios m_u ON m_u.id = m.usuario_id
            JOIN pacientes p ON p.id = c.paciente_id
            JOIN usuarios p_u ON p_u.id = p.usuario_id
            WHERE c.id = %s AND c.paciente_id = %s
        """, (consulta_id, paciente_id))
        row = cur.fetchone()
        
        if not row:
            cur.close()
            flash('Consulta não encontrada ou você não tem acesso.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        consulta_data = list(row)
        
        # Processar sintomas (separar por vírgula)
        sintomas_lista = []
        if len(consulta_data) > 8 and consulta_data[8]:
            sintomas_lista = [s.strip() for s in consulta_data[8].split(',') if s.strip()]
        
        # ===== BUSCAR RECEITAS DA TABELA RECEITA =====
        cur.execute("""
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
        """, (consulta_id,))
        receitas_raw = cur.fetchall()
        cur.close()
        
        # Formatar as receitas para exibição
        receitas = []
        for r in receitas_raw:
            # Criar resumos para exibição nos cards
            diagnostico_texto = r[1][:150] + '...' if r[1] and len(r[1]) > 150 else r[1]
            prescricao_texto = r[2][:150] + '...' if r[2] and len(r[2]) > 150 else r[2]
            
            # Aplicar formatação bonita para o conteúdo completo
            diagnostico_html = limpar_receita_bonita(r[1]) if r[1] else ''
            prescricao_html = limpar_receita_bonita(r[2]) if r[2] else ''
            
            receitas.append({
                'id': r[0],
                'diagnostico': diagnostico_html,
                'diagnostico_texto': diagnostico_texto,
                'prescricao': prescricao_html,
                'prescricao_texto': prescricao_texto,
                'recomendacoes': r[3],
                'status': r[4],
                'created_at': formatar_data(r[5], '%d/%m/%Y %H:%M'),
                'receita_pdf_path': r[6],
                'pdf_gerado': bool(r[7]),
                'data_geracao_pdf': formatar_data(r[8], '%d/%m/%Y %H:%M') if r[8] else None,
                'status_class': 'success' if r[4] == 'ativa' else 'secondary'
            })
        
        status_class = {
            'agendada': 'warning',
            'realizada': 'success',
            'cancelada': 'danger',
            'confirmada': 'info'
        }.get(consulta_data[5], 'secondary')
        
        return render_template('paciente/detalhes_consulta.html', 
                               consulta=consulta_data,
                               sintomas=sintomas_lista,
                               receitas=receitas,  # Passa a lista de receitas
                               status_class=status_class,
                               user=session,
                               formatar_data=formatar_data,
                               datetime=datetime,
                               user_type='paciente')
    
    # Cancelar consulta
    @paciente_bp.route('/consultas/<int:consulta_id>/cancelar', methods=['POST'])
    @paciente_required
    def cancelar_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT status, data_hora FROM consultas 
                WHERE id = %s AND paciente_id = %s
            """, (consulta_id, paciente_id))
            consulta = cur.fetchone()
            
            if not consulta:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('paciente.minhas_consultas'))
            
            if consulta[0] != 'agendada':
                flash('Apenas consultas agendadas podem ser canceladas.', 'warning')
                return redirect(url_for('paciente.detalhes_consulta', consulta_id=consulta_id))
            
            cur.execute("""
                UPDATE consultas 
                SET status = 'cancelada' 
                WHERE id = %s AND paciente_id = %s
            """, (consulta_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            flash('Consulta cancelada com sucesso!', 'success')
            
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Erro ao cancelar consulta: {e}")
            flash('Erro ao cancelar consulta. Tente novamente.', 'danger')
        
        return redirect(url_for('paciente.minhas_consultas'))
    
    # Perfil do paciente
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        if request.method == 'POST':
            telefone = request.form.get('telefone')
            endereco = request.form.get('endereco')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero')
            alergias = request.form.get('alergias', '')
            medicamentos_uso = request.form.get('medicamentos_uso', '')
            historico_doencas = request.form.get('historico_doencas', '')
            contato_emergencia = request.form.get('contato_emergencia', '')
            
            execute_query("""
                UPDATE pacientes 
                SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s,
                    alergias=%s, medicamentos_uso=%s, historico_doencas=%s, contato_emergencia=%s
                WHERE id=%s
            """, (telefone, endereco, data_nascimento, genero,
                  alergias, medicamentos_uso, historico_doencas, contato_emergencia, paciente_id))
            flash('Perfil atualizado com sucesso!', 'success')
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
                               paciente_nome=info[0],
                               data_nascimento=info[1],
                               genero=info[2],
                               telefone=info[3],
                               endereco=info[4],
                               email=info[5],
                               alergias=info[6],
                               medicamentos_uso=info[7],
                               historico_doencas=info[8],
                               contato_emergencia=info[9],
                               user=session)
    
    return paciente_bp