from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_mysqldb import MySQL
from google import genai
from google.genai import types
import uuid
from datetime import datetime
from config import Config
import os
from werkzeug.utils import secure_filename
from PIL import Image
import traceback
import base64
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import html
import re

app = Flask(__name__)
app.config.from_object(Config)

# ========== INICIALIZAÇÃO DO BANCO DE DADOS ==========
mysql = MySQL(app)

# ========== CONFIGURAÇÃO GEMINI AI ==========
api_key = app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')

client = None
gemini_available = False
MODEL_NAME = None

PREFERRED_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.5"
]

def safe_list_models(c):
    """Retorna lista de modelos disponíveis"""
    try:
        models = []
        for m in c.models.list():
            supported = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
            models.append((m.name, supported))
        return models
    except Exception as e:
        print("Erro ao listar modelos:", e)
        return []

def choose_model(c, preferred_list=None):
    """Escolhe automaticamente um modelo compatível"""
    try:
        for pref in (preferred_list or []):
            for m in c.models.list():
                name = getattr(m, "name", None) or getattr(m, "model", None)
                supported = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
                if name and pref in name and ("generateContent" in supported or "chat" in supported or "startChat" in supported):
                    return name
        for m in c.models.list():
            name = getattr(m, "name", None) or getattr(m, "model", None)
            supported = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
            if name and ("generateContent" in supported or "chat" in supported):
                return name
    except Exception as e:
        print("Erro em choose_model:", e)
    return None

# Inicialização do cliente Gemini
if api_key and api_key.strip() and api_key.lower() != 'root':
    try:
        client = genai.Client(api_key=api_key)
        MODEL_NAME = choose_model(client, PREFERRED_MODELS)
        if not MODEL_NAME:
            available = safe_list_models(client)
            print("Modelos disponíveis (name, supported_actions):")
            for name, sup in available:
                print(f"  - {name} -> {sup}")
            raise RuntimeError("Nenhum modelo com 'generateContent' encontrado para sua chave.")
        gemini_available = True
        print(f"Gemini configurado. Modelo selecionado: {MODEL_NAME}")
    except Exception as e:
        gemini_available = False
        print("Erro ao configurar Gemini AI:", str(e))
        traceback.print_exc()
else:
    print("AVISO: Chave API Gemini não configurada. Defina GEMINI_API_KEY ou coloque no Config.")

# ========== CONFIGURAÇÕES GERAIS ==========
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Armazenamento de chats em memória
diagnostico_chats = {}

# ========== FUNÇÕES AUXILIARES ==========
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def execute_query(query, params=None, fetch=False):
    """Função auxiliar para executar queries no banco de dados"""
    try:
        cur = mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch:
            result = cur.fetchall()
        else:
            mysql.connection.commit()
            result = None
        
        cur.close()
        return result
    except Exception as e:
        mysql.connection.rollback()
        print(f"Database error: {e}")
        traceback.print_exc()
        return None

def formatar_diagnostico(texto):
    """Formata o diagnóstico em HTML com estrutura organizada"""
    texto = texto.replace('\n', '<br>')
    html_content = f"""
    <div class="diagnostico-container">
        <div class="diagnostico-header">
            <h4><i class="fas fa-file-medical-alt"></i> Relatório de Diagnóstico</h4>
            <p class="text-muted">Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>
        <div class="diagnostico-content">
            {texto}
        </div>
        <div class="diagnostico-footer">
            <p class="text-end"><small>Este diagnóstico foi gerado por inteligência artificial e deve ser revisado por um profissional médico.</small></p>
        </div>
    </div>
    """
    return html_content

