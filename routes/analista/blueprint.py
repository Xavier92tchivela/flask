# routes/analista/blueprint.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import logging
from datetime import datetime
import mysql.connector
import os
import traceback

logger = logging.getLogger(__name__)

# Função auxiliar para conexão com banco
def get_db_connection():
    """Conexão com o banco de dados"""
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'root'),
        database=os.getenv('DB_NAME', 'sistema_medico'),
        charset='utf8mb4',
        use_unicode=True
    )

def init_analista(mysql, client, gemini_available, MODEL_NAME, app):
    """Inicializa e configura o blueprint do analista"""
    
    print("\n" + "=" * 50)
    print("INICIALIZANDO BLUEPRINT DO ANALISTA")
    print("=" * 50)
    
    # Importações dentro da função para evitar importação circular
    from .decorators import analista_required
    from .database import set_mysql, execute_query
    from .helpers import formatar_data, calcular_idade
    from .gemini_service import set_gemini_config, analisar_imagem_com_gemini, salvar_imagem_temporaria, preparar_contexto_clinico
    from .notifications import set_notification_deps, criar_notificacao_medico, salvar_diagnostico_ia, criar_notificacao_analise_manual
    from .file_utils import set_app_config
    
    # Configurar dependências
    set_mysql(mysql)
    set_gemini_config(gemini_available, MODEL_NAME, app)
    set_notification_deps(execute_query, logger)
    set_app_config(app)
    
    print("Dependências configuradas")
    
    # Importar rotas (dentro da função também)
    from .routes.dashboard import register_dashboard_routes
    from .routes.pedidos import register_pedidos_routes
    from .routes.analise import register_analise_routes
    from .routes.historico import register_historico_routes
    from .routes.perfil import register_perfil_routes
    
    # Criar blueprint
    analista_bp = Blueprint('analista', __name__, url_prefix='/analista')
    print("Blueprint criado")
    
    # Registrar rotas
    print("\nRegistrando rotas:")
    
    register_dashboard_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Dashboard routes registradas")
    
    register_pedidos_routes(analista_bp, analista_required, execute_query, formatar_data, calcular_idade)
    print("  - Pedidos routes registradas")
    
    register_analise_routes(analista_bp, analista_required, execute_query, formatar_data, calcular_idade,
                           analisar_imagem_com_gemini, salvar_imagem_temporaria, preparar_contexto_clinico,
                           criar_notificacao_medico, salvar_diagnostico_ia, gemini_available, MODEL_NAME)
    print("  - Analise routes registradas")
    
    register_historico_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Historico routes registradas")
    
    register_perfil_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Perfil routes registradas")
    
    # ============ ROTAS ADICIONAIS DE ANÁLISE MANUAL ============
    print("\nRegistrando rotas de análise manual:")
    
    @analista_bp.route('/analise_manual/<int:pedido_id>')
    @analista_required
    def analise_manual(pedido_id):
        """Página de análise manual"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            print(f"[INFO] Buscando pedido ID: {pedido_id}")
            
            # CORRIGIDO: Buscar dados do pedido com JOIN correto
            cursor.execute("""
                SELECT 
                    p.*,
                    u_paciente.nome as paciente_nome,
                    u_paciente.email as paciente_email,
                    u_paciente.telefone as paciente_telefone,
                    u_medico.id as medico_usuario_id,
                    u_medico.nome as medico_nome,
                    u_medico.email as medico_email
                FROM pedidos_analise p
                LEFT JOIN usuarios u_paciente ON p.paciente_id = u_paciente.id
                LEFT JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN usuarios u_medico ON m.usuario_id = u_medico.id
                WHERE p.id = %s
            """, (pedido_id,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash(f'Pedido #{pedido_id} não encontrado!', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            print(f"[OK] Pedido encontrado: #{pedido.get('id')} - Paciente: {pedido.get('paciente_nome')}")
            
            # Buscar anexos
            anexos_pedido = []
            try:
                cursor.execute("""
                    SELECT filename, original_name, type, size, upload_date
                    FROM anexos_pedido
                    WHERE pedido_id = %s
                """, (pedido_id,))
                anexos_pedido = cursor.fetchall()
                print(f"[INFO] Anexos encontrados: {len(anexos_pedido)}")
            except Exception as e:
                print(f"[WARN] Erro ao buscar anexos: {e}")
            
            # Buscar diagnóstico existente
            dados = {}
            try:
                if pedido.get('consulta_id'):
                    cursor.execute("""
                        SELECT tipo_exame, descricao, resultado, diagnostico_preliminar, 
                               diagnostico_final, observacoes, status
                        FROM diagnostico
                        WHERE consulta_id = %s
                    """, (pedido['consulta_id'],))
                    
                    dados_salvos = cursor.fetchone()
                    if dados_salvos:
                        dados = {
                            'tipo_exame': dados_salvos.get('tipo_exame'),
                            'descricao': dados_salvos.get('descricao'),
                            'resultado': dados_salvos.get('resultado'),
                            'diagnostico_preliminar': dados_salvos.get('diagnostico_preliminar'),
                            'diagnostico_final': dados_salvos.get('diagnostico_final'),
                            'observacoes': dados_salvos.get('observacoes'),
                            'status': dados_salvos.get('status')
                        }
                        print(f"[INFO] Diagnóstico encontrado para pedido #{pedido_id}")
            except Exception as e:
                print(f"[WARN] Erro ao buscar diagnóstico: {e}")
            
            return render_template('analista/analise_manual.html',
                                 pedido=pedido,
                                 anexos_pedido=anexos_pedido,
                                 dados=dados)
                                 
        except Exception as e:
            logger.error(f"[ERROR] Erro ao carregar análise manual: {str(e)}")
            print(f"[ERROR] ERRO DETALHADO: {str(e)}")
            flash(f'Erro ao carregar análise manual: {str(e)}', 'danger')
            return redirect(url_for('analista.pedidos'))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @analista_bp.route('/salvar_analise_manual/<int:pedido_id>', methods=['POST'])
    @analista_required
    def salvar_analise_manual(pedido_id):
        """Salvar análise manual e criar notificação para o médico"""
        conn = None
        cursor = None
        try:
            # Pegar dados do formulário
            consulta_id = request.form.get('consulta_id')
            tipo_exame = request.form.get('tipo_exame', '').strip()
            descricao = request.form.get('descricao', '').strip()
            resultado = request.form.get('resultado', '').strip()
            diagnostico_preliminar = request.form.get('diagnostico_preliminar', '').strip()
            diagnostico_final = request.form.get('diagnostico_final', '').strip()
            observacoes = request.form.get('observacoes', '').strip()
            status = request.form.get('status', 'concluido')
            
            print(f"[INFO] Salvando análise manual para pedido #{pedido_id}")
            print(f"   - Tipo Exame: {tipo_exame}")
            print(f"   - Diagnóstico Final: {diagnostico_final[:100]}..." if len(diagnostico_final) > 100 else f"   - Diagnóstico Final: {diagnostico_final}")
            print(f"   - Status: {status}")
            
            if not resultado or not diagnostico_final:
                flash('Resultado e diagnóstico final são obrigatórios!', 'warning')
                return redirect(url_for('analista.analise_manual', pedido_id=pedido_id))
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # CORRIGIDO: Buscar o pedido para obter informações com JOIN correto
            cursor.execute("""
                SELECT 
                    p.*,
                    u_paciente.nome as paciente_nome,
                    u_paciente.email as paciente_email,
                    u_medico.id as medico_usuario_id,
                    u_medico.nome as medico_nome
                FROM pedidos_analise p
                LEFT JOIN usuarios u_paciente ON p.paciente_id = u_paciente.id
                LEFT JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN usuarios u_medico ON m.usuario_id = u_medico.id
                WHERE p.id = %s
            """, (pedido_id,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido não encontrado!', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            consulta_id = pedido.get('consulta_id')
            medico_usuario_id = pedido.get('medico_usuario_id')
            medico_nome = pedido.get('medico_nome', 'Médico')
            paciente_nome = pedido.get('paciente_nome', 'Paciente')
            
            print(f"[INFO] Pedido #{pedido_id}:")
            print(f"   - Consulta ID: {consulta_id}")
            print(f"   - Médico ID: {medico_usuario_id}")
            print(f"   - Médico Nome: {medico_nome}")
            print(f"   - Paciente: {paciente_nome}")
            
            if not consulta_id:
                flash('Este pedido não está associado a uma consulta. Não é possível salvar o diagnóstico.', 'danger')
                return redirect(url_for('analista.analise_manual', pedido_id=pedido_id))
            
            # Verificar se já existe diagnóstico para esta consulta
            cursor.execute("SELECT id FROM diagnostico WHERE consulta_id = %s", (consulta_id,))
            diagnostico_existente = cursor.fetchone()
            
            if diagnostico_existente:
                # Atualizar diagnóstico existente
                cursor.execute("""
                    UPDATE diagnostico 
                    SET tipo_exame = %s,
                        descricao = %s,
                        resultado = %s,
                        diagnostico_preliminar = %s,
                        diagnostico_final = %s,
                        observacoes = %s,
                        status = 'concluido',
                        atualizado_em = NOW()
                    WHERE consulta_id = %s
                """, (tipo_exame, descricao, resultado, diagnostico_preliminar, 
                      diagnostico_final, observacoes, consulta_id))
                print(f"[OK] Diagnóstico ATUALIZADO para consulta #{consulta_id}")
            else:
                # Inserir novo diagnóstico
                cursor.execute("""
                    INSERT INTO diagnostico 
                    (consulta_id, tipo_exame, descricao, resultado, diagnostico_preliminar, 
                     diagnostico_final, observacoes, status, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'concluido', NOW(), NOW())
                """, (consulta_id, tipo_exame, descricao, resultado, diagnostico_preliminar,
                      diagnostico_final, observacoes))
                print(f"[OK] Novo diagnóstico CRIADO para consulta #{consulta_id}")
            
            # Montar resultado completo
            resultado_completo = f"""
