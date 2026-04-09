from flask import render_template, session, redirect, url_for, flash, request
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging

logger = logging.getLogger(__name__)


@farmaceutico_bp.route('/produtos')
def produtos():
    """Catálogo de produtos/medicamentos"""
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
        for p in produtos_raw:
            produtos.append({
                'id': p[0],
                'nome': p[1] if not isinstance(p[1], bytes) else p[1].decode('utf-8', errors='ignore'),
                'descricao': p[2] if not isinstance(p[2], bytes) else p[2].decode('utf-8', errors='ignore'),
                'categoria': p[3] if not isinstance(p[3], bytes) else p[3].decode('utf-8', errors='ignore'),
                'quantidade': p[4] if p[4] else 0,
                'unidade': p[5] if not isinstance(p[5], bytes) else p[5].decode('utf-8', errors='ignore'),
                'estoque_minimo': p[6] if p[6] else 0,
                'lote': p[7] if not isinstance(p[7], bytes) else p[7].decode('utf-8', errors='ignore'),
                'data_validade': p[8],
                'fornecedor_id': p[9],
                'preco_custo': p[10],
                'preco_venda': p[11],
                'localizacao': p[12] if not isinstance(p[12], bytes) else p[12].decode('utf-8', errors='ignore')
            })
        
        return render_template('farmaceutico/produtos.html',
                             produtos=produtos,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro ao listar produtos: {e}")
        print(f"ERRO em produtos: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar produtos.', 'danger')
        return redirect(url_for('farmaceutico.dashboard'))


@farmaceutico_bp.route('/produtos/novo', methods=['GET', 'POST'])
def novo_produto():
    """Adicionar novo produto ao catálogo"""
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
                flash('Nome do produto é obrigatório.', 'danger')
                return redirect(url_for('farmaceutico.novo_produto'))
            
            # Verificar se produto já existe
            produto_existente = execute_query_auth("""
                SELECT id FROM produtos WHERE nome = %s
            """, (nome,), True)
            
            if produto_existente:
                flash('Produto já existe! Use a opção "Nova Entrada" para adicionar mais unidades.', 'warning')
                return redirect(url_for('farmaceutico.entrada_estoque'))
            
            # Inserir novo produto
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
            return redirect(url_for('farmaceutico.produtos'))
            
        except Exception as e:
            logger.error(f"Erro ao adicionar produto: {e}")
            print(f"ERRO: {e}")
            flash('Erro ao adicionar produto.', 'danger')
            return redirect(url_for('farmaceutico.novo_produto'))
    
    # GET - mostrar formulario
    try:
        # Buscar fornecedores
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
        return redirect(url_for('farmaceutico.produtos'))


@farmaceutico_bp.route('/produtos/editar/<int:id>', methods=['GET', 'POST'])
def editar_produto_catalogo(id):
    """Editar produto do catálogo"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            descricao = request.form.get('descricao')
            categoria = request.form.get('categoria')
            unidade = request.form.get('unidade')
            estoque_minimo = request.form.get('estoque_minimo', 0, type=int)
            localizacao = request.form.get('localizacao')
            fornecedor_id = request.form.get('fornecedor_id')
            preco_custo = request.form.get('preco_custo', 0, type=float)
            preco_venda = request.form.get('preco_venda', 0, type=float)
            lote = request.form.get('lote')
            data_validade = request.form.get('data_validade')
            
            execute_query_auth("""
                UPDATE produtos 
                SET nome=%s, descricao=%s, categoria=%s, unidade=%s,
                    estoque_minimo=%s, localizacao=%s, fornecedor_id=%s,
                    preco_custo=%s, preco_venda=%s, lote=%s, data_validade=%s,
                    updated_at=NOW()
                WHERE id=%s
            """, (nome, descricao, categoria, unidade, estoque_minimo,
                  localizacao, fornecedor_id, preco_custo, preco_venda,
                  lote, data_validade, id))
            
            flash('Produto atualizado com sucesso!', 'success')
            return redirect(url_for('farmaceutico.produtos'))
            
        except Exception as e:
            logger.error(f"Erro ao editar produto: {e}")
            flash('Erro ao editar produto.', 'danger')
            return redirect(url_for('farmaceutico.produtos'))
    
    # GET - mostrar formulario
    try:
        produto_raw = execute_query_auth("""
            SELECT id, nome, descricao, categoria, unidade, estoque_minimo,
                   localizacao, fornecedor_id, preco_custo, preco_venda,
                   lote, data_validade
            FROM produtos WHERE id = %s
        """, (id,), True)
        
        if not produto_raw:
            flash('Produto nao encontrado.', 'danger')
            return redirect(url_for('farmaceutico.produtos'))
        
        p = produto_raw[0]
        produto = {
            'id': p[0],
            'nome': p[1] if not isinstance(p[1], bytes) else p[1].decode('utf-8', errors='ignore'),
            'descricao': p[2] if not isinstance(p[2], bytes) else p[2].decode('utf-8', errors='ignore'),
            'categoria': p[3] if not isinstance(p[3], bytes) else p[3].decode('utf-8', errors='ignore'),
            'unidade': p[4] if not isinstance(p[4], bytes) else p[4].decode('utf-8', errors='ignore'),
            'estoque_minimo': p[5],
            'localizacao': p[6] if not isinstance(p[6], bytes) else p[6].decode('utf-8', errors='ignore'),
            'fornecedor_id': p[7],
            'preco_custo': p[8],
            'preco_venda': p[9],
            'lote': p[10] if not isinstance(p[10], bytes) else p[10].decode('utf-8', errors='ignore'),
            'data_validade': p[11]
        }
        
        # Buscar fornecedores
        fornecedores_raw = execute_query_auth("""
            SELECT id, nome FROM fornecedores ORDER BY nome
        """, fetch=True) or []
        
        fornecedores = []
        for f in fornecedores_raw:
            fornecedores.append({
                'id': f[0],
                'nome': f[1] if not isinstance(f[1], bytes) else f[1].decode('utf-8', errors='ignore')
            })
        
        return render_template('farmaceutico/editar_produto.html',
                             produto=produto,
                             fornecedores=fornecedores,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro ao carregar produto: {e}")
        flash('Erro ao carregar produto.', 'danger')
        return redirect(url_for('farmaceutico.produtos'))


@farmaceutico_bp.route('/produtos/deletar/<int:id>', methods=['POST'])
def deletar_produto(id):
    """Deletar produto do catálogo"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        execute_query_auth("DELETE FROM produtos WHERE id = %s", (id,))
        flash('Produto deletado com sucesso!', 'success')
        
    except Exception as e:
        logger.error(f"Erro ao deletar produto: {e}")
        flash('Erro ao deletar produto.', 'danger')
    
    return redirect(url_for('farmaceutico.produtos'))