def gerar_pdf_fallback(paciente_nome, consulta_data):
    """Gera um PDF básico em caso de erro"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        story.append(Paragraph("RECEITA MÉDICA - MODO DE EMERGÊNCIA", styles['Heading1']))
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph(f"<b>Paciente:</b> {paciente_nome}", styles['Normal']))
        story.append(Paragraph(f"<b>Data:</b> {consulta_data}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("Houve um problema técnico ao gerar a receita completa.", styles['Normal']))
        story.append(Paragraph("Por favor, consulte o sistema para visualizar a receita original.", styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("_________________________", styles['Normal']))
        story.append(Paragraph("Assinatura Médica", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Erro no PDF de fallback: {e}")
        return None

def formatar_data(data, formato='%d/%m/%Y %H:%M'):
    """Formata data de forma segura, lidando com strings e objetos datetime"""
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

def html_to_pdf(html_content, paciente_nome, consulta_data):
    """Converte HTML da receita para PDF de forma limpa e profissional"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()

        # Estilos personalizados
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#2c3e50')
        )

        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            textColor=colors.HexColor('#34495e'),
            leading=14
        )

        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            textColor=colors.HexColor('#2c3e50'),
            leading=14
        )

        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            spaceBefore=20,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=1
        )

        story = []

        # Cabeçalho
        story.append(Paragraph("RECEITA MÉDICA", title_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"<b>Paciente:</b> {paciente_nome}", normal_style))
        story.append(Paragraph(f"<b>Data da Consulta:</b> {consulta_data}", normal_style))
        story.append(Spacer(1, 0.1 * inch))

        # Limpeza do HTML
        cleaned_html = re.sub(r'<style.*?>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r'<script.*?>.*?</script>', '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        text_content = re.sub(r'<[^>]+>', '', cleaned_html)
        text_content = html.unescape(text_content)

        # Divide em linhas limpas
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]

        # Monta conteúdo
        for line in lines:
            if re.search(r'\b(DIAGNÓSTICO|MEDICAMENTO|RECOMENDA|TRATAMENTO|ORIENTA|EXAME|RETORNO)\b', line, re.IGNORECASE):
                story.append(Spacer(1, 0.15 * inch))
                story.append(Paragraph(f"<b>{line}</b>", header_style))
            elif re.match(r'^\d+\.|\•|\-', line):
                story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{line}", normal_style))
            else:
                story.append(Paragraph(line, normal_style))

        # Rodapé
        story.append(Spacer(1, 0.4 * inch))
        story.append(Paragraph("_________________________", footer_style))
        story.append(Paragraph("Dr(a). " + session.get('user_name', 'Médico'), footer_style))
        story.append(Paragraph("CRM: " + session.get('crm', ''), footer_style))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", footer_style))

        # Geração do PDF
        doc.build(story)
        buffer.seek(0)

        if buffer.getbuffer().nbytes == 0:
            raise Exception("PDF gerado está vazio")

        return buffer

    except Exception as e:
        print(f"Erro detalhado ao gerar PDF: {e}")
        traceback.print_exc()

        try:
            return gerar_pdf_fallback(paciente_nome, consulta_data)
        except Exception as fallback_error:
            print(f"Erro no PDF de fallback: {fallback_error}")
            return None

@app.context_processor
def inject_utils():
    """Injeta funções úteis nos templates"""
    return dict(
        datetime=datetime,
        formatar_data=formatar_data
    )

# ========== ROTAS DE AUTENTICAÇÃO ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = execute_query(
            "SELECT id, uuid, nome, email, senha, tipo FROM usuarios WHERE email = %s AND ativo = TRUE", 
            (email,), True
        )
        
        if user and user[0][4] == password:
            session['user_id'] = user[0][0]
            session['user_name'] = user[0][2]
            session['user_type'] = user[0][5]
            flash('Login realizado com sucesso!', 'success')
            
            if user[0][5] == 'medico':
                return redirect(url_for('medico_dashboard'))
            else:
                return redirect(url_for('paciente_dashboard'))
        else:
            flash('Email ou senha incorretos', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Rota para registro de novos usuários"""
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        telefone = request.form['telefone']
        password = request.form['password']
        tipo = request.form['tipo']
        
        user_exists = execute_query(
            "SELECT id FROM usuarios WHERE email = %s", 
            (email,), True
        )
        
        if user_exists:
            flash('Este email já está cadastrado.', 'danger')
            return redirect(url_for('register'))
        
        user_uuid = str(uuid.uuid4())
        execute_query(
            "INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_uuid, nome, email, password, telefone, tipo)
        )
        
        user_id = execute_query(
            "SELECT id FROM usuarios WHERE email = %s", 
            (email,), True
        )[0][0]
        
        if tipo == 'paciente':
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero')
            endereco = request.form.get('endereco')
            
            execute_query(
                "INSERT INTO pacientes (usuario_id, data_nascimento, genero, endereco) VALUES (%s, %s, %s, %s)",
                (user_id, data_nascimento, genero, endereco)
            )
        elif tipo == 'medico':
            especialidade = request.form.get('especialidade')
            crm = request.form.get('crm')
            
            execute_query(
                "INSERT INTO medicos (usuario_id, especialidade, crm) VALUES (%s, %s, %s)",
                (user_id, especialidade, crm)
            )
        
        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# ========== ROTAS DE CONSULTAS ==========
@app.route('/minhas_consultas')
def minhas_consultas():
    """Página principal de consultas"""
    if 'user_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_type = session.get('user_type')
    
    consultas = []
    
    if user_type == 'paciente':
        consultas = execute_query("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, 
                   c.data_hora, c.status, c.receita
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            JOIN pacientes p ON c.paciente_id = p.id 
            WHERE p.usuario_id = %s 
            ORDER BY c.data_hora DESC
        """, (user_id,), True) or []
    
    elif user_type == 'medico':
        consultas = execute_query("""
            SELECT c.id, p_u.nome as paciente_nome, 
                   c.data_hora, c.status, c.receita
            FROM consultas c 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            JOIN medicos m ON c.medico_id = m.id 
            WHERE m.usuario_id = %s 
            ORDER BY c.data_hora DESC
        """, (user_id,), True) or []
    
    return render_template('minhas_consultas.html', 
                         consultas=consultas, 
                         user=session,
                         user_type=user_type)

