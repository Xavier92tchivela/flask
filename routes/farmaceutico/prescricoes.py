from flask import render_template, session, redirect, url_for, flash, request, send_file, abort
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging
from datetime import datetime
import os
import sys
import traceback
import glob

# ================= CONFIGURAÇÕES =================
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger(__name__)

# Configuração de diretórios - MÚLTIPLAS OPÇÕES
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

# Lista de TODOS os possíveis diretórios onde PDFs podem estar
POSSIBLE_PDF_DIRS = [
    os.path.join(BASE_DIR, 'uploads', 'receitas'),
    os.path.join(BASE_DIR, 'static', 'pdfs'),
    os.path.join(BASE_DIR, 'static', 'uploads', 'receitas'),
    os.path.join(BASE_DIR, 'media', 'receitas'),
    os.path.join(BASE_DIR, 'receitas_pdf'),
    os.path.join(BASE_DIR, 'temp', 'receitas'),
    os.path.join(BASE_DIR, 'downloads', 'receitas'),
    os.path.join(BASE_DIR, 'pdfs'),
    # Caminhos absolutos comuns
    r'c:\Users\dell\Videos\DOCTORIAv10\uploads\receitas',
    r'c:\Users\dell\Videos\DOCTORIAv10\static\pdfs',
]

# Criar diretórios principais
UPLOAD_FOLDER = POSSIBLE_PDF_DIRS[0]
STATIC_PDF_FOLDER = POSSIBLE_PDF_DIRS[1]

for pasta in [UPLOAD_FOLDER, STATIC_PDF_FOLDER]:
    os.makedirs(pasta, exist_ok=True)

# ================= UTILITÁRIOS =================
def safe_decode(value):
    """Decodifica bytes para string de forma segura"""
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')
    return str(value)


def buscar_pdf_em_todo_sistema(receita_id, nome_arquivo_sugerido=None):
    """
    Busca o arquivo PDF em TODO o sistema de arquivos
    
    Args:
        receita_id: ID da receita
        nome_arquivo_sugerido: Nome sugerido do arquivo
    
    Returns:
        tuple: (caminho_do_arquivo, mensagem_erro)
    """
    print(f"\n🔍 BUSCA INTENSIVA por PDF da receita #{receita_id}")
    
    todos_encontrados = []
    
    # 1. Buscar por padrões de nome em todos os diretórios possíveis
    padroes_busca = [
        f'receita_{receita_id}.pdf',
        f'receita_{receita_id}_*.pdf',
        f'*{receita_id}*.pdf',
        f'receita_*{receita_id}*.pdf',
        f'Receita_{receita_id}.pdf',
        f'RECEITA_{receita_id}.pdf',
    ]
    
    if nome_arquivo_sugerido:
        padroes_busca.insert(0, nome_arquivo_sugerido)
    
    # Buscar em todos os diretórios possíveis
    for pasta in POSSIBLE_PDF_DIRS:
        if not os.path.exists(pasta):
            continue
            
        print(f"  Buscando em: {pasta}")
        
        for padrao in padroes_busca:
            # Busca exata
            caminho_exato = os.path.join(pasta, padrao)
            if os.path.exists(caminho_exato):
                print(f"    ✓ Encontrado (exato): {caminho_exato}")
                todos_encontrados.append(caminho_exato)
            
            # Busca com glob
            arquivos = glob.glob(os.path.join(pasta, padrao))
            for arquivo in arquivos:
                if os.path.exists(arquivo) and arquivo not in todos_encontrados:
                    print(f"    ✓ Encontrado (glob): {arquivo}")
                    todos_encontrados.append(arquivo)
    
    # 2. Busca recursiva em toda a pasta DOCTORIAv10
    print(f"\n  Busca recursiva em: {BASE_DIR}")
    for root, dirs, files in os.walk(BASE_DIR):
        # Limitar profundidade para não demorar muito
        if root.count(os.sep) - BASE_DIR.count(os.sep) > 5:
            continue
            
        for file in files:
            if file.lower().endswith('.pdf') and str(receita_id) in file:
                caminho_completo = os.path.join(root, file)
                if caminho_completo not in todos_encontrados:
                    print(f"    ✓ Encontrado (recursivo): {caminho_completo}")
                    todos_encontrados.append(caminho_completo)
    
    # 3. Se encontrou arquivos, retorna o primeiro
    if todos_encontrados:
        print(f"\n  ✅ Total de {len(todos_encontrados)} arquivo(s) encontrado(s)")
        return todos_encontrados[0], None
    
    print(f"\n  ❌ NENHUM arquivo PDF encontrado para a receita #{receita_id}")
    return None, f"Arquivo PDF da receita #{receita_id} não encontrado em nenhum local do sistema"


