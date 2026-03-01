# routes/analista_fallback.py
from flask import Blueprint, render_template, redirect, url_for, flash, session,jsonify
from functools import wraps
import datetime

def create_analista_fallback():
    """Cria blueprint de fallback para analista - VERSÃO CORRIGIDA COM ROTAS COMPLETAS"""
    
    print("📝 Criando blueprint de fallback do analista (com todas as rotas)...")
    
    analista_fallback = Blueprint('analista', __name__, url_prefix='/analista')
    
    def analista_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            if session.get('user_type') != 'analista':
                flash('Acesso restrito a analistas.', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    
    @analista_fallback.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista (fallback)"""
        return render_template('analista/dashboard.html', 
                              user=session, 
                              analista={'nome': session.get('user_name', 'Analista')},
                              estatisticas={'pendentes': 0, 'em_analise': 0, 'concluidos': 0, 'urgentes': 0},
                              pedidos_atribuidos=[])
    
    @analista_fallback.route('/pedidos')
    @analista_required
    def pedidos():
        """Lista de pedidos (fallback)"""
        return render_template('analista/pedidos.html', 
                              user=session, 
                              pedidos=[])
    
    # ===== ROTA CORRIGIDA =====
    @analista_fallback.route('/analisar/<int:pedido_id>', methods=['GET', 'POST'])  # 👈 CORREÇÃO AQUI!
    @analista_required
    def analisar_pedido(pedido_id):
        """Página de análise de pedido (fallback)"""
        flash('Módulo de análise em modo de contingência. Funcionalidades limitadas.', 'warning')
        
        # Dados simulados para teste
        pedido_simulado = {
            'id': pedido_id,
            'tipo_exame': 'Exame de Teste',
            'descricao': 'Descrição simulada para teste',
            'observacoes': 'Observações simuladas',
            'urgencia': 'normal',
            'status': 'pendente',
            'data_solicitacao': '25/02/2026 10:30',
            'paciente_nome': 'Paciente Teste',
            'paciente_idade': '30 anos',
            'paciente_genero': 'Masculino',
            'medico_nome': 'Dr. Teste'
        }
        
        return render_template('analista/analisar_exame.html', 
                              user=session, 
                              pedido=pedido_simulado,
                              anexos_pedido=[],
                              diagnosticos_anteriores=[],
                              gemini_available=False,
                              MODEL_NAME=None,
                              now=datetime.now())
    
    @analista_fallback.route('/minhas-analises')
    @analista_required
    def minhas_analises():
        """Histórico de análises (fallback)"""
        return render_template('analista/minhas_analises.html', 
                              user=session, 
                              analises=[])
    
    @analista_fallback.route('/historico')
    @analista_required
    def historico():
        """Alias para minhas_analises"""
        return redirect(url_for('analista.minhas_analises'))
    
    @analista_fallback.route('/perfil')
    @analista_required
    def perfil():
        """Perfil do analista (fallback)"""
        return render_template('analista/perfil.html', 
                              user=session,
                              analista={'nome': session.get('user_name', 'Analista')})
    
    @analista_fallback.route('/configuracoes')
    @analista_required
    def configuracoes():
        """Configurações (fallback)"""
        return render_template('analista/configuracoes.html', 
                              user=session,
                              gemini_available=False,
                              MODEL_NAME=None)
    
    @analista_fallback.route('/proximo-pedido')
    @analista_required
    def proximo_pedido():
        """Próximo pedido (fallback)"""
        flash('Módulo de análise não está totalmente configurado.', 'warning')
        return redirect(url_for('analista.dashboard'))
    
    # ===== ROTAS API =====
    @analista_fallback.route('/api/gemini-status')
    @analista_required
    def api_gemini_status():
        """API status Gemini (fallback)"""
        return jsonify({
            'success': True,
            'gemini_available': False,
            'model_name': 'Nenhum (modo fallback)',
            'timestamp': datetime.now().isoformat()
        })
    
    @analista_fallback.route('/api/analisar_imagem/<int:pedido_id>', methods=['POST'])
    @analista_required
    def api_analisar_imagem(pedido_id):
        """API análise de imagem (fallback)"""
        return jsonify({
            'success': False,
            'error': 'API Gemini não disponível no modo fallback',
            'warning': 'Use análise manual',
            'pedido_status': 'pendente'
        }), 503
    
    print("✅ Blueprint de fallback do analista criado com sucesso!")
    return analista_fallback