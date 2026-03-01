"""Sistema de notificações para o módulo analista"""
import logging
import base64
import os
import traceback

logger = logging.getLogger(__name__)
_execute_query = None
_logger = None

def set_notification_deps(execute_query_func, logger_func):
    """Configura dependências das notificações"""
    global _execute_query, _logger
    _execute_query = execute_query_func
    _logger = logger_func

def criar_notificacao_medico(medico_id, pedido_id, titulo, mensagem, tipo='diagnostico'):
    """Cria notificação para o médico sobre novo diagnóstico"""
    try:
        if not _execute_query:
            logger.error("❌ Execute_query não configurado")
            return False
            
        result = _execute_query("""
            INSERT INTO notificacoes 
            (usuario_id, tipo, titulo, mensagem, referencia_id, lida, criado_em)
            VALUES (%s, %s, %s, %s, %s, FALSE, NOW())
        """, (
            medico_id,
            tipo,
            titulo,
            mensagem,
            pedido_id
        ), commit=True)
        
        if result:
            logger.info(f"🔔 Notificação criada para médico {medico_id} sobre pedido {pedido_id}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar notificação: {e}")
        return False

def salvar_diagnostico_ia(consulta_id, tipo_exame, descricao, observacoes, 
                         resultado, diagnostico_ia, status='pendente', 
                         imagem_path=None, imagem_base64=None, formato_imagem=None, tamanho_imagem=None):
    """Salva diagnóstico gerado pela IA na tabela diagnostico"""
    try:
        if not _execute_query:
            logger.error("❌ Execute_query não configurado")
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
                logger.info(f"📝 Diagnóstico atualizado para consulta {consulta_id}")
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
                logger.info(f"📝 Novo diagnóstico criado para consulta {consulta_id}")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar diagnóstico: {e}")
        logger.error(traceback.format_exc())
        return False