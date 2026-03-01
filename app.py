# app.py - VERSÃO FINAL COMPLETA E CORRIGIDA COM ADMIN COMPLETO
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_mysqldb import MySQL
import uuid
from datetime import datetime
from config import Config
import os
from werkzeug.utils import secure_filename
from PIL import Image
import traceback
import logging
import json

# Importar utilitários
from utils.gemini import configurar_gemini
from utils.database import execute_query
from utils.helpers import formatar_data, calcular_idade, allowed_file
from utils.pdf import html_to_pdf

# Importar serviços
from services.receita_service import ReceitaService

# Importar rotas
from routes.auth import init_auth
from routes.medico import init_medico
from routes.paciente import init_paciente
from routes.consulta import create_consulta_blueprint
from routes.analista import init_analista
from routes.pedido_analise import init_pedido_analise

# Importar módulos do admin
from routes.admin import init_admin  # 👈 IMPORTANTE: Importa o inicializador completo

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# ========== INICIALIZAÇÃO DO BANCO DE DADOS ==========
mysql = MySQL(app)

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
    auth_bp = init_auth(mysql)
    app.register_blueprint(auth_bp)
    print("[1/7] Auth blueprint registrado com sucesso!")
except Exception as e:
    print(f"[1/7] Erro ao registrar Auth: {e}")
    raise

# 2. Médico (COM serviço de receitas)
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
    print("[2/7] Medico blueprint registrado com serviço de receitas!")
except Exception as e:
    print(f"[2/7] Erro ao registrar Medico: {e}")
    logger.error(f"Erro crítico no médico: {e}")
    logger.error(traceback.format_exc())
    raise

# 3. Paciente
try:
    paciente_bp = init_paciente(mysql, app)
    app.register_blueprint(paciente_bp)
    print("[3/7] Paciente blueprint registrado com sucesso!")
except Exception as e:
    print(f"[3/7] Erro ao registrar Paciente: {e}")
    raise

# 4. Analista
try:
    print("\nInicializando blueprint do analista (modular)...")
    analista_bp = init_analista(mysql, client, gemini_available, MODEL_NAME, app)
    app.register_blueprint(analista_bp)
    print("[4/7] Analista blueprint registrado com sucesso!")
    
    # Verificar rota específica
    rotas = verificar_rotas_blueprint('analista', '/analista')
    rota_analisar = any('/analista/analisar/' in r for r in rotas)
    if rota_analisar:
        print("   Rota /analista/analisar/<id> encontrada!")
    else:
        print("   ATENÇÃO: Rota /analista/analisar/ NÃO encontrada!")
        
except Exception as e:
    print(f"[4/7] Erro ao registrar Analista: {e}")
    print("   Verifique o arquivo routes/analista/__init__.py")
    raise

# 5. Pedido Análise
try:
    pedido_analise_bp = init_pedido_analise(mysql, app)
    app.register_blueprint(pedido_analise_bp)
    print("[5/7] Pedido_analise blueprint registrado com sucesso!")
except Exception as e:
    print(f"[5/7] Erro ao registrar Pedido_analise: {e}")
    raise

# 6. Consulta
try:
    consulta_bp = create_consulta_blueprint(mysql)
    app.register_blueprint(consulta_bp)
    print("[6/7] Consulta blueprint registrado com sucesso!")
except Exception as e:
    print(f"[6/7] Erro ao registrar Consulta: {e}")
    raise

# ===== ADMIN BLUEPRINT COMPLETO =====
# 7. Admin - Módulo completo com todas as rotas
try:
    admin_bp = init_admin(mysql)  # 👈 Agora usa o inicializador completo
    app.register_blueprint(admin_bp)
    print("[7/7] Admin blueprint registrado com sucesso!")
    print("   Modulos carregados:")
    print("      • auth - Autenticacao")
    print("      • dashboard - Dashboard principal")
    print("      • medicos - Gerenciamento de medicos")
    print("      • analistas - Gerenciamento de analistas")
    print("      • pacientes - Gerenciamento de pacientes")
    print("      • consultas - Listagem de consultas")
    print("      • estatisticas - Relatorios")
    print("      • configuracoes - Configuracoes do sistema")