@app.route('/consultas/agendar', methods=['GET', 'POST'])
def agendar_consulta():
    """Agendar nova consulta"""
    if 'user_id' not in session:
        flash('Por favor, faça login para agendar consultas.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            user_id = session['user_id']
            user_type = session.get('user_type')
            
            if user_type == 'paciente':
                paciente = execute_query(
                    "SELECT id FROM pacientes WHERE usuario_id = %s", 
                    (user_id,), True
                )
                if not paciente:
                    flash('Perfil de paciente não encontrado.', 'danger')
                    return redirect(url_for('minhas_consultas'))
                paciente_id = paciente[0][0]
            else:
                paciente_id = request.form['paciente_id']
            
            medico_id = request.form['medico_id']
            data_hora = request.form['data_hora']
            observacoes = request.form.get('observacoes', '')
            
            if not medico_id or not data_hora:
                flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('agendar_consulta'))
            
            data_hora_obj = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
            data_hora_mysql = data_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
            
            consulta_conflito = execute_query("""
                SELECT id FROM consultas 
                WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'
            """, (medico_id, data_hora_mysql), True)
            
            if consulta_conflito:
                flash('Este médico já possui uma consulta agendada para este horário. Por favor, escolha outro horário.', 'danger')
                return redirect(url_for('agendar_consulta'))
            
            execute_query(
                """INSERT INTO consultas (paciente_id, medico_id, data_hora, observacoes, status) 
                VALUES (%s, %s, %s, %s, 'agendada')""",
                (paciente_id, medico_id, data_hora_mysql, observacoes)
            )
            
            flash('Consulta agendada com sucesso!', 'success')
            return redirect(url_for('minhas_consultas'))
            
        except Exception as e:
            flash(f'Erro ao agendar consulta: {str(e)}', 'danger')
            return redirect(url_for('agendar_consulta'))
    
    medicos = execute_query("""
        SELECT m.id, u.nome, m.especialidade 
        FROM medicos m 
        JOIN usuarios u ON m.usuario_id = u.id 
        WHERE u.ativo = TRUE
        ORDER BY u.nome
    """, fetch=True) or []
    
    paciente_nome = None
    if session.get('user_type') == 'paciente':
        paciente_info = execute_query("""
            SELECT u.nome 
            FROM pacientes p 
            JOIN usuarios u ON p.usuario_id = u.id 
            WHERE p.usuario_id = %s
        """, (session['user_id'],), True)
        
        if paciente_info:
            paciente_nome = paciente_info[0][0]
    
    pacientes = []
    if session.get('user_type') != 'paciente':
        pacientes = execute_query("""
            SELECT p.id, u.nome 
            FROM pacientes p 
            JOIN usuarios u ON p.usuario_id = u.id 
            WHERE u.ativo = TRUE
            ORDER BY u.nome
        """, fetch=True) or []
    
    return render_template('agendar_consulta.html', 
                         medicos=medicos, 
                         pacientes=pacientes,
                         paciente_nome=paciente_nome,
                         user=session)

@app.route('/consultas/<int:consulta_id>')
def detalhes_consulta(consulta_id):
    """Detalhes de uma consulta específica"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_type = session.get('user_type')
    
    if user_type == 'paciente':
        consulta = execute_query("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, m.crm,
                   c.data_hora, c.status, c.observacoes, c.receita,
                   p_u.nome as paciente_nome, p.data_nascimento, p.genero
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE c.id = %s AND p.usuario_id = %s
        """, (consulta_id, user_id), True)
    elif user_type == 'medico':
        consulta = execute_query("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, m.crm,
                   c.data_hora, c.status, c.observacoes, c.receita,
                   p_u.nome as paciente_nome, p.data_nascimento, p.genero
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE c.id = %s AND m.usuario_id = %s
        """, (consulta_id, user_id), True)
    else:
        consulta = execute_query("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, m.crm,
                   c.data_hora, c.status, c.observacoes, c.receita,
                   p_u.nome as paciente_nome, p.data_nascimento, p.genero
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE c.id = %s
        """, (consulta_id,), True)
    
    if not consulta:
        flash('Consulta não encontrada ou você não tem acesso.', 'danger')
        return redirect(url_for('minhas_consultas'))
    
    consulta = consulta[0]
    return render_template('detalhes_consulta.html', 
                         consulta=consulta, 
                         user=session,
                         user_type=user_type)

