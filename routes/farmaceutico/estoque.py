from flask import render_template, session, redirect, url_for, flash, request, jsonify
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@farmaceutico_bp.route('/estoque')
def estoque():
    """Gerenciamento de estoque de medicamentos"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        # Buscar todos os produtos da tabela produtos
        produtos_raw = execute_query_auth("""
            SELECT id, nome, descricao, categoria, quantidade, unidade,
                   estoque_minimo, lote, data_validade, fornecedor_id,
                   preco_custo, preco_venda, localizacao
            FROM produtos
            ORDER BY nome
        """, fetch=True) or []
        
        # Converter para dicionarios
        produtos = []
        total_unidades = 0
        for p in produtos_raw:
            quantidade = p[4] if p[4] else 0
            estoque_minimo = p[6] if p[6] else 0
            
            total_unidades += quantidade
            
            # Calcular status do estoque
            if quantidade <= 0:
                status = 'esgotado'
                status_class = 'danger'
                status_text = 'Esgotado'
            elif quantidade <= estoque_minimo:
                status = 'baixo'
                status_class = 'warning'
                status_text = 'Estoque Baixo'
            else:
                status = 'normal'
                status_class = 'success'
                status_text = 'Normal'
            
            # Verificar validade
            validade_class = ''
            validade_text = ''
            if p[8]:
                if isinstance(p[8], str):
                    data_validade = datetime.strptime(p[8], '%Y-%m-%d').date()
                else:
                    data_validade = p[8].date() if hasattr(p[8], 'date') else p[8]
                
                hoje = datetime.now().date()
                if data_validade < hoje:
                    validade_class = 'danger'
                    validade_text = 'Vencido'
                elif (data_validade - hoje).days <= 30:
                    validade_class = 'warning'
                    validade_text = 'Proximo Vencimento'
                else:
                    validade_class = 'success'
                    validade_text = 'Valido'
            
            produtos.append({
                'id': p[0],
                'nome': p[1] if not isinstance(p[1], bytes) else p[1].decode('utf-8', errors='ignore'),
                'descricao': p[2] if not isinstance(p[2], bytes) else p[2].decode('utf-8', errors='ignore'),
                'categoria': p[3] if not isinstance(p[3], bytes) else p[3].decode('utf-8', errors='ignore'),
                'quantidade': quantidade,
                'unidade': p[5] if not isinstance(p[5], bytes) else p[5].decode('utf-8', errors='ignore'),
                'estoque_minimo': estoque_minimo,
                'lote': p[7] if not isinstance(p[7], bytes) else p[7].decode('utf-8', errors='ignore'),
                'data_validade': p[8],
                'fornecedor_id': p[9],
                'preco_custo': p[10],
                'preco_venda': p[11],
                'localizacao': p[12] if not isinstance(p[12], bytes) else p[12].decode('utf-8', errors='ignore'),
                'status': status,
                'status_class': status_class,
                'status_text': status_text,
                'validade_class': validade_class,
                'validade_text': validade_text
            })
        
        # Estatisticas do estoque
        stats = {
            'total_produtos': len(produtos),
            'estoque_baixo': len([p for p in produtos if p['status'] == 'baixo']),
            'esgotados': len([p for p in produtos if p['status'] == 'esgotado']),
            'total_unidades': total_unidades
        }
        
        return render_template('farmaceutico/estoque.html',
                             produtos=produtos,
                             stats=stats,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro no estoque: {e}")
        print(f"ERRO em estoque: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar estoque.', 'danger')
        return redirect(url_for('farmaceutico.dashboard'))


@farmaceutico_bp.route('/estoque/entrada', methods=['GET', 'POST'])
def entrada_estoque():
    """Registrar entrada de produto no estoque"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            descricao = request.form.get('descricao')
            categoria = request.form.get('categoria')
            quantidade = request.form.get('quantidade', 0, type=int)
            unidade = request.form.get('unidade')
            estoque_minimo = request.form.get('estoque_minimo', 10, type=int)
            lote = request.form.get('lote')
            data_validade = request.form.get('data_validade')
            fornecedor_id = request.form.get('fornecedor_id')
            preco_custo = request.form.get('preco_custo', 0, type=float)
            preco_venda = request.form.get('preco_venda', 0, type=float)
            localizacao = request.form.get('localizacao')
            
            if not nome:
                flash('Nome do produto e obrigatorio.', 'danger')
                return redirect(url_for('farmaceutico.entrada_estoque'))
            
            if quantidade <= 0:
                flash('Quantidade deve ser maior que zero.', 'danger')
                return redirect(url_for('farmaceutico.entrada_estoque'))
            
            # Verificar se produto ja existe
            produto_existente = execute_query_auth("""
                SELECT id, quantidade FROM produtos WHERE nome = %s
            """, (nome,), True)
            
            if produto_existente:
                produto_id = produto_existente[0][0]
                nova_quantidade = produto_existente[0][1] + quantidade
                execute_query_auth("""
                    UPDATE produtos 
                    SET quantidade = %s, updated_at = NOW()
                    WHERE id = %s
                """, (nova_quantidade, produto_id))
                flash(f'Produto "{nome}" atualizado! Nova quantidade: {nova_quantidade}', 'success')
            else:
                execute_query_auth("""
                    INSERT INTO produtos 
                    (nome, descricao, categoria, quantidade, unidade, 
                     estoque_minimo, lote, data_validade, fornecedor_id,
                     preco_custo, preco_venda, localizacao, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (nome, descricao, categoria, quantidade, unidade,
                      estoque_minimo, lote, data_validade, fornecedor_id,
                      preco_custo, preco_venda, localizacao))
                flash(f'Produto "{nome}" adicionado com sucesso!', 'success')
            
            return redirect(url_for('farmaceutico.estoque'))
            
        except Exception as e:
            logger.error(f"Erro ao registrar entrada: {e}")
            print(f"ERRO: {e}")
            flash('Erro ao registrar entrada.', 'danger')
            return redirect(url_for('farmaceutico.entrada_estoque'))
    
    # GET - mostrar formulario
    try:
        fornecedores_raw = execute_query_auth("""
            SELECT id, nome FROM fornecedores ORDER BY nome
        """, fetch=True) or []
        
        fornecedores = []
        for f in fornecedores_raw:
            fornecedores.append({
                'id': f[0],
                'nome': f[1] if not isinstance(f[1], bytes) else f[1].decode('utf-8', errors='ignore')
            })
        
        return render_template('farmaceutico/novo_produto.html',
                             fornecedores=fornecedores,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro ao carregar formulario: {e}")
        flash('Erro ao carregar formulario.', 'danger')
        return redirect(url_for('farmaceutico.estoque'))


@farmaceutico_bp.route('/estoque/baixar/<int:id>', methods=['POST'])
def baixar_estoque(id):
    """Baixar quantidade do estoque"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        quantidade = request.form.get('quantidade', 0, type=int)
        
        if quantidade <= 0:
            flash('Quantidade invalida.', 'danger')
            return redirect(url_for('farmaceutico.estoque'))
        
        produto = execute_query_auth("""
            SELECT id, quantidade FROM produtos WHERE id = %s
        """, (id,), True)
        
        if not produto:
            flash('Produto nao encontrado.', 'danger')
            return redirect(url_for('farmaceutico.estoque'))
        
        quantidade_atual = produto[0][1]
        
        if quantidade > quantidade_atual:
            flash(f'Quantidade insuficiente. Disponivel: {quantidade_atual}', 'danger')
            return redirect(url_for('farmaceutico.estoque'))
        
        execute_query_auth("""
            UPDATE produtos 
            SET quantidade = quantidade - %s, updated_at = NOW()
            WHERE id = %s
        """, (quantidade, id))
        
        flash('Baixa realizada com sucesso!', 'success')
        return redirect(url_for('farmaceutico.estoque'))
    
    except Exception as e:
        logger.error(f"Erro ao baixar estoque: {e}")
        flash('Erro ao baixar estoque.', 'danger')
        return redirect(url_for('farmaceutico.estoque'))


@farmaceutico_bp.route('/estoque/repor/<int:id>', methods=['POST'])
def repor_estoque(id):
    """Repor quantidade no estoque"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        quantidade = request.form.get('quantidade', 0, type=int)
        
        if quantidade <= 0:
            flash('Quantidade invalida.', 'danger')
            return redirect(url_for('farmaceutico.estoque'))
        
        execute_query_auth("""
            UPDATE produtos 
            SET quantidade = quantidade + %s, updated_at = NOW()
            WHERE id = %s
        """, (quantidade, id))
        
        flash('Estoque reposto com sucesso!', 'success')
        return redirect(url_for('farmaceutico.estoque'))
    
    except Exception as e:
        logger.error(f"Erro ao repor estoque: {e}")
        flash('Erro ao repor estoque.', 'danger')
        return redirect(url_for('farmaceutico.estoque'))


@farmaceutico_bp.route('/api/produto/<int:id>')
def api_produto_detalhe(id):
    """API para obter detalhes do produto"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        return jsonify({'error': 'Acesso negado'}), 403
    
    try:
        produto_raw = execute_query_auth("""
            SELECT id, nome, descricao, categoria, quantidade, unidade,
                   estoque_minimo, lote, data_validade, fornecedor_id,
                   preco_custo, preco_venda, localizacao
            FROM produtos WHERE id = %s
        """, (id,), True)
        
        if not produto_raw:
            return jsonify({'error': 'Produto nao encontrado'}), 404
        
        p = produto_raw[0]
        produto = {
            'id': p[0],
            'nome': p[1] if not isinstance(p[1], bytes) else p[1].decode('utf-8', errors='ignore'),
            'descricao': p[2] if not isinstance(p[2], bytes) else p[2].decode('utf-8', errors='ignore'),
            'categoria': p[3] if not isinstance(p[3], bytes) else p[3].decode('utf-8', errors='ignore'),
            'quantidade': p[4],
            'unidade': p[5] if not isinstance(p[5], bytes) else p[5].decode('utf-8', errors='ignore'),
            'estoque_minimo': p[6],
            'lote': p[7] if not isinstance(p[7], bytes) else p[7].decode('utf-8', errors='ignore'),
            'data_validade': p[8].strftime('%d/%m/%Y') if p[8] else None,
            'fornecedor_id': p[9],
            'preco_custo': float(p[10]) if p[10] else 0,
            'preco_venda': float(p[11]) if p[11] else 0,
            'localizacao': p[12] if not isinstance(p[12], bytes) else p[12].decode('utf-8', errors='ignore')
        }
        
        return jsonify(produto)
    
    except Exception as e:
        print(f"ERRO na API: {e}")
        return jsonify({'error': str(e)}), 500