except Exception as e:
    print(f"[7/7] Erro ao registrar Admin: {e}")
    raise

# ========== VERIFICACAO FINAL DE ROTAS ==========
print("\n" + "=" * 70)
print("VERIFICACAO FINAL DE ROTAS")
print("=" * 70)

with app.app_context():
    # Listar endpoints importantes
    endpoints_procurados = ['dashboard', 'dashboard_geral', 'auth.login', 'analista.dashboard', 'admin.login', 'admin.dashboard']
    
    for endpoint in endpoints_procurados:
        try:
            url = url_for(endpoint)
            print(f"   {endpoint}: {url}")
        except Exception as e:
            print(f"   {endpoint}: ERRO - {str(e)}")
    
    # Listar todas as rotas do admin
    rotas_admin = []
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/admin'):
            rotas_admin.append({
                'rota': str(rule),
                'endpoint': rule.endpoint,
                'metodos': list(rule.methods)
            })
    
    if rotas_admin:
        print(f"\n Rotas do admin encontradas: {len(rotas_admin)}")
        for rota in rotas_admin:
            print(f"    {rota['rota']} - {rota['endpoint']}")
    else:
        print(" NENHUMA ROTA DO ADMIN ENCONTRADA!")

print("=" * 70 + "\n")

# ========== FUNCOES AUXILIARES ==========
def obter_diagnostico_consulta(consulta_id):
    try:
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
    
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Erro interno do servidor: {e}")
    logger.error(traceback.format_exc())
    try:
        return render_template('500.html'), 500
    except:
        return "<h1>Erro 500 - Erro Interno do Servidor</h1>", 500

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
        return redirect(url_for('medico.consulta.detalhes_consulta', consulta_id=consulta_id))
    elif user_type == 'analista':
        return redirect(url_for('analista.analisar_pedido', pedido_id=consulta_id))
    else:
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