@app.route('/consultas/<int:consulta_id>/cancelar', methods=['POST'])
def cancelar_consulta(consulta_id):
    """Cancelar uma consulta"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    
    try:
        user_id = session['user_id']
        user_type = session.get('user_type')
        
        if user_type == 'paciente':
            result = execute_query("""
                SELECT c.id FROM consultas c 
                JOIN pacientes p ON c.paciente_id = p.id 
                WHERE c.id = %s AND p.usuario_id = %s AND c.status = 'agendada'
            """, (consulta_id, user_id), True)
        elif user_type == 'medico':
            result = execute_query("""
                SELECT c.id FROM consultas c 
                JOIN medicos m ON c.medico_id = m.id 
                WHERE c.id = %s AND m.usuario_id = %s AND c.status = 'agendada'
            """, (consulta_id, user_id), True)
        else:
            result = execute_query(
                "SELECT id FROM consultas WHERE id = %s AND status = 'agendada'", 
                (consulta_id,), True
            )
        
        if not result:
            return jsonify({'success': False, 'error': 'Consulta não encontrada ou não pode ser cancelada'}), 404
        
        execute_query(
            "UPDATE consultas SET status = 'cancelada' WHERE id = %s",
            (consulta_id,)
        )
        
        return jsonify({'success': True, 'message': 'Consulta cancelada com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ROTAS DO PACIENTE ==========
@app.route('/paciente/dashboard')
def paciente_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'paciente':
        return redirect(url_for('login'))
    
    paciente = execute_query(
        "SELECT id FROM pacientes WHERE usuario_id = %s", 
        (session['user_id'],), True
    )
    
    if not paciente:
        flash('Perfil de paciente não encontrado.', 'danger')
        return redirect(url_for('logout'))
    
    paciente_id = paciente[0][0]
    
    paciente_info = execute_query("""
        SELECT p_u.nome, p.data_nascimento, p.genero 
        FROM pacientes p 
        JOIN usuarios p_u ON p.usuario_id = p_u.id 
        WHERE p.id = %s
    """, (paciente_id,), True)
    
    if paciente_info:
        paciente_nome = paciente_info[0][0]
    else:
        paciente_nome = session['user_name']
    
    consultas = execute_query("""
        SELECT c.id, m_u.nome as medico_nome, m.especialidade, 
               c.data_hora, c.status, c.receita
        FROM consultas c 
        JOIN medicos m ON c.medico_id = m.id 
        JOIN usuarios m_u ON m.usuario_id = m_u.id 
        WHERE c.paciente_id = %s 
        ORDER BY c.data_hora DESC
    """, (paciente_id,), True) or []
    
    return render_template('paciente_dashboard.html', 
                         consultas=consultas, 
                         user=session,
                         paciente_id=paciente_id,
                         paciente_nome=paciente_nome)

# ========== ROTAS DO MÉDICO ==========
@app.route('/medico/dashboard')
def medico_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return redirect(url_for('login'))
    
    consultas = execute_query("""
        SELECT c.id, p_u.nome as paciente_nome, c.data_hora, c.status 
        FROM consultas c 
        JOIN pacientes p ON c.paciente_id = p.id 
        JOIN usuarios p_u ON p.usuario_id = p_u.id 
        JOIN medicos m ON c.medico_id = m.id 
        WHERE m.usuario_id = %s 
        ORDER BY c.data_hora DESC
    """, (session['user_id'],), True)
    
    return render_template('medico_dashboard.html', consultas=consultas, user=session)

@app.route('/medico/analise/<int:consulta_id>', methods=['GET', 'POST'])
def medico_analise(consulta_id):
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return redirect(url_for('login'))
    
    consulta = execute_query("""
        SELECT c.id, p_u.nome as paciente_nome, p.id as paciente_id, 
               c.data_hora, c.status, c.observacoes 
        FROM consultas c 
        JOIN pacientes p ON c.paciente_id = p.id 
        JOIN usuarios p_u ON p.usuario_id = p_u.id 
        JOIN medicos m ON c.medico_id = m.id 
        WHERE c.id = %s AND m.usuario_id = %s
    """, (consulta_id, session['user_id']), True)
    
    if not consulta:
        flash('Consulta não encontrada ou não pertence a você.', 'danger')
        return redirect(url_for('medico_dashboard'))
    
    consulta = consulta[0]
    receita = None
    
    if request.method == 'POST':
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                tipo_exame = request.form.get('tipo_exame')
                observacoes_exame = request.form.get('observacoes_exame')
                
                if not gemini_available:
                    data_formatada = formatar_data(consulta[3])
                    
                    receita = f"""
                    <div class="alert alert-warning">
                        <h4><i class="fas fa-exclamation-triangle"></i> DIAGNÓSTICO SIMULADO</h4>
                        <p>API Gemini não configurada.</p>
                    </div>
                    <div class="diagnostico-content">
                        <h5>Paciente: {consulta[1]}</h5>
                        <p><strong>Data:</strong> {data_formatada}</p>
                        <p><strong>Exame:</strong> {tipo_exame}</p>
                        <p>Configure a API Gemini para análise real.</p>
                    </div>
                    """
                    
                    execute_query(
                        "UPDATE consultas SET receita = %s, status = 'realizada' WHERE id = %s",
                        (receita, consulta_id)
                    )
                    flash('Diagnóstico simulado gerado! Configure a API Gemini.', 'warning')
                else:
                    try:
                        img = Image.open(filepath)
                        data_formatada = formatar_data(consulta[3])
                        
                        prompt = f"""
Analise a imagem e gere diagnóstico detalhado em HTML.

