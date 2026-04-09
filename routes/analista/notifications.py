# routes/analista/notifications.py
"""Sistema de notificações para o módulo analista"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Variáveis globais
_execute_query = None
_logger = None

def set_notification_deps(execute_query_func, logger_func):
    """Configura dependências das notificações"""
    global _execute_query, _logger
    _execute_query = execute_query_func
    _logger = logger_func
    if _logger:
        _logger.info(" Dependências de notificações configuradas")
    print("[NOTIFICATIONS] Dependências configuradas")

def criar_notificacao_medico(medico_id, pedido_id, titulo, mensagem, tipo='diagnostico'):
    """Cria notificação para o médico"""
    try:
        if not _execute_query:
            print("[NOTIFICACAO]  Execute_query não configurado")
            return False
        
        print(f"[NOTIFICACAO] Criando notificação:")
        print(f"   - Médico ID: {medico_id}")
        print(f"   - Pedido ID: {pedido_id}")
        print(f"   - Tipo: {tipo}")
        print(f"   - Título: {titulo}")
        
        result = _execute_query("""
            INSERT INTO notificacoes 
            (usuario_id, tipo, titulo, mensagem, referencia_id, lida, criado_em)
            VALUES (%s, %s, %s, %s, %s, 0, NOW())
        """, (
            medico_id,
            tipo,
            titulo,
            mensagem,
            pedido_id
        ), commit=True)
        
        if result:
            print(f"[NOTIFICACAO]  Notificação criada com sucesso!")
            return True
        else:
            print(f"[NOTIFICACAO]  Falha ao criar notificação")
            return False
        
    except Exception as e:
        print(f"[NOTIFICACAO]  Erro: {e}")
        return False

def criar_notificacao_analise_manual(medico_id, pedido_id, consulta_id, tipo_exame, diagnostico_final, paciente_nome=None):
    """Cria notificação específica para análise manual concluída"""
    try:
        titulo = f" Análise Manual Concluída - {tipo_exame}"
        
        diagnostico_resumido = diagnostico_final[:150] if diagnostico_final else "Diagnóstico não informado"
        if diagnostico_final and len(diagnostico_final) > 150:
            diagnostico_resumido += '...'
        
        data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        mensagem = f"""Análise manual concluída!

Paciente: {paciente_nome or 'Não informado'}
Exame: {tipo_exame}
Data: {data_atual}

Diagnóstico: {diagnostico_resumido}

Clique para visualizar o resultado completo."""
        
        print(f"[NOTIFICACAO] ========================================")
        print(f"[NOTIFICACAO] CRIANDO NOTIFICAÇÃO DE ANÁLISE MANUAL")
        print(f"[NOTIFICACAO] Médico ID: {medico_id}")
        print(f"[NOTIFICACAO] Pedido ID: {pedido_id}")
        print(f"[NOTIFICACAO] Exame: {tipo_exame}")
        print(f"[NOTIFICACAO] ========================================")
        
        return criar_notificacao_medico(medico_id, pedido_id, titulo, mensagem, 'analise_manual')
        
    except Exception as e:
        print(f"[NOTIFICACAO]  Erro criar_notificacao_analise_manual: {e}")
        return False

def salvar_diagnostico_ia(consulta_id, tipo_exame, descricao, observacoes, 
                         resultado, diagnostico_ia, status='pendente', 
                         imagem_path=None, imagem_base64=None, formato_imagem=None, tamanho_imagem=None):
    """Salva diagnóstico gerado pela IA na tabela diagnostico"""
    try:
        if not _execute_query:
            print("[NOTIFICACAO] ❌ Execute_query não configurado")
            return False
            
        # Verificar se já existe diagnóstico
        existing_diagnostic = _execute_query("""
            SELECT id FROM diagnostico WHERE consulta_id = %s
        """, (consulta_id,), fetch=True, one=True)
        
        if existing_diagnostic:
            result = _execute_query("""
                UPDATE diagnostico 
                SET tipo_exame = %s,
                    descricao = %s,
                    observacoes = %s,
                    resultado = %s,
                    diagnostico_preliminar = %s,
                    status = %s,
                    imagem_path = %s,
                    imagem_base64 = %s,
                    formato_imagem = %s,
                    tamanho_imagem = %s,
                    atualizado_em = NOW()
                WHERE consulta_id = %s
            """, (
                tipo_exame, descricao, observacoes, resultado, diagnostico_ia,
                status, imagem_path, imagem_base64, formato_imagem, tamanho_imagem,
                consulta_id
            ), commit=True)
            
            if result is not None:
                print(f"[NOTIFICACAO] Diagnóstico atualizado para consulta {consulta_id}")
                return True
        else:
            result = _execute_query("""
                INSERT INTO diagnostico 
                (consulta_id, tipo_exame, descricao, observacoes, resultado, 
                 diagnostico_preliminar, status, imagem_path, imagem_base64, 
                 formato_imagem, tamanho_imagem, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                consulta_id, tipo_exame, descricao, observacoes, resultado,
                diagnostico_ia, status, imagem_path, imagem_base64,
                formato_imagem, tamanho_imagem
            ), commit=True)
            
            if result:
                print(f"[NOTIFICACAO] Novo diagnóstico criado para consulta {consulta_id}")
                return True
        
        return False
        
    except Exception as e:
        print(f"[NOTIFICACAO] ❌ Erro ao salvar diagnóstico: {e}")
        return False

# Exportar funções necessárias
__all__ = [
    'set_notification_deps',
    'criar_notificacao_medico',
    'criar_notificacao_analise_manual',
    'salvar_diagnostico_ia'
]