@app.route('/api/receita/pdf/<int:consulta_id>')
def gerar_pdf_receita(consulta_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nao autenticado'}), 401
    
    try:
        consulta_info = execute_query(mysql, """
            SELECT c.receita, p_u.nome, c.data_hora, m_u.nome as medico_nome
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s
        """, (consulta_id,), fetch=True, one=True)
        
        if not consulta_info:
            return jsonify({'error': 'Consulta nao encontrada'}), 404
        
        receita, paciente_nome, data_hora, medico_nome = consulta_info
        
        if not receita:
            return jsonify({'error': 'Nenhuma receita encontrada'}), 404
        
        data_formatada = formatar_data(data_hora)
        pdf_buffer = html_to_pdf(receita, paciente_nome, data_formatada, session)
        
        if not pdf_buffer:
            return jsonify({'error': 'Nao foi possivel gerar o PDF'}), 500
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"receita_{paciente_nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Erro na geracao do PDF: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/receita/html/<int:consulta_id>')
def obter_receita_html(consulta_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nao autenticado'}), 401
    
    try:
        receita_db = execute_query(mysql,
            "SELECT receita FROM consultas WHERE id = %s", 
            (consulta_id,), fetch=True, one=True
        )
        
        if not receita_db or not receita_db[0]:
            return jsonify({'error': 'Nenhuma receita encontrada'}), 404
        
        return jsonify({'success': True, 'receita': receita_db[0]})
        
    except Exception as e:
        logger.error(f"Erro ao obter receita HTML: {e}")
        return jsonify({'error': str(e)}), 500

# ========== ROTA PRINCIPAL DO DASHBOARD ==========
@app.route('/dashboard')
def dashboard():
    """Rota principal do dashboard - compativel com todos os blueprints"""
    if 'user_id' not in session:
        flash('Por favor, faca login para acessar esta pagina.', 'warning')
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    
    # Redirecionar para o dashboard especifico do tipo de usuario
    if user_type == 'paciente':
        return redirect(url_for('paciente.dashboard'))
    elif user_type == 'medico':
        return redirect(url_for('medico.dashboard'))
    elif user_type == 'analista':
        return redirect(url_for('analista.dashboard'))
    elif user_type == 'admin':
        return redirect(url_for('admin.dashboard'))
    else:
        # Dashboard geral para usuarios sem tipo especifico
        stats = {
            'pacientes': execute_query(mysql, "SELECT COUNT(*) FROM pacientes", fetch=True, one=True)[0] or 0,
            'medicos': execute_query(mysql, "SELECT COUNT(*) FROM medicos", fetch=True, one=True)[0] or 0,
            'analistas': execute_query(mysql, "SELECT COUNT(*) FROM analistas", fetch=True, one=True)[0] or 0,
            'consultas_hoje': execute_query(mysql,
                "SELECT COUNT(*) FROM consultas WHERE DATE(data_hora) = CURDATE()", 
                fetch=True, one=True
            )[0] or 0,
            'diagnosticos': execute_query(mysql, "SELECT COUNT(*) FROM diagnostico", fetch=True, one=True)[0] or 0
        }
        
        return render_template('dashboard.html', user=session, stats=stats)

# ROTA DASHBOARD GERAL (mantida para compatibilidade)
@app.route('/dashboard-geral')
def dashboard_geral():
    """Redireciona para a rota principal dashboard"""
    return redirect(url_for('dashboard'))

@app.route('/health')
def health_check():
    db_status = 'connected'
    try:
        mysql.connection.ping(True)
    except:
        db_status = 'disconnected'
    
    status = {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'gemini_available': gemini_available,
        'gemini_model': MODEL_NAME,
        'database': db_status,
        'upload_folder': os.path.isdir(UPLOAD_FOLDER),
        'blueprints': ['auth', 'medico', 'paciente', 'analista', 'consulta', 'pedido_analise', 'admin']
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
    """Rota temporaria para criar um pedido de teste"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if session.get('user_type') != 'analista':
        return "Acesso negado", 403
    
    try:
        pedido = execute_query(mysql, "SELECT id FROM pedidos_analise LIMIT 1", fetch=True, one=True)
        
        if pedido:
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido[0]))
        
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
            novo_id = result
            flash(f'Pedido de teste #{novo_id} criado com sucesso!', 'success')
            return redirect(url_for('analista.analisar_pedido', pedido_id=novo_id))
        else:
            flash('Erro ao criar pedido de teste', 'danger')
            return redirect(url_for('analista.dashboard'))
            
    except Exception as e:
        logger.error(f"Erro ao criar pedido de teste: {e}")
        flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('analista.dashboard'))

if __name__ == '__main__':
    app.secret_key = app.config.get('SECRET_KEY', 'default_secret_key')
    logger.info(f"Aplicacao iniciada. Gemini disponivel: {gemini_available}")
    
    print("\n" + "=" * 70)
    print("SISTEMA MEDICO INICIADO COM SUCESSO!")
    print("=" * 70)
    print(f"URL principal: http://localhost:50037")
    print(f"Health check: http://localhost:50037/health")
    print(f"Teste Gemini: http://localhost:50040/api/test-gemini")
    print(f"Criar pedido teste: http://localhost:50037/criar-pedido-teste-analista")
    print(f"Admin login: http://localhost:50037/admin/login")
    print(f"\nGemini: {'ATIVO' if gemini_available else 'INATIVO'}")
    print(f"   Modelo: {MODEL_NAME or 'Nenhum'}")
    if not gemini_available:
        print("     Limite da API excedido! Use analise manual.")
    print(f"\nServico de Receitas: ATIVO")
    print(f"\nBlueprints registrados: 7/7")
    print("=" * 70)
    print("\nSISTEMA PRONTO PARA USO!")
    print("Acesse: http://localhost:50037")
    print("=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=50042, debug=True)