Paciente: {consulta[1]}
Data: {data_formatada}
Exame: {tipo_exame}
Observações: {observacoes_exame or 'Nenhuma'}

Forneça:
1. Achados da imagem
2. Diagnóstico
3. Medicamentos
4. Recomendações
5. Retorno

Use HTML com Bootstrap.
"""
                        response = client.models.generate_content(model=MODEL_NAME, contents=[prompt, img])
                        receita = formatar_diagnostico(getattr(response, "text", str(response)))
                        
                        execute_query(
                            "UPDATE consultas SET receita = %s, status = 'realizada' WHERE id = %s",
                            (receita, consulta_id)
                        )
                        flash('Diagnóstico gerado com sucesso!', 'success')
                        
                    except Exception as e:
                        traceback.print_exc()
                        flash(f'Erro ao gerar diagnóstico: {str(e)}', 'danger')
    
    if not receita:
        receita_db = execute_query(
            "SELECT receita FROM consultas WHERE id = %s", 
            (consulta_id,), True
        )
        if receita_db and receita_db[0][0]:
            receita = receita_db[0][0]
    
    return render_template('medico_analise.html', consulta=consulta, receita=receita)

# ========== ROTAS ADMINISTRATIVAS ==========
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('user_type') == 'paciente':
        return redirect(url_for('login'))
    
    stats = {
        'pacientes': execute_query("SELECT COUNT(*) FROM pacientes", fetch=True)[0][0],
        'medicos': execute_query("SELECT COUNT(*) FROM medicos", fetch=True)[0][0],
        'consultas_hoje': execute_query(
            "SELECT COUNT(*) FROM consultas WHERE DATE(data_hora) = CURDATE()", fetch=True
        )[0][0]
    }
    
    return render_template('dashboard.html', user=session, stats=stats)

@app.route('/pacientes')
def pacientes():
    if 'user_id' not in session or session.get('user_type') == 'paciente':
        return redirect(url_for('login'))
    
    pacientes = execute_query("""
        SELECT p.id, u.nome, u.email, u.telefone, p.data_nascimento, p.genero, p.endereco 
        FROM pacientes p 
        JOIN usuarios u ON p.usuario_id = u.id 
        WHERE u.ativo = TRUE
    """, fetch=True)
    
    return render_template('pacientes.html', pacientes=pacientes)

@app.route('/medicos')
def medicos():
    if 'user_id' not in session or session.get('user_type') == 'paciente':
        return redirect(url_for('login'))
    
    medicos = execute_query("""
        SELECT m.id, u.nome, u.email, u.telefone, m.especialidade, m.crm 
        FROM medicos m 
        JOIN usuarios u ON m.usuario_id = u.id 
        WHERE u.ativo = TRUE
    """, fetch=True)
    
    return render_template('medicos.html', medicos=medicos)

@app.route('/consultas_admin')
def consultas_admin():
    if 'user_id' not in session or session.get('user_type') == 'paciente':
        return redirect(url_for('login'))
    
    consultas = execute_query("""
        SELECT c.id, p_u.nome as paciente_nome, m_u.nome as medico_nome, 
               c.data_hora, c.status, c.observacoes 
        FROM consultas c 
        JOIN pacientes p ON c.paciente_id = p.id 
        JOIN usuarios p_u ON p.usuario_id = p_u.id 
        JOIN medicos m ON c.medico_id = m.id 
        JOIN usuarios m_u ON m.usuario_id = m_u.id 
        ORDER BY c.data_hora DESC
    """, fetch=True)
    
    return render_template('consultas_admin.html', consultas=consultas)

@app.route('/agendamento_admin', methods=['GET', 'POST'])
def agendamento_admin():
    if 'user_id' not in session or session.get('user_type') == 'paciente':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        paciente_id = request.form['paciente']
        medico_id = request.form['medico']
        data_hora = request.form['data_hora']
        observacoes = request.form['observacoes']
        
        data_hora_obj = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
        data_hora_mysql = data_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
        
        execute_query(
            "INSERT INTO consultas (paciente_id, medico_id, data_hora, observacoes, status) VALUES (%s, %s, %s, %s, 'agendada')",
            (paciente_id, medico_id, data_hora_mysql, observacoes)
        )
        
        flash('Consulta agendada com sucesso!', 'success')
        return redirect(url_for('consultas_admin'))
    
    pacientes = execute_query(
        "SELECT p.id, u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE u.ativo = TRUE",
        fetch=True
    )
    
    medicos = execute_query(
        "SELECT m.id, u.nome, m.especialidade FROM medicos m JOIN usuarios u ON m.usuario_id = u.id WHERE u.ativo = TRUE",
        fetch=True
    )
    
    return render_template('agendamento_admin.html', pacientes=pacientes, medicos=medicos)

# ========== ROTAS DA API ==========
@app.route('/api/receita/editar/<int:consulta_id>', methods=['POST'])
def editar_receita(consulta_id):
    """Salva a receita editada pelo médico"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    data = request.get_json() or {}
    receita_editada = data.get('receita')
    
    if not receita_editada:
        return jsonify({'error': 'Receita vazia'}), 400
    
    try:
        execute_query(
            "UPDATE consultas SET receita = %s, status = 'revisada' WHERE id = %s",
            (receita_editada, consulta_id)
        )
        
        return jsonify({'success': True, 'message': 'Receita atualizada com sucesso!'})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/receita/pdf/<int:consulta_id>')
