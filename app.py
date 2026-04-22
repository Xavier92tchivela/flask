from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
import pymysql
pymysql.install_as_MySQLdb()
import uuid
from datetime import datetime
from config import Config
import os
from werkzeug.utils import secure_filename
from PIL import Image
import traceback
import logging
import json

# Importar o middleware
from middleware.timing import TimingMiddleware

# Importar utilitários
from utils.gemini import configurar_gemini
from utils.database import execute_query
from utils.helpers import formatar_data, calcular_idade, allowed_file
from utils.pdf import html_to_pdf

# Importar serviços
from services.receita_service import ReceitaService
from services.dashboard_service import DashboardService

# Importar rotas
from routes.auth import init_auth
from routes.medico import init_medico
from routes.paciente import init_paciente
from routes.consulta import create_consulta_blueprint
from routes.analista import init_analista
from routes.pedido_analise import init_pedido_analise
from routes.enfermeiro import init_enfermeiro
from routes.assinatura import assinatura_bp
from routes.admin import init_admin
from routes.farmaceutico import farmaceutico_bp

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
app.wsgi_app = TimingMiddleware(app.wsgi_app)

# Configuração para mostrar erros detalhados
app.config['DEBUG'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True
app.secret_key = app.config.get('SECRET_KEY', 'chave_secreta_padrao_para_desenvolvimento')

# ========== INICIALIZAÇÃO DO BANCO DE DADOS COM PYMYSQL ==========
class MySQLConnection:
    """Classe substituta para flask_mysqldb usando PyMySQL"""
    
    def __init__(self, app=None):
        self.app = app
        self._connection = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
    
    def get_connection(self):
        """Retorna uma conexão ativa com o banco"""
        try:
            if self._connection is None or not self._connection.open:
                import pymysql
                import os
                
                # Obter configurações do app ou environment variables
                config = {
                    'host': os.environ.get('MYSQL_HOST', app.config.get('MYSQL_HOST', 'localhost')),
                    'user': os.environ.get('MYSQL_USER', app.config.get('MYSQL_USER', 'root')),
                    'password': os.environ.get('MYSQL_PASSWORD', app.config.get('MYSQL_PASSWORD', '')),
                    'database': os.environ.get('MYSQL_DB', app.config.get('MYSQL_DB', 'defaultdb')),
                    'port': int(os.environ.get('MYSQL_PORT', app.config.get('MYSQL_PORT', 3306))),
                    'cursorclass': pymysql.cursors.DictCursor,
                    'autocommit': False
                }
                
                # Adicionar SSL se necessário
                ssl_mode = os.environ.get('MYSQL_SSL_MODE', app.config.get('MYSQL_SSL_MODE', 'DISABLED'))
                if ssl_mode == 'REQUIRED':
                    config['ssl'] = {'ssl-mode': 'REQUIRED'}
                
                logger.info(f"Conectando ao banco: {config['host']}:{config['port']}/{config['database']}")
                self._connection = pymysql.connect(**config)
                logger.info("Conexão com banco de dados estabelecida com sucesso!")
            
            return self._connection
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco: {e}")
            raise
    
    @property
    def connection(self):
        """Propriedade para compatibilidade com código existente"""
        return self.get_connection()
    
    def close(self):
        """Fecha a conexão"""
        if self._connection and self._connection.open:
            self._connection.close()
            self._connection = None

# Instanciar o objeto mysql para compatibilidade
try:
    mysql = MySQLConnection(app)
    # Testar conexão
    conn = mysql.get_connection()
    conn.ping()
    logger.info("✅ Conexão com MySQL estabelecida com sucesso!")
except Exception as e:
    logger.error(f"❌ Falha ao conectar ao MySQL: {e}")
    mysql = None

# ========== CONFIGURAÇÃO GEMINI AI ==========
api_key = app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
client, gemini_available, MODEL_NAME = configurar_gemini(api_key)

# ========== CONFIGURAÇÕES GERAIS ==========
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ========== SERVIÇOS ==========
receita_service = ReceitaService(mysql, app, gemini_available, MODEL_NAME)

# ========== FUNÇÃO PARA VERIFICAR ROTAS ==========
def verificar_rotas_blueprint(bp_name, bp_prefix):
    """Verifica se as rotas de um blueprint foram registradas"""
    with app.app_context():
        rotas_encontradas = []
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith(bp_prefix):
                rotas_encontradas.append(str(rule))
        return rotas_encontradas

# ========== REGISTRAR BLUEPRINTS ==========
print("\n" + "=" * 70)
print("INICIANDO REGISTRO DE BLUEPRINTS")
print("=" * 70)

# 1. Auth
try:
    if mysql:
        auth_bp = init_auth(mysql)
        app.register_blueprint(auth_bp)
        print("[1/10] Auth blueprint registrado com sucesso!")
    else:
        print("[1/10] ERRO: MySQL não disponível para Auth")
        raise Exception("MySQL não disponível")
except Exception as e:
    print(f"[1/10] Erro ao registrar Auth: {e}")
    traceback.print_exc()
    raise

# 2. Médico
try:
    medico_bp = init_medico(
        mysql=mysql, 
        client=client, 
        gemini_available=gemini_available, 
        MODEL_NAME=MODEL_NAME, 
        app=app,
        receita_service=receita_service
    )
    app.register_blueprint(medico_bp)
    print("[2/10] Medico blueprint registrado com serviço de receitas!")
except Exception as e:
    print(f"[2/10] Erro ao registrar Medico: {e}")
    logger.error(f"Erro crítico no médico: {e}")
    logger.error(traceback.format_exc())
    raise

# 3. Paciente
try:
    paciente_bp = init_paciente(mysql, app)
    app.register_blueprint(paciente_bp)
    print("[3/10] Paciente blueprint registrado com sucesso!")
except Exception as e:
    print(f"[3/10] Erro ao registrar Paciente: {e}")
    traceback.print_exc()
    raise

# 4. Analista
try:
    print("\nInicializando blueprint do analista (modular)...")
    analista_bp = init_analista(mysql, client, gemini_available, MODEL_NAME, app)
    app.register_blueprint(analista_bp)
    print("[4/10] Analista blueprint registrado com sucesso!")
    
    rotas = verificar_rotas_blueprint('analista', '/analista')
    rota_analisar = any('/analista/analisar/' in r for r in rotas)
    if rota_analisar:
        print("   Rota /analista/analisar/<id> encontrada!")
    else:
        print("   ATENÇÃO: Rota /analista/analisar/ NÃO encontrada!")
        
except Exception as e:
    print(f"[4/10] Erro ao registrar Analista: {e}")
    print("   Verifique o arquivo routes/analista/__init__.py")
    traceback.print_exc()
    raise

# 5. Pedido Análise
try:
    pedido_analise_bp = init_pedido_analise(mysql, app)
    app.register_blueprint(pedido_analise_bp)
    print("[5/10] Pedido_analise blueprint registrado com sucesso!")
except Exception as e:
    print(f"[5/10] Erro ao registrar Pedido_analise: {e}")
    traceback.print_exc()
    raise

# 6. Consulta
try:
    consulta_bp = create_consulta_blueprint(mysql)
    app.register_blueprint(consulta_bp)
    print("[6/10] Consulta blueprint registrado com sucesso!")
except Exception as e:
    print(f"[6/10] Erro ao registrar Consulta: {e}")
    traceback.print_exc()
    raise

# 7. Enfermeiro
try:
    enfermeiro_bp = init_enfermeiro(mysql)
    app.register_blueprint(enfermeiro_bp)
    print("[7/10] Enfermeiro blueprint registrado com sucesso!")
    print("   Modulos carregados:")
    print("      • dashboard - Dashboard do enfermeiro")
    print("      • triagem - Gerenciamento de triagens")
    print("      • sinais_vitais - Registro de sinais vitais")
    print("      • historico - Histórico de pacientes")
    print("      • perfil - Perfil do enfermeiro")
    print("      • api - API para consultas")
except Exception as e:
    print(f"[7/10] Erro ao registrar Enfermeiro: {e}")
    logger.error(f"Erro crítico no enfermeiro: {e}")
    logger.error(traceback.format_exc())
    raise

# 8. Assinatura
try:
    app.register_blueprint(assinatura_bp)
    print("[8/10] Assinatura blueprint registrado com sucesso!")
    
    with app.app_context():
        rotas_ass = []
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/assinatura'):
                rotas_ass.append(str(rule))
        if rotas_ass:
            print("   Rotas registradas:")
            for rota in rotas_ass:
                print(f"      • {rota}")
        else:
            print("    Nenhuma rota encontrada para /assinatura/")
            
except Exception as e:
    print(f"[8/10] Erro ao registrar Assinatura: {e}")
    traceback.print_exc()
    raise

# 9. Admin
try:
    admin_bp = init_admin(mysql)
    app.register_blueprint(admin_bp)
    print("[9/10] Admin blueprint registrado com sucesso!")
    print("   Modulos carregados:")
    print("      • auth - Autenticacao")
    print("      • dashboard - Dashboard principal")
    print("      • medicos - Gerenciamento de medicos")
    print("      • analistas - Gerenciamento de analistas")
    print("      • pacientes - Gerenciamento de pacientes")
    print("      • enfermeiros - Gerenciamento de enfermeiros")
    print("      • consultas - Listagem de consultas")
    print("      • estatisticas - Relatorios")
    print("      • configuracoes - Configuracoes do sistema")
except Exception as e:
    print(f"[9/10] Erro ao registrar Admin: {e}")
    traceback.print_exc()
    raise

# 10. FARMACÊUTICO
try:
    app.register_blueprint(farmaceutico_bp)
    print("[10/10] Farmaceutico blueprint registrado com sucesso!")
    print("   Modulos carregados:")
    print("      • dashboard - Dashboard do farmacêutico")
    print("      • prescricoes - Gerenciamento de prescrições")
    print("      • dispensacoes - Gerenciamento de dispensações")
    print("      • estoque - Gerenciamento de estoque")
    print("      • produtos - Catálogo de produtos")
    print("      • fornecedores - Gerenciamento de fornecedores")
    print("      • relatorios - Relatórios do farmacêutico")
except Exception as e:
    print(f"[10/10] Erro ao registrar Farmaceutico: {e}")
    logger.error(f"Erro crítico no farmacêutico: {e}")
    logger.error(traceback.format_exc())
    raise

# ========== VERIFICACAO FINAL DE ROTAS ==========
print("\n" + "=" * 70)
print("VERIFICACAO FINAL DE ROTAS")
print("=" * 70)

with app.app_context():
    endpoints_procurados = [
        'dashboard', 'dashboard_geral', 
        'auth.login', 
        'analista.dashboard', 
        'enfermeiro.dashboard.index',
        'admin.login', 'admin.dashboard',
        'assinatura.index',
        'farmaceutico.dashboard'
    ]
    
    for endpoint in endpoints_procurados:
        try:
            url = url_for(endpoint)
            print(f"    ✅ {endpoint}: {url}")
        except Exception as e:
            print(f"    ❌ {endpoint}: ERRO - {str(e)}")
    
    # Verificar rotas do farmacêutico
    rotas_farmaceutico = []
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/farmaceutico'):
            rotas_farmaceutico.append({
                'rota': str(rule),
                'endpoint': rule.endpoint,
                'metodos': list(rule.methods)
            })
    
    if rotas_farmaceutico:
        print(f"\n✅ Rotas do farmacêutico encontradas: {len(rotas_farmaceutico)}")
        for rota in rotas_farmaceutico[:5]:
            print(f"    • {rota['rota']} - {rota['endpoint']}")
        if len(rotas_farmaceutico) > 5:
            print(f"    ... e mais {len(rotas_farmaceutico) - 5} rotas")
    else:
        print("\n❌ NENHUMA ROTA DO FARMACÊUTICO ENCONTRADA!")

print("=" * 70 + "\n")

# ========== FUNCOES AUXILIARES ==========
def obter_diagnostico_consulta(consulta_id):
    try:
        if not mysql:
            return None
            
        diagnostico = execute_query(mysql, """
            SELECT d.*, c.data_hora,
                   p_u.nome as paciente_nome, p.data_nascimento, p.genero,
                   m_u.nome as medico_nome, m.especialidade, m.crm
            FROM diagnostico d
            JOIN consultas c ON d.consulta_id = c.id
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE d.consulta_id = %s
        """, (consulta_id,), fetch=True)
        
        if not diagnostico:
            return None
        
        d = diagnostico[0]
        return {
            'id': d[0], 'consulta_id': d[1], 'tipo_exame': d[2],
            'descricao': d[3], 'observacoes': d[4], 'resultado': d[5],
            'diagnostico_preliminar': d[6], 'diagnostico_final': d[7],
            'status': d[8], 'imagem_path': d[9], 'imagem_base64': d[10],
            'formato_imagem': d[11], 'tamanho_imagem': d[12],
            'criado_em': formatar_data(d[13]), 'atualizado_em': formatar_data(d[14]),
            'data_consulta': formatar_data(d[15]), 'paciente_nome': d[16],
            'paciente_data_nascimento': formatar_data(d[17], '%d/%m/%Y') if d[17] else None,
            'paciente_genero': d[18], 'medico_nome': d[19],
            'medico_especialidade': d[20], 'medico_crm': d[21]
        }
    except Exception as e:
        logger.error(f"Erro ao obter diagnostico: {e}")
        return None

# ========== CONTEXT PROCESSOR ==========
@app.context_processor
def inject_utils():
    return dict(
        datetime=datetime,
        formatar_data=formatar_data,
        gemini_available=gemini_available,
        MODEL_NAME=MODEL_NAME
    )

# ========== ROTAS DE ERRO ==========
@app.errorhandler(404)
def page_not_found(e):
    logger.error(f"Pagina nao encontrada: {request.url}")
    
    if '/analista/' in request.url:
        flash('Pedido nao encontrado ou rota invalida.', 'warning')
        return redirect(url_for('analista.dashboard'))
    elif '/enfermeiro/' in request.url:
        flash('Registro nao encontrado.', 'warning')
        return redirect(url_for('enfermeiro.dashboard.index'))
    elif '/farmaceutico/' in request.url:
        flash('Página não encontrada.', 'warning')
        return redirect(url_for('farmaceutico.dashboard'))
    
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Erro interno do servidor: {e}")
    logger.error(traceback.format_exc())
    try:
        return render_template('500.html', error=str(e)), 500
    except:
        return f"<h1>Erro 500 - Erro Interno do Servidor</h1><pre>{traceback.format_exc()}</pre>", 500

# ========== ROTAS GERAIS ==========
@app.route('/')
def index():
    return redirect(url_for('auth.index'))

@app.route('/minhas_consultas')
def minhas_consultas():
    if 'user_id' not in session:
        flash('Por favor, faca login para acessar esta pagina.', 'warning')
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    
    if user_type == 'paciente':
        return redirect(url_for('paciente.minhas_consultas'))
    elif user_type == 'medico':
        return redirect(url_for('medico.dashboard'))
    elif user_type == 'analista':
        return redirect(url_for('analista.dashboard'))
    elif user_type == 'enfermeiro':
        return redirect(url_for('enfermeiro.dashboard.index'))
    elif user_type == 'farmaceutico':
        return redirect(url_for('farmaceutico.dashboard'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/consultas/<int:consulta_id>')
def detalhes_consulta(consulta_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    
    if user_type == 'paciente':
        return redirect(url_for('paciente.detalhes_consulta', consulta_id=consulta_id))
    elif user_type == 'medico':
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    elif user_type == 'analista':
        return redirect(url_for('analista.analisar_pedido', pedido_id=consulta_id))
    elif user_type == 'enfermeiro' and mysql:
        sinais = execute_query(mysql, """
            SELECT id FROM sinais_vitais WHERE consulta_id = %s
        """, (consulta_id,), fetch=True, one=True)
        if sinais:
            return redirect(url_for('enfermeiro.sinais_vitais.detalhes_sinais_vitais', vital_id=sinais[0]))
        else:
            return redirect(url_for('enfermeiro.sinais_vitais.registrar_sinais_vitais', consulta_id=consulta_id))
    else:
        if not mysql:
            flash('Banco de dados não disponível', 'danger')
            return redirect(url_for('dashboard'))
            
        consulta = execute_query(mysql, """
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, m.crm,
                   c.data_hora, c.status, c.observacoes, c.receita,
                   p_u.nome as paciente_nome, p.data_nascimento, p.genero
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            JOIN pacientes p ON c.paciente_id = p.id 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE c.id = %s
        """, (consulta_id,), fetch=True, one=True)
        
        if not consulta:
            flash('Consulta nao encontrada.', 'danger')
            return redirect(url_for('dashboard'))
        
        diagnostico_info = obter_diagnostico_consulta(consulta_id)
        
        return render_template('detalhes_consulta.html', 
                             consulta=consulta, 
                             diagnostico=diagnostico_info,
                             user=session,
                             user_type=user_type)

# ========== ROTAS DA API DO DASHBOARD ==========
@app.route('/medico/api/pedidos-recentes')
def api_pedidos_recentes():
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autorizado'}), 401
    
    medico_id = session.get('medico_id')
    
    try:
        if not mysql:
            return jsonify({'error': 'Banco de dados indisponível'}), 500
            
        conn = mysql.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                pa.id,
                pa.tipo_exame,
                pa.status,
                pa.status_aprovacao,
                DATE_FORMAT(pa.data_solicitacao, '%%d/%%m/%%Y %%H:%%i') as data_solicitacao,
                u.nome as paciente_nome
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE pa.medico_id = %s
            ORDER BY pa.data_solicitacao DESC
            LIMIT 5
        """, (medico_id,))
        
        pedidos = cur.fetchall()
        cur.close()
        
        pedidos_lista = []
        for p in pedidos:
            pedidos_lista.append({
                'id': p['id'],
                'tipo_exame': p['tipo_exame'],
                'status': p['status'],
                'status_aprovacao': p['status_aprovacao'],
                'data_solicitacao': p['data_solicitacao'],
                'paciente_nome': p['paciente_nome']
            })
        
        return jsonify({'pedidos': pedidos_lista})
        
    except Exception as e:
        logger.error(f"Erro ao buscar pedidos: {e}")
        return jsonify({'pedidos': []})

@app.route('/medico/api/contadores')
def api_contadores():
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autorizado'}), 401
    
    medico_id = session.get('medico_id')
    
    try:
        if not mysql:
            return jsonify({'error': 'Banco de dados indisponível'}), 500
            
        dados = DashboardService.get_dados_dashboard(medico_id, mysql)
        
        return jsonify({
            'consultas_hoje': dados['consultas_hoje'],
            'resultados_pendentes': dados['resultados_pendentes'],
            'analises_solicitadas': dados['analises_solicitadas'],
            'notificacoes': dados['notificacoes']
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar contadores: {e}")
        return jsonify({
            'consultas_hoje': 0,
            'resultados_pendentes': 0,
            'analises_solicitadas': 0,
            'notificacoes': 0
        })

@app.route('/medico/api/notificacoes')
def api_notificacoes():
    if 'user_id' not in session or session.get('user_type') != 'medico':
        return jsonify({'error': 'Não autorizado'}), 401
    
    medico_id = session.get('medico_id')
    
    try:
        if not mysql:
            return jsonify({'error': 'Banco de dados indisponível'}), 500
            
        conn = mysql.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                pa.id,
                pa.tipo_exame,
                u.nome as paciente_nome,
                DATE_FORMAT(pa.data_conclusao, '%%d/%%m/%%Y %%H:%%i') as data_conclusao,
                TIMESTAMPDIFF(HOUR, pa.data_conclusao, NOW()) as horas_atras
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE pa.medico_id = %s 
              AND pa.status = 'concluido' 
              AND pa.status_aprovacao = 'pendente'
              AND pa.data_conclusao >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY pa.data_conclusao DESC
            LIMIT 5
        """, (medico_id,))
        
        notificacoes = cur.fetchall()
        cur.close()
        
        notificacoes_lista = []
        for n in notificacoes:
            tempo = f"há {n['horas_atras']} horas" if n['horas_atras'] < 24 else f"há {n['horas_atras']//24} dias"
            notificacoes_lista.append({
                'id': n['id'],
                'titulo': f"Resultado: {n['tipo_exame']}",
                'mensagem': f"{n['paciente_nome']} - Aguardando revisão",
                'tempo': tempo,
                'link': f"/medico/revisar-analise/{n['id']}"
            })
        
        return jsonify({'notificacoes': notificacoes_lista})
        
    except Exception as e:
        logger.error(f"Erro ao buscar notificações: {e}")
        return jsonify({'notificacoes': []})

# ========== ROTA PRINCIPAL DO DASHBOARD ==========
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Por favor, faca login para acessar esta pagina.', 'warning')
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    
    if user_type == 'paciente':
        return redirect(url_for('paciente.dashboard'))
    elif user_type == 'medico':
        return redirect(url_for('medico.dashboard'))
    elif user_type == 'analista':
        return redirect(url_for('analista.dashboard'))
    elif user_type == 'enfermeiro':
        return redirect(url_for('enfermeiro.dashboard.index'))
    elif user_type == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif user_type == 'farmaceutico':
        return redirect(url_for('farmaceutico.dashboard'))
    else:
        if not mysql:
            stats = {
                'pacientes': 0,
                'medicos': 0,
                'analistas': 0,
                'enfermeiros': 0,
                'consultas_hoje': 0,
                'diagnosticos': 0,
                'sinais_vitais': 0
            }
        else:
            stats = {
                'pacientes': execute_query(mysql, "SELECT COUNT(*) as total FROM pacientes", fetch=True, one=True)['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM pacientes", fetch=True, one=True) else 0,
                'medicos': execute_query(mysql, "SELECT COUNT(*) as total FROM medicos", fetch=True, one=True)['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM medicos", fetch=True, one=True) else 0,
                'analistas': execute_query(mysql, "SELECT COUNT(*) as total FROM analistas", fetch=True, one=True)['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM analistas", fetch=True, one=True) else 0,
                'enfermeiros': execute_query(mysql, "SELECT COUNT(*) as total FROM enfermeiros", fetch=True, one=True)['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM enfermeiros", fetch=True, one=True) else 0,
                'consultas_hoje': execute_query(mysql,
                    "SELECT COUNT(*) as total FROM consultas WHERE DATE(data_hora) = CURDATE()", 
                    fetch=True, one=True
                )['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM consultas WHERE DATE(data_hora) = CURDATE()", fetch=True, one=True) else 0,
                'diagnosticos': execute_query(mysql, "SELECT COUNT(*) as total FROM diagnostico", fetch=True, one=True)['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM diagnostico", fetch=True, one=True) else 0,
                'sinais_vitais': execute_query(mysql, "SELECT COUNT(*) as total FROM sinais_vitais", fetch=True, one=True)['total'] if execute_query(mysql, "SELECT COUNT(*) as total FROM sinais_vitais", fetch=True, one=True) else 0
            }
        
        return render_template('dashboard.html', user=session, stats=stats)

@app.route('/dashboard-geral')
def dashboard_geral():
    return redirect(url_for('dashboard'))

@app.route('/health')
def health_check():
    db_status = 'connected'
    db_error = None
    try:
        if mysql:
            conn = mysql.get_connection()
            conn.ping()
        else:
            db_status = 'disconnected'
            db_error = 'MySQL not initialized'
    except Exception as e:
        db_status = 'disconnected'
        db_error = str(e)
    
    status = {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'gemini_available': gemini_available,
        'gemini_model': MODEL_NAME,
        'database': db_status,
        'database_error': db_error,
        'upload_folder': os.path.isdir(UPLOAD_FOLDER),
        'blueprints': ['auth', 'medico', 'paciente', 'analista', 'consulta', 'pedido_analise', 'enfermeiro', 'admin', 'assinatura', 'farmaceutico']
    }
    return jsonify(status)

@app.route('/api/test-gemini')
def test_gemini():
    if not gemini_available or not client:
        return jsonify({
            'success': False,
            'message': 'Gemini nao esta disponivel',
            'available': False
        }), 503
    
    try:
        if client and client.get('model'):
            import google.generativeai as genai
            
            response = client['model'].generate_content(
                "Ola! Responda apenas com 'TESTE OK'.",
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1, 
                    max_output_tokens=20
                )
            )
            
            resposta = response.text if response and hasattr(response, 'text') else str(response)
            
            return jsonify({
                'success': True,
                'available': True,
                'model': MODEL_NAME,
                'response': resposta
            })
        else:
            return jsonify({'success': False, 'message': 'Modelo nao configurado'}), 500
            
    except Exception as e:
        logger.error(f"Erro no teste Gemini: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/criar-pedido-teste-analista')
def criar_pedido_teste_analista():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if session.get('user_type') != 'analista':
        return "Acesso negado", 403
    
    try:
        if not mysql:
            flash('Banco de dados não disponível', 'danger')
            return redirect(url_for('analista.dashboard'))
            
        pedido = execute_query(mysql, "SELECT id FROM pedidos_analise LIMIT 1", fetch=True, one=True)
        
        if pedido:
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido['id']))
        
        result = execute_query(mysql, """
            INSERT INTO pedidos_analise 
            (tipo_exame, descricao, urgencia, status, data_solicitacao, criado_em)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
        """, (
            'Raio-X Torax',
            'Paciente com tosse persistente ha 3 dias',
            'normal',
            'pendente'
        ), commit=True)
        
        if result:
            flash(f'Pedido de teste criado com sucesso!', 'success')
            return redirect(url_for('analista.dashboard'))
        else:
            flash('Erro ao criar pedido de teste', 'danger')
            return redirect(url_for('analista.dashboard'))
            
    except Exception as e:
        logger.error(f"Erro ao criar pedido de teste: {e}")
        flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('analista.dashboard'))

# ========== INICIALIZAÇÃO DO BANCO DE DADOS ==========
def init_database():
    """Cria as tabelas necessárias se não existirem"""
    if not mysql:
        logger.error("MySQL não disponível para inicialização")
        return False
    
    try:
        conn = mysql.get_connection()
        cursor = conn.cursor()
        
        # Criar tabela usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                uuid VARCHAR(36) UNIQUE NOT NULL,
                nome VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                senha VARCHAR(255) NOT NULL,
                telefone VARCHAR(20),
                tipo ENUM('paciente', 'medico', 'analista', 'enfermeiro', 'farmaceutico') NOT NULL,
                ativo BOOLEAN DEFAULT TRUE,
                reset_token VARCHAR(255),
                reset_token_expira DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Criar tabela pacientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pacientes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT UNIQUE,
                data_nascimento DATE,
                endereco TEXT,
                genero ENUM('masculino', 'feminino', 'outro'),
                telefone VARCHAR(255),
                alergias TEXT,
                medicamentos_uso TEXT,
                historico_doencas TEXT,
                contato_emergencia VARCHAR(255),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        
        # Criar tabela medicos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT UNIQUE,
                crm VARCHAR(20),
                especialidade VARCHAR(100),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        
        # Criar tabela farmaceuticos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS farmaceuticos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT UNIQUE,
                crf VARCHAR(20),
                especialidade VARCHAR(100),
                ativo BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        cursor.close()
        logger.info("✅ Banco de dados inicializado com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        return False

if __name__ == '__main__':
    # Inicializar banco de dados
    init_database()
    
    logger.info(f"Aplicacao iniciada. Gemini disponivel: {gemini_available}")
    
    print("\n" + "=" * 70)
    print("🚀 SISTEMA MEDICO INICIADO COM SUCESSO!")
    print("=" * 70)
    print(f"📍 URL principal: http://localhost:5000")
    print(f"🔍 Health check: http://localhost:5000/health")
    print(f"🤖 Teste Gemini: http://localhost:5000/api/test-gemini")
    print(f"🧪 Criar pedido teste: http://localhost:5000/criar-pedido-teste-analista")
    print(f"👑 Admin login: http://localhost:5000/admin/login")
    print(f"👨‍⚕️ Enfermeiro dashboard: http://localhost:5000/enfermeiro/dashboard/")
    print(f"💊 FARMACÊUTICO login: http://localhost:5000/auth/login")
    print(f"💊 FARMACÊUTICO dashboard: http://localhost:5000/farmaceutico/dashboard")
    print(f"✍️ ASSINATURA: http://localhost:5000/assinatura/")
    print(f"🧪 Teste assinatura: http://localhost:5000/assinatura/teste")
    print(f"\n🤖 Gemini: {'✅ ATIVO' if gemini_available else '❌ INATIVO'}")
    print(f"   Modelo: {MODEL_NAME or 'Nenhum'}")
    if not gemini_available:
        print("     ⚠️ Limite da API excedido! Use análise manual.")
    print(f"\n📦 Servico de Receitas: ✅ ATIVO")
    print(f"\n📋 Blueprints registrados: 10/10")
    print("    ✅ Auth")
    print("    ✅ Medico")
    print("    ✅ Paciente")
    print("    ✅ Analista")
    print("    ✅ Pedido Análise")
    print("    ✅ Consulta")
    print("    ✅ Enfermeiro")
    print("    ✅ Assinatura")
    print("    ✅ Admin")
    print("    ✅ FARMACÊUTICO")
    print("=" * 70)
    print("\n🎯 SISTEMA PRONTO PARA USO!")
    print("🌐 Acesse: http://localhost:5000")
    print("=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