📋 RELATÓRIO DE ANÁLISE MANUAL

DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}
ANALISTA: {session.get('user_name', 'Analista')}
PEDIDO: #{pedido_id}
PACIENTE: {paciente_nome}
EXAME: {tipo_exame}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ACHADOS PRINCIPAIS:
{resultado}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DIAGNÓSTICO FINAL:
{diagnostico_final}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBSERVAÇÕES ADICIONAIS:
{observacoes if observacoes else 'Nenhuma observação adicional'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Assinado por: {session.get('user_name', 'Analista')}
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
"""
            
            # Atualizar o pedido_analise com status CONCLUÍDO
            cursor.execute("""
                UPDATE pedidos_analise 
                SET status = 'concluido',
                    analista_id = %s,
                    resultado_analise = %s,
                    diagnostico_analista = %s,
                    recomendacoes_analista = %s,
                    data_conclusao = NOW(),
                    atualizado_em = NOW()
                WHERE id = %s
            """, (session.get('user_id'), resultado_completo, diagnostico_final, observacoes, pedido_id))
            
            conn.commit()
            print(f"[OK] Pedido #{pedido_id} atualizado para status 'concluido'")
            
            # ========== CRIAR NOTIFICAÇÃO PARA O MÉDICO ==========
            if medico_usuario_id:
                notificacao_criada = criar_notificacao_analise_manual(
                    medico_id=medico_usuario_id,
                    pedido_id=pedido_id,
                    consulta_id=consulta_id,
                    tipo_exame=tipo_exame,
                    diagnostico_final=diagnostico_final,
                    paciente_nome=paciente_nome
                )
                
                if notificacao_criada:
                    print(f"[OK]  Notificação criada para médico #{medico_usuario_id} ({medico_nome})")
                    flash(f' Análise salva e médico {medico_nome} foi notificado!', 'success')
                else:
                    print(f"[WARN]  Falha ao criar notificação para médico #{medico_usuario_id}")
                    flash(' Análise salva, mas houve falha ao notificar o médico.', 'warning')
            else:
                print(f"[WARN]  Médico não encontrado para o pedido #{pedido_id}")
                flash(' Análise salva, mas não foi possível notificar o médico.', 'warning')
            
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"[ERROR] Erro ao salvar análise manual: {str(e)}")
            print(f"[ERROR] ERRO DETALHADO: {str(e)}")
            print(traceback.format_exc())
            flash(f'Erro ao salvar análise manual: {str(e)}', 'danger')
            if conn:
                conn.rollback()
            return redirect(url_for('analista.analise_manual', pedido_id=pedido_id))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    print("  - Analise manual routes registradas com NOTIFICAÇÕES")
    print("  - Rotas adicionais registradas com sucesso!")
    
    print("\n" + "=" * 50)
    print("BLUEPRINT DO ANALISTA INICIALIZADO COM SUCESSO!")
    print("=" * 50 + "\n")
    
    return analista_bp