def gerar_pdf_receita(consulta_id):
    """Gera PDF da receita médica"""
    if 'user_id' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    
    try:
        consulta_info = execute_query("""
            SELECT c.receita, p_u.nome, c.data_hora, m_u.nome as medico_nome
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s
        """, (consulta_id,), True)
        
        if not consulta_info:
            return jsonify({'error': 'Consulta não encontrada'}), 404
        
        receita, paciente_nome, data_hora, medico_nome = consulta_info[0]
        
        if not receita:
            return jsonify({'error': 'Nenhuma receita encontrada para esta consulta'}), 404
        
        data_formatada = formatar_data(data_hora)
        pdf_buffer = html_to_pdf(receita, paciente_nome, data_formatada)
        
        if not pdf_buffer:
            return jsonify({'error': 'Não foi possível gerar o PDF'}), 500
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"receita_{paciente_nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Erro na geração do PDF: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Erro interno ao gerar PDF: {str(e)}'}), 500

@app.route('/api/receita/html/<int:consulta_id>')
def obter_receita_html(consulta_id):
    """Obtém a receita em HTML para edição"""
    if 'user_id' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    
    try:
        receita_db = execute_query(
            "SELECT receita FROM consultas WHERE id = %s", 
            (consulta_id,), True
        )
        
        if not receita_db or not receita_db[0][0]:
            return jsonify({'error': 'Nenhuma receita encontrada'}), 404
        
        return jsonify({
            'success': True,
            'receita': receita_db[0][0]
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/analise-local', methods=['POST'])
def analise_local():
    """Análise local quando a API Gemini não está disponível"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados não fornecidos'}), 400
    
    tipo_exame = data.get('tipo_exame')
    observacoes = data.get('observacoes')
    consulta_id = data.get('consulta_id')
    paciente_nome = data.get('paciente_nome')
    
    if not all([tipo_exame, consulta_id, paciente_nome]):
        return jsonify({'error': 'Dados incompletos'}), 400
    
    diagnostico_simulado = f"""
    <div class="diagnostico-container">
        <div class="diagnostico-header">
            <h4><i class="fas fa-file-medical-alt"></i> Relatório de Diagnóstico (Modo Local)</h4>
            <p class="text-muted">Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>
        <div class="diagnostico-content">
            <h5>Paciente: {paciente_nome}</h5>
            <p><strong>Tipo de Exame:</strong> {tipo_exame}</p>
            <p><strong>Observações:</strong> {observacoes or 'Nenhuma'}</p>
            
            <div class="mt-3">
                <h6>Resultados da Análise:</h6>
                <p>Este é um diagnóstico simulado gerado em modo offline.</p>
                <p>Configure a API Gemini para obter análises mais precisas.</p>
            </div>
            
            <div class="alert alert-warning mt-3">
                <strong><i class="fas fa-exclamation-triangle"></i> Aviso:</strong>
                Este diagnóstico foi gerado em modo básico. Para análise completa com IA, configure a API Gemini.
            </div>
        </div>
    </div>
    """
    
    try:
        execute_query(
            "UPDATE consultas SET receita = %s, status = 'realizada' WHERE id = %s",
            (diagnostico_simulado, consulta_id)
        )
        
        return jsonify({'success': True, 'message': 'Análise local gerada com sucesso!'})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/diagnostico/chat/<int:consulta_id>', methods=['POST'])
def chat_diagnostico(consulta_id):
    """Chat entre médico e IA para discutir diagnóstico"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    if not gemini_available or client is None or MODEL_NAME is None:
        return jsonify({'error': 'API Key não configurada ou modelo indisponível'}), 500
    
    data = request.get_json() or {}
    user_message = data.get('message')
    
    if not user_message:
        return jsonify({'error': 'Mensagem vazia'}), 400
    
    try:
        chat_key = f"{session['user_id']}_{consulta_id}"
        
        if chat_key not in diagnostico_chats:
            consulta_info = execute_query("""
                SELECT c.receita, p_u.nome, p.data_nascimento, p.genero
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE c.id = %s
            """, (consulta_id,), True)
            
            if not consulta_info:
                return jsonify({'error': 'Consulta não encontrada'}), 404
            
            diagnostico, paciente_nome, data_nasc, genero = consulta_info[0]
            
            chat_session = client.chats.create(model=MODEL_NAME)
            diagnostico_chats[chat_key] = chat_session
            
            prompt_inicial = f"""
Você é um assistente médico especialista discutindo um caso com o Dr(a). {session['user_name']}.

INFORMAÇÕES DO PACIENTE:
- Nome: {paciente_nome}
- Data Nascimento: {data_nasc if data_nasc else 'Não informado'}
- Gênero: {genero if genero else 'Não informado'}

DIAGNÓSTICO ATUAL:
{diagnostico or 'Nenhum diagnóstico registrado ainda'}

Você deve:
1. Fornecer insights baseados em evidências científicas
2. Sugerir diagnósticos diferenciais quando apropriado
3. Ajudar na interpretação de exames
4. Sugerir ajustes no tratamento quando solicitado
5. Explicar conceitos médicos de forma clara

Seja colaborativo e respeitoso com a expertise do médico.
"""
            _ = chat_session.send_message(prompt_inicial)
        
        chat_session = diagnostico_chats[chat_key]
        response = chat_session.send_message(f"Médico: {user_message}")
        
        return jsonify({
            'response': getattr(response, "text", str(response)),
            'timestamp': datetime.now().strftime('%H:%M')
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/diagnostico/salvar/<int:consulta_id>', methods=['POST'])
def salvar_diagnostico_revisado(consulta_id):
    """Salva o diagnóstico após discussão com a IA"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    data = request.get_json() or {}
    diagnostico_revisado = data.get('diagnostico')
    
    if not diagnostico_revisado:
        return jsonify({'error': 'Diagnóstico vazio'}), 400
    
    try:
        execute_query(
            "UPDATE consultas SET receita = %s, status = 'revisada' WHERE id = %s",
            (diagnostico_revisado, consulta_id)
        )
        
        chat_key = f"{session['user_id']}_{consulta_id}"
        if chat_key in diagnostico_chats:
            try:
                del diagnostico_chats[chat_key]
            except Exception:
                diagnostico_chats.pop(chat_key, None)
        
        return jsonify({'success': True})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/receita/gerar/<int:consulta_id>', methods=['POST'])
def gerar_receita_medica(consulta_id):
    """Gera receita médica baseada no diagnóstico"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    if not gemini_available:
        return jsonify({'error': 'API Key não configurada.'}), 500
    
    try:
        diagnostico_db = execute_query(
            "SELECT receita FROM consultas WHERE id = %s", 
            (consulta_id,), True
        )
        diagnostico = diagnostico_db[0][0] if diagnostico_db and diagnostico_db[0][0] else ""
        
        paciente_db = execute_query("""
            SELECT p_u.nome, p.data_nascimento, p.genero 
            FROM consultas c 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE c.id = %s
        """, (consulta_id,), True)
        
        paciente_info = paciente_db[0] if paciente_db else ["Paciente", None, None]
        
        prompt = f"""
Com base no diagnóstico abaixo, gere uma receita médica profissional em HTML:

PACIENTE: {paciente_info[0]}
DATA NASC: {paciente_info[1] if paciente_info[1] else 'Não informado'}
GÊNERO: {paciente_info[2] if paciente_info[2] else 'Não informado'}

DIAGNÓSTICO:
{diagnostico}

Gere uma receita completa com:
1. Cabeçalho profissional
2. Diagnóstico resumido
3. Medicamentos (nome, dosagem, frequência, duração)
4. Recomendações
5. Data retorno
6. Assinatura

Use HTML com Bootstrap.
"""
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        receita_html = getattr(response, "text", str(response))
        
        execute_query(
            "UPDATE consultas SET receita = %s WHERE id = %s",
            (receita_html, consulta_id)
        )
        
        return jsonify({
            'receita': receita_html,
            'paciente': paciente_info[0],
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M')
        })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/receita/concordancia/<int:consulta_id>', methods=['POST'])
def concordancia_receita(consulta_id):
    """Processa concordância do médico com a receita gerada"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    data = request.get_json() or {}
    concordancia = data.get('concordancia')
    observacoes = data.get('observacoes', '')
    
    try:
        if concordancia:
            execute_query(
                "UPDATE consultas SET status = 'finalizada', receita_aprovada = TRUE WHERE id = %s",
                (consulta_id,)
            )
            return jsonify({'success': True, 'message': 'Receita aprovada com sucesso!'})
        else:
            execute_query(
                "UPDATE consultas SET status = 'em_revisao', receita_aprovada = FALSE WHERE id = %s",
                (consulta_id,)
            )
            
            receita_db = execute_query(
                "SELECT receita FROM consultas WHERE id = %s", 
                (consulta_id,), True
            )
            receita_atual = receita_db[0][0] if receita_db else ""
            
            return jsonify({
                'success': True, 
                'message': 'Vamos discutir a receita para melhorá-la.',
                'iniciar_chat': True,
                'receita_atual': receita_atual
            })
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/diagnostico/analisar/<int:consulta_id>', methods=['POST'])
def analisar_exame(consulta_id):
    """Analisa imagem do exame e gera diagnóstico usando Gemini"""
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autenticado'}), 401
    
    if not gemini_available:
        return jsonify({'error': 'API Gemini não configurada'}), 500
    
    try:
        consulta = execute_query("""
            SELECT c.id, p_u.nome as paciente_nome 
            FROM consultas c 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            JOIN medicos m ON c.medico_id = m.id 
            WHERE c.id = %s AND m.usuario_id = %s
        """, (consulta_id, session['user_id']), True)
        
        if not consulta:
            return jsonify({'error': 'Consulta não encontrada'}), 404
        
        consulta = consulta[0]
        
        if 'imagem' not in request.files:
            return jsonify({'error': 'Nenhuma imagem enviada'}), 400
        
        file = request.files['imagem']
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Arquivo não permitido'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        tipo_exame = request.form.get('tipo_exame', 'exame geral')
        observacoes_exame = request.form.get('observacoes_exame', '')
        
        img = Image.open(filepath)
        
        prompt = f"""
Analise esta imagem de exame médico e forneça um diagnóstico detalhado em formato HTML.

INFORMAÇÕES DO PACIENTE:
- Nome: {consulta[1]}
- Tipo de Exame: {tipo_exame}
- Observações: {observacoes_exame or 'Nenhuma'}

FORNECER EM HTML COM BOOTSTRAP:
1. RESUMO DOS ACHADOS - Descrição clara do que foi observado
2. DIAGNÓSTICO PRINCIPAL - Diagnóstico baseado nos achados
3. DIAGNÓSTICOS DIFERENCIAIS - Outras possibilidades a considerar
4. RECOMENDAÇÕES - Exames complementares, tratamentos, orientações
5. PROGNÓSTICO - Expectativa de evolução

Seja preciso e técnico, mas use linguagem acessível.
"""
        
        response = client.models.generate_content(
            model=MODEL_NAME, 
            contents=[prompt, img]
        )
        
        diagnostico_html = formatar_diagnostico(getattr(response, "text", str(response)))
        
        execute_query(
            "UPDATE consultas SET receita = %s, status = 'realizada' WHERE id = %s",
            (diagnostico_html, consulta_id)
        )
        
        return jsonify({
            'success': True,
            'diagnostico': diagnostico_html,
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M')
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Erro na análise: {str(e)}'}), 500

# ========== ROTAS PARA PACIENTE VISUALIZAR RECEITAS ==========
@app.route('/api/paciente/receita/<int:consulta_id>')
def paciente_obter_receita(consulta_id):
    """Obtém a receita para o paciente visualizar"""
    if 'user_id' not in session or session.get('user_type') != 'paciente':
        return jsonify({'error': 'Não autenticado'}), 401
    
    try:
        consulta_info = execute_query("""
            SELECT c.receita, c.receita_aprovada, p_u.nome as paciente_nome,
                   m_u.nome as medico_nome, c.data_hora
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s AND p.usuario_id = %s
        """, (consulta_id, session['user_id']), True)
        
        if not consulta_info:
            return jsonify({'error': 'Consulta não encontrada'}), 404
        
        receita, receita_aprovada, paciente_nome, medico_nome, data_hora = consulta_info[0]
        
        if not receita_aprovada:
            return jsonify({'error': 'Receita ainda não foi aprovada pelo médico'}), 403
        
        if not receita:
            return jsonify({'error': 'Nenhuma receita encontrada'}), 404
        
        return jsonify({
            'success': True,
            'receita': receita,
            'paciente_nome': paciente_nome,
            'medico_nome': medico_nome,
            'data_consulta': formatar_data(data_hora)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/paciente/receita/pdf/<int:consulta_id>')
def paciente_gerar_pdf_receita(consulta_id):
    """Gera PDF da receita para o paciente"""
    if 'user_id' not in session or session.get('user_type') != 'paciente':
        return jsonify({'error': 'Não autenticado'}), 401
    
    try:
        consulta_info = execute_query("""
            SELECT c.receita, p_u.nome, c.data_hora, m_u.nome as medico_nome,
                   c.receita_aprovada
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s AND p.usuario_id = %s
        """, (consulta_id, session['user_id']), True)
        
        if not consulta_info:
            return jsonify({'error': 'Consulta não encontrada'}), 404
        
        receita, paciente_nome, data_hora, medico_nome, receita_aprovada = consulta_info[0]
        
        if not receita_aprovada:
            return jsonify({'error': 'Receita não aprovada pelo médico'}), 403
        
        if not receita:
            return jsonify({'error': 'Nenhuma receita encontrada'}), 404
        
        data_formatada = formatar_data(data_hora)
        pdf_buffer = html_to_pdf(receita, paciente_nome, data_formatada)
        
        if not pdf_buffer:
            return jsonify({'error': 'Não foi possível gerar o PDF'}), 500
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"receita_medica_{paciente_nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Erro na geração do PDF: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Erro interno ao gerar PDF: {str(e)}'}), 500
    # Adicione isso no final do seu app.py, antes do if __name__ == '__main__'
@app.route('/list-routes')
def list_routes():
    """Lista todas as rotas disponíveis - para debug"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify(routes)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.secret_key = app.config.get('SECRET_KEY', 'default_secret_key')
    app.run(host='0.0.0.0', port=5005, debug=True)