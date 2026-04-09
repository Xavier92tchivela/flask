from flask import render_template, session, redirect, url_for, flash
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@farmaceutico_bp.route('/dashboard')
def dashboard():
    """Dashboard do farmacêutico"""
    
    print("\n===== DASHBOARD FARMACEUTICO =====")
    print(f"Sessao: {dict(session)}")
    
    # Verificar se está logado
    if not session.get('logged_in'):
        flash('Sessao expirada. Faca login novamente.', 'danger')
        return redirect(url_for('auth.login'))
    
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    
    print(f"user_id: {user_id}")
    print(f"user_type: {user_type}")
    
    # Funcao auxiliar para decodificar bytes
    def decode_value(val):
        if val is None:
            return ''
        if isinstance(val, bytes):
            return val.decode('utf-8', errors='ignore')
        return str(val) if val else ''
    
    # Verificar se é farmacêutico
    if user_type != 'farmaceutico':
        usuario = execute_query_auth("""
            SELECT tipo FROM usuarios WHERE id = %s
        """, (user_id,), True)
        
        if usuario and len(usuario) > 0:
            tipo_usuario = decode_value(usuario[0][0])
            if tipo_usuario == 'farmaceutico':
                session['user_type'] = 'farmaceutico'
                session.modified = True
                user_type = 'farmaceutico'
                print("Sessao corrigida para farmaceutico")
            else:
                flash('Acesso restrito a farmaceuticos.', 'danger')
                return redirect(url_for('auth.login'))
        else:
            flash('Usuario nao encontrado.', 'danger')
            return redirect(url_for('auth.login'))
    
    try:
        # Buscar dados do farmacêutico
        farmaceutico = execute_query_auth("""
            SELECT f.id, f.crf, f.especialidade, u.nome
            FROM farmaceuticos f
            JOIN usuarios u ON f.usuario_id = u.id
            WHERE f.usuario_id = %s AND f.ativo = 1
        """, (user_id,), True)
        
        print(f"Farmaceutico encontrado: {farmaceutico}")
        
        if not farmaceutico:
            flash('Dados do farmaceutico nao encontrados.', 'danger')
            return redirect(url_for('auth.logout'))
        
        farmaceutico_raw = farmaceutico[0]
        
        # Decodificar todos os campos do farmacêutico
        farmaceutico_clean = (
            farmaceutico_raw[0],  # id
            decode_value(farmaceutico_raw[1]),  # crf
            decode_value(farmaceutico_raw[2]),  # especialidade
            decode_value(farmaceutico_raw[3])   # nome
        )
        
        # ========== BUSCAR ESTATISTICAS ==========
        total_ativas = 0
        dispensas_hoje = 0
        estoque_baixo = 0
        validade_prox = 0
        
        # 1. TOTAL DE RECEITAS ATIVAS
        try:
            resultado_count = execute_query_auth("SELECT COUNT(*) FROM receita WHERE status = 'ativa'", fetch=True)
            if resultado_count and len(resultado_count) > 0:
                total_ativas = int(resultado_count[0][0]) if resultado_count[0][0] else 0
            print(f"TOTAL DE RECEITAS ATIVAS: {total_ativas}")
        except Exception as e:
            print(f"Erro ao contar receitas ativas: {e}")
            total_ativas = 0
        
        # 2. DISPENSAS DE HOJE
        try:
            resultado_disp = execute_query_auth("""
                SELECT COUNT(*) FROM receita 
                WHERE status = 'dispensada' 
                AND DATE(data_geracao_pdf) = CURDATE()
            """, fetch=True)
            
            if resultado_disp and len(resultado_disp) > 0:
                dispensas_hoje = int(resultado_disp[0][0]) if resultado_disp[0][0] else 0
            print(f"DISPENSAS HOJE: {dispensas_hoje}")
        except Exception as e:
            print(f"Erro ao contar dispensas: {e}")
            dispensas_hoje = 0
        
        # 3. ESTOQUE BAIXO - USANDO TABELA PRODUTOS
        try:
            resultado_estoque = execute_query_auth("""
                SELECT COUNT(*) FROM produtos 
                WHERE quantidade <= estoque_minimo 
                AND quantidade > 0
            """, fetch=True)
            
            if resultado_estoque and len(resultado_estoque) > 0:
                estoque_baixo = int(resultado_estoque[0][0]) if resultado_estoque[0][0] else 0
            print(f"ESTOQUE BAIXO: {estoque_baixo}")
        except Exception as e:
            print(f"Erro ao contar estoque baixo: {e}")
            estoque_baixo = 0
        
        # 4. VALIDADE PROXIMA - USANDO TABELA PRODUTOS
        try:
            resultado_validade = execute_query_auth("""
                SELECT COUNT(*) FROM produtos 
                WHERE data_validade IS NOT NULL
                AND data_validade <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                AND data_validade >= CURDATE()
            """, fetch=True)
            
            if resultado_validade and len(resultado_validade) > 0:
                validade_prox = int(resultado_validade[0][0]) if resultado_validade[0][0] else 0
            print(f"VALIDADE PROXIMA: {validade_prox}")
        except Exception as e:
            print(f"Erro ao contar validade proxima: {e}")
            validade_prox = 0
        
        # Montar tupla de estatisticas
        stats = (total_ativas, dispensas_hoje, estoque_baixo, validade_prox)
        print(f"STATS FINAL: {stats}")
        
        # ========== BUSCAR RECEITAS PARA LISTAR ==========
        receitas_ativas = []
        try:
            receitas_raw = execute_query_auth("""
                SELECT r.id, r.created_at, r.status, 
                       SUBSTRING(r.diagnostico, 1, 100) as diagnostico,
                       p.nome AS paciente_nome,
                       m.nome AS medico_nome
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                JOIN pacientes pac ON c.paciente_id = pac.id
                JOIN usuarios p ON pac.usuario_id = p.id
                JOIN medicos med ON c.medico_id = med.id
                JOIN usuarios m ON med.usuario_id = m.id
                WHERE r.status = 'ativa'
                ORDER BY r.created_at DESC
                LIMIT 10
            """, fetch=True)
            
            receitas_raw = receitas_raw or []
            print(f"RECEITAS ENCONTRADAS: {len(receitas_raw)}")
            
            for r in receitas_raw:
                if len(r) >= 6:
                    receita_dict = {
                        'id': r[0],
                        'created_at': r[1],
                        'status': decode_value(r[2]),
                        'diagnostico': decode_value(r[3])[:100],
                        'paciente_nome': decode_value(r[4]),
                        'medico_nome': decode_value(r[5])
                    }
                    receitas_ativas.append(receita_dict)
                    print(f"  - ID: {receita_dict['id']} | Paciente: {receita_dict['paciente_nome']}")
                    
        except Exception as e:
            print(f"Erro ao buscar receitas: {e}")
            import traceback
            traceback.print_exc()
        
        # Decodificar o nome do usuário na sessão
        user_name = session.get('user_name')
        if isinstance(user_name, bytes):
            user_name = user_name.decode('utf-8', errors='ignore')
            session['user_name'] = user_name
        
        # Atualizar último acesso
        session['ultimo_acesso'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        print(f"\nDADOS ENVIADOS:")
        print(f"   Stats: {stats}")
        print(f"   Receitas listadas: {len(receitas_ativas)}")
        
        return render_template('farmaceutico/dashboard.html',
                             farmaceutico=farmaceutico_clean,
                             stats=stats,
                             receitas_ativas=receitas_ativas,
                             nome_usuario=user_name,
                             now=datetime.now().strftime('%d/%m/%Y %H:%M'))
        
    except Exception as e:
        logger.error(f"Erro no dashboard do farmaceutico: {e}")
        print(f"EXCECAO: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar dashboard: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))