def corrigir_caminho_pdf_no_banco(receita_id, novo_caminho):
    """Atualiza o caminho do PDF no banco de dados"""
    try:
        execute_query_auth("""
            UPDATE receita 
            SET receita_pdf_path = %s, pdf_gerado = 1
            WHERE id = %s
        """, (novo_caminho, receita_id))
        print(f"  ✓ Caminho do PDF atualizado no banco: {novo_caminho}")
        return True
    except Exception as e:
        print(f"  ✗ Erro ao atualizar banco: {e}")
        return False


def listar_todos_pdfs_sistema():
    """Lista todos os PDFs encontrados no sistema para diagnóstico"""
    print("\n" + "="*70)
    print("DIAGNÓSTICO COMPLETO - TODOS OS PDFs NO SISTEMA")
    print("="*70)
    
    todos_pdfs = []
    
    # Buscar em todos os diretórios
    for pasta in POSSIBLE_PDF_DIRS:
        if os.path.exists(pasta):
            print(f"\n📁 {pasta}")
            for arquivo in os.listdir(pasta):
                if arquivo.lower().endswith('.pdf'):
                    caminho = os.path.join(pasta, arquivo)
                    tamanho = os.path.getsize(caminho)
                    print(f"   📄 {arquivo} ({tamanho:,} bytes)")
                    todos_pdfs.append(caminho)
    
    # Busca recursiva
    print(f"\n📁 Busca recursiva em {BASE_DIR}:")
    for root, dirs, files in os.walk(BASE_DIR):
        if root.count(os.sep) - BASE_DIR.count(os.sep) > 3:
            continue
        for file in files:
            if file.lower().endswith('.pdf'):
                caminho = os.path.join(root, file)
                if caminho not in todos_pdfs:
                    tamanho = os.path.getsize(caminho)
                    print(f"   📄 {os.path.relpath(caminho, BASE_DIR)} ({tamanho:,} bytes)")
                    todos_pdfs.append(caminho)
    
    print(f"\n✅ Total de PDFs encontrados: {len(todos_pdfs)}")
    print("="*70)
    
    return todos_pdfs


# ================= ROTAS PRINCIPAIS =================

@farmaceutico_bp.route('/prescricoes')
def prescricoes():
    """Lista de prescrições (receitas)"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    status_filtro = request.args.get('status', 'todas')
    
    try:
        query = """
            SELECT r.id, 
                   r.created_at, 
                   r.status, 
                   r.diagnostico,
                   p.nome as paciente_nome,
                   m.nome as medico_nome,
                   r.receita_pdf_path, 
                   r.pdf_gerado
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN pacientes pac ON c.paciente_id = pac.id
            JOIN usuarios p ON pac.usuario_id = p.id
            JOIN medicos med ON c.medico_id = med.id
            JOIN usuarios m ON med.usuario_id = m.id
        """
        
        params = []
        if status_filtro != 'todas':
            query += " WHERE r.status = %s"
            params.append(status_filtro)
        
        query += " ORDER BY r.created_at DESC"
        
        resultados = execute_query_auth(query, params, fetch=True) or []
        
        prescricoes_lista = []
        for r in resultados:
            # Verificar se o PDF realmente existe
            pdf_path_db = safe_decode(r[6]) if r[6] else None
            pdf_existe = False
            
            if pdf_path_db and os.path.exists(pdf_path_db):
                pdf_existe = True
            elif r[7] == 1:
                # Tentar encontrar o PDF
                pdf_encontrado, _ = buscar_pdf_em_todo_sistema(r[0], pdf_path_db)
                if pdf_encontrado:
                    pdf_existe = True
                    # Atualizar caminho no banco
                    corrigir_caminho_pdf_no_banco(r[0], pdf_encontrado)
            
            prescricoes_lista.append({
                'id': r[0],
                'created_at': r[1],
                'status': safe_decode(r[2]),
                'diagnostico': safe_decode(r[3])[:150] + "..." if len(safe_decode(r[3])) > 150 else safe_decode(r[3]),
                'paciente_nome': safe_decode(r[4]),
                'medico_nome': safe_decode(r[5]),
                'pdf_existe': pdf_existe,
                'pdf_gerado': r[7] if len(r) > 7 else 0
            })
        
        stats = {
            'ativas': len([p for p in prescricoes_lista if p['status'] == 'ativa']),
            'dispensadas': len([p for p in prescricoes_lista if p['status'] == 'dispensada']),
            'expiradas': len([p for p in prescricoes_lista if p['status'] == 'expirada']),
            'total': len(prescricoes_lista)
        }
        
        return render_template('farmaceutico/prescricoes.html',
                             prescricoes=prescricoes_lista,
                             status_atual=status_filtro,
                             stats=stats,
                             nome_usuario=safe_decode(session.get('user_name')))
    
    except Exception as e:
        logger.error(f"Erro ao listar prescrições: {e}")
        traceback.print_exc()
        flash('Erro ao carregar prescrições.', 'danger')
        return redirect(url_for('farmaceutico.dashboard'))


@farmaceutico_bp.route('/visualizar-pdf/<int:receita_id>')
def visualizar_pdf(receita_id):
    """Visualizar PDF da receita - VERSÃO CORRIGIDA"""
    if not session.get('logged_in'):
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    print(f"\n{'='*60}")
    print(f"📄 VISUALIZAR PDF - Receita #{receita_id}")
    print(f"{'='*60}")
    
    try:
        # Buscar informações da receita
        result = execute_query_auth("""
            SELECT id, receita_pdf_path, pdf_gerado, status, created_at
            FROM receita 
            WHERE id = %s
        """, (receita_id,), fetch=True)
        
        if not result:
            flash('Receita não encontrada', 'danger')
            return redirect(url_for('farmaceutico.prescricoes'))
        
        r = result[0]
        pdf_path_db = safe_decode(r[1]) if r[1] else None
        pdf_gerado = r[2]
        status = safe_decode(r[3]) if len(r) > 3 else 'desconhecido'
        
        print(f"  ID: {receita_id}")
        print(f"  Status: {status}")
        print(f"  PDF Gerado (BD): {pdf_gerado}")
        print(f"  Path no BD: {pdf_path_db}")
        
        # Se o PDF não foi gerado no banco, não adianta procurar
        if not pdf_gerado or pdf_gerado == 0:
            flash('PDF ainda não foi gerado para esta receita.', 'warning')
            print(f"  ⚠️ PDF não gerado no banco de dados")
            return redirect(url_for('farmaceutico.prescricao_detalhe', id=receita_id))
        
        # BUSCA INTENSIVA DO PDF
        arquivo_pdf, erro = buscar_pdf_em_todo_sistema(receita_id, pdf_path_db)
        
        if arquivo_pdf and os.path.exists(arquivo_pdf):
            print(f"\n  ✅ PDF ENCONTRADO: {arquivo_pdf}")
            
            # Atualizar o caminho no banco de dados se necessário
            if pdf_path_db != arquivo_pdf:
                corrigir_caminho_pdf_no_banco(receita_id, arquivo_pdf)
            
            # Enviar o arquivo
            return send_file(
                arquivo_pdf,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=f'receita_{receita_id}.pdf'
            )
        
        # Se não encontrou, mostrar diagnóstico detalhado
        print(f"\n  ❌ {erro}")
        
        # Listar todos os PDFs do sistema para ajudar no diagnóstico
        print("\n  📋 Todos os PDFs encontrados no sistema:")
        listar_todos_pdfs_sistema()
        
        flash(f'❌ {erro}', 'danger')
        return redirect(url_for('farmaceutico.prescricao_detalhe', id=receita_id))
    
    except Exception as e:
        logger.error(f"Erro ao visualizar PDF: {e}")
        traceback.print_exc()
        flash(f'Erro ao visualizar o PDF: {str(e)}', 'danger')
        return redirect(url_for('farmaceutico.prescricao_detalhe', id=receita_id))


@farmaceutico_bp.route('/diagnosticar-pdfs')
def diagnosticar_pdfs():
    """Rota de diagnóstico - Lista todos os PDFs do sistema"""
    if not session.get('logged_in'):
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Executar diagnóstico completo
    todos_pdfs = listar_todos_pdfs_sistema()
    
    # Verificar receitas no banco
    receitas_com_pdf = execute_query_auth("""
        SELECT id, receita_pdf_path, pdf_gerado, status
        FROM receita 
        WHERE pdf_gerado = 1
        ORDER BY id DESC
    """, fetch=True) or []
    
    html = "<html><body style='font-family: monospace; padding: 20px;'>"
    html += "<h1>🔍 Diagnóstico de PDFs - DOCTORIA</h1>"
    
    html += f"<h2>📁 PDFs Encontrados no Sistema ({len(todos_pdfs)})</h2>"
    html += "<ul>"
    for pdf in todos_pdfs:
        if os.path.exists(pdf):
            tamanho = os.path.getsize(pdf)
            html += f"<li>📄 {pdf} ({tamanho:,} bytes)</li>"
    html += "</ul>"
    
    html += f"<h2>📊 Receitas com PDF no Banco ({len(receitas_com_pdf)})</h2>"
    html += "<table border='1' cellpadding='5' cellspacing='0'>"
    html += "<tr><th>ID</th><th>Status</th><th>Path no BD</th><th>PDF Existe?</th></tr>"
    
    for r in receitas_com_pdf:
        path = safe_decode(r[1]) if r[1] else "NULL"
        existe = os.path.exists(path) if path and path != "NULL" else False
        cor = "green" if existe else "red"
        html += f"<tr>"
        html += f"<td>{r[0]}</td>"
        html += f"<td>{safe_decode(r[3])}</td>"
        html += f"<td style='font-size: 12px;'>{path}</td>"
        html += f"<td style='color: {cor}; font-weight: bold;'>{'✅ SIM' if existe else '❌ NÃO'}</td>"
        html += "</tr>"
    
    html += "</table>"
    
    html += "<br><a href='/farmaceutico/prescricoes'>← Voltar para Prescrições</a>"
    html += "</body></html>"
    
    return html


@farmaceutico_bp.route('/prescricao/<int:id>')
def prescricao_detalhe(id):
    """Detalhes de uma prescrição específica"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        query = """
            SELECT r.id, 
                   r.created_at, 
                   r.status, 
                   r.diagnostico, 
                   r.prescricao, 
                   r.recomendacoes,
                   c.id as consulta_id, 
                   c.data_hora,
                   p.id as paciente_id, 
                   p.nome as paciente_nome, 
                   p.telefone, 
                   p.email,
                   m.id as medico_id, 
                   m.nome as medico_nome,
                   r.receita_pdf_path, 
                   r.pdf_gerado, 
                   r.data_geracao_pdf
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN pacientes pac ON c.paciente_id = pac.id
            JOIN usuarios p ON pac.usuario_id = p.id
            JOIN medicos med ON c.medico_id = med.id
            JOIN usuarios m ON med.usuario_id = m.id
            WHERE r.id = %s
        """
        
        resultado = execute_query_auth(query, (id,), fetch=True)
        
        if not resultado or len(resultado) == 0:
            flash('Receita não encontrada.', 'danger')
            return redirect(url_for('farmaceutico.prescricoes'))
        
        r = resultado[0]
        
        receita = {
            'id': r[0],
            'created_at': r[1],
            'status': safe_decode(r[2]),
            'diagnostico': safe_decode(r[3]),
            'prescricao': safe_decode(r[4]),
            'recomendacoes': safe_decode(r[5]),
            'consulta_id': r[6],
            'data_hora': r[7],
            'paciente_id': r[8],
            'paciente_nome': safe_decode(r[9]),
            'telefone': safe_decode(r[10]),
            'email': safe_decode(r[11]),
            'medico_id': r[12],
            'medico_nome': safe_decode(r[13]),
            'receita_pdf_path': safe_decode(r[14]) if r[14] else None,
            'pdf_gerado': r[15] if len(r) > 15 else 0,
            'data_geracao_pdf': r[16] if len(r) > 16 else None
        }
        
        return render_template('farmaceutico/prescricao_detalhe.html',
                             receita=receita,
                             nome_usuario=safe_decode(session.get('user_name')))
    
    except Exception as e:
        logger.error(f"Erro ao carregar detalhes da prescrição: {e}")
        traceback.print_exc()
        flash('Erro ao carregar detalhes da prescrição.', 'danger')
        return redirect(url_for('farmaceutico.prescricoes'))


@farmaceutico_bp.route('/dispensar/<int:receita_id>', methods=['GET', 'POST'])
def dispensar(receita_id):
    """Realizar dispensação de uma receita"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            execute_query_auth("""
                UPDATE receita 
                SET status = 'dispensada'
                WHERE id = %s AND status = 'ativa'
            """, (receita_id,))
            
            flash('✅ Dispensa realizada com sucesso!', 'success')
            return redirect(url_for('farmaceutico.prescricoes', status='ativas'))
            
        except Exception as e:
            logger.error(f"Erro ao dispensar: {e}")
            flash('Erro ao realizar dispensa.', 'danger')
            return redirect(url_for('farmaceutico.prescricoes'))
    
    # GET - mostrar confirmação
    try:
        resultado = execute_query_auth("""
            SELECT r.id, p.nome as paciente_nome, m.nome as medico_nome
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN pacientes pac ON c.paciente_id = pac.id
            JOIN usuarios p ON pac.usuario_id = p.id
            JOIN medicos med ON c.medico_id = med.id
            JOIN usuarios m ON med.usuario_id = m.id
            WHERE r.id = %s AND r.status = 'ativa'
        """, (receita_id,), fetch=True)
        
        if not resultado:
            flash('Receita não encontrada ou já dispensada.', 'danger')
            return redirect(url_for('farmaceutico.prescricoes'))
        
        r = resultado[0]
        return render_template('farmaceutico/dispensar.html',
                             receita={'id': r[0], 'paciente_nome': safe_decode(r[1]), 'medico_nome': safe_decode(r[2])},
                             nome_usuario=safe_decode(session.get('user_name')))
    
    except Exception as e:
        logger.error(f"Erro: {e}")
        flash('Erro ao carregar dispensação.', 'danger')
        return redirect(url_for('farmaceutico.prescricoes'))