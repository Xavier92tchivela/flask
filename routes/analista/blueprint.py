# routes/analista/blueprint.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import logging
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

# FUNÇÃO AUXILIAR REMOVIDA - NÃO CRIAR NOVAS CONEXÕES!

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
        """Página de análise manual - USANDO CONEXÃO EXISTENTE"""
        try:
            print(f"[INFO] Buscando pedido ID: {pedido_id} para análise manual")
            
            # USAR execute_query EM VEZ DE CRIAR NOVA CONEXÃO
            pedido = execute_query("""
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
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                flash(f'Pedido #{pedido_id} não encontrado!', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            print(f"[OK] Pedido encontrado: #{pedido.get('id') if isinstance(pedido, dict) else pedido[0]} - Paciente: {pedido.get('paciente_nome') if isinstance(pedido, dict) else pedido[8] if len(pedido) > 8 else 'N/A'}")
            
            # Buscar anexos
            anexos_pedido = []
            try:
                anexos = execute_query("""
                    SELECT filename, original_name, tipo, size, upload_date
                    FROM anexos_pedidos
                    WHERE pedido_id = %s
                """, (pedido_id,), fetch=True)
                
                if anexos:
                    for a in anexos:
                        anexos_pedido.append({
                            'filename': a[0] if isinstance(a, (list, tuple)) else a.get('filename'),
                            'original_name': a[1] if isinstance(a, (list, tuple)) else a.get('original_name'),
                            'type': a[2] if isinstance(a, (list, tuple)) else a.get('tipo'),
                            'size': a[3] if isinstance(a, (list, tuple)) else a.get('size'),
                            'upload_date': a[4] if isinstance(a, (list, tuple)) else a.get('upload_date')
                        })
                    print(f"[INFO] Anexos encontrados: {len(anexos_pedido)}")
            except Exception as e:
                print(f"[WARN] Erro ao buscar anexos: {e}")
            
            # Buscar diagnóstico existente
            dados = {}
            consulta_id = pedido.get('consulta_id') if isinstance(pedido, dict) else pedido[12] if len(pedido) > 12 else None
            
            if consulta_id:
                try:
                    diagnostico = execute_query("""
                        SELECT tipo_exame, descricao, resultado, diagnostico_preliminar, 
                               diagnostico_final, observacoes, status
                        FROM diagnostico
                        WHERE consulta_id = %s
                    """, (consulta_id,), fetch=True, one=True)
                    
                    if diagnostico:
                        if isinstance(diagnostico, dict):
                            dados = {
                                'tipo_exame': diagnostico.get('tipo_exame'),
                                'descricao': diagnostico.get('descricao'),
                                'resultado': diagnostico.get('resultado'),
                                'diagnostico_preliminar': diagnostico.get('diagnostico_preliminar'),
                                'diagnostico_final': diagnostico.get('diagnostico_final'),
                                'observacoes': diagnostico.get('observacoes'),
                                'status': diagnostico.get('status')
                            }
                        else:
                            dados = {
                                'tipo_exame': diagnostico[0] if len(diagnostico) > 0 else None,
                                'descricao': diagnostico[1] if len(diagnostico) > 1 else None,
                                'resultado': diagnostico[2] if len(diagnostico) > 2 else None,
                                'diagnostico_preliminar': diagnostico[3] if len(diagnostico) > 3 else None,
                                'diagnostico_final': diagnostico[4] if len(diagnostico) > 4 else None,
                                'observacoes': diagnostico[5] if len(diagnostico) > 5 else None,
                                'status': diagnostico[6] if len(diagnostico) > 6 else None
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
            traceback.print_exc()
            flash(f'Erro ao carregar análise manual: {str(e)}', 'danger')
            return redirect(url_for('analista.pedidos'))

    @analista_bp.route('/salvar_analise_manual/<int:pedido_id>', methods=['POST'])
    @analista_required
    def salvar_analise_manual(pedido_id):
        """Salvar análise manual e criar notificação para o médico - USANDO CONEXÃO EXISTENTE"""
        try:
            # Pegar dados do formulário
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
            
            # Buscar o pedido
            pedido = execute_query("""
                SELECT 
                    p.id, p.consulta_id, p.paciente_id, p.medico_id,
                    u_paciente.nome as paciente_nome,
                    u_medico.id as medico_usuario_id,
                    u_medico.nome as medico_nome
                FROM pedidos_analise p
                LEFT JOIN usuarios u_paciente ON p.paciente_id = u_paciente.id
                LEFT JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN usuarios u_medico ON m.usuario_id = u_medico.id
                WHERE p.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                flash('Pedido não encontrado!', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            # Extrair dados
            if isinstance(pedido, dict):
                consulta_id = pedido.get('consulta_id')
                medico_usuario_id = pedido.get('medico_usuario_id')
                medico_nome = pedido.get('medico_nome', 'Médico')
                paciente_nome = pedido.get('paciente_nome', 'Paciente')
            else:
                consulta_id = pedido[1] if len(pedido) > 1 else None
                medico_usuario_id = pedido[5] if len(pedido) > 5 else None
                medico_nome = pedido[6] if len(pedido) > 6 else 'Médico'
                paciente_nome = pedido[4] if len(pedido) > 4 else 'Paciente'
            
            print(f"[INFO] Pedido #{pedido_id}:")
            print(f"   - Consulta ID: {consulta_id}")
            print(f"   - Médico ID: {medico_usuario_id}")
            print(f"   - Médico Nome: {medico_nome}")
            print(f"   - Paciente: {paciente_nome}")
            
            if not consulta_id:
                flash('Este pedido não está associado a uma consulta. Não é possível salvar o diagnóstico.', 'danger')
                return redirect(url_for('analista.analise_manual', pedido_id=pedido_id))
            
            # Verificar se já existe diagnóstico
            diagnostico_existente = execute_query("""
                SELECT id FROM diagnostico WHERE consulta_id = %s
            """, (consulta_id,), fetch=True, one=True)
            
            if diagnostico_existente:
                execute_query("""
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
                      diagnostico_final, observacoes, consulta_id), commit=True)
                print(f"[OK] Diagnóstico ATUALIZADO para consulta #{consulta_id}")
            else:
                execute_query("""
                    INSERT INTO diagnostico 
                    (consulta_id, tipo_exame, descricao, resultado, diagnostico_preliminar, 
                     diagnostico_final, observacoes, status, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'concluido', NOW(), NOW())
                """, (consulta_id, tipo_exame, descricao, resultado, diagnostico_preliminar,
                      diagnostico_final, observacoes), commit=True)
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
            
            # Atualizar pedido
            execute_query("""
                UPDATE pedidos_analise 
                SET status = 'concluido',
                    analista_id = %s,
                    resultado_analise = %s,
                    diagnostico_analista = %s,
                    recomendacoes_analista = %s,
                    data_conclusao = NOW(),
                    atualizado_em = NOW()
                WHERE id = %s
            """, (session.get('user_id'), resultado_completo, diagnostico_final, observacoes, pedido_id), commit=True)
            
            print(f"[OK] Pedido #{pedido_id} atualizado para status 'concluido'")
            
            # Criar notificação para o médico
            if medico_usuario_id:
                try:
                    from .notifications import criar_notificacao_analise_manual
                    notificacao_criada = criar_notificacao_analise_manual(
                        medico_id=medico_usuario_id,
                        pedido_id=pedido_id,
                        consulta_id=consulta_id,
                        tipo_exame=tipo_exame,
                        diagnostico_final=diagnostico_final,
                        paciente_nome=paciente_nome
                    )
                    
                    if notificacao_criada:
                        print(f"[OK] Notificação criada para médico #{medico_usuario_id} ({medico_nome})")
                        flash(f'Análise salva e médico {medico_nome} foi notificado!', 'success')
                    else:
                        print(f"[WARN] Falha ao criar notificação para médico #{medico_usuario_id}")
                        flash('Análise salva, mas houve falha ao notificar o médico.', 'warning')
                except Exception as e:
                    print(f"[WARN] Erro ao criar notificação: {e}")
                    flash('Análise salva, mas houve falha ao notificar o médico.', 'warning')
            else:
                print(f"[WARN] Médico não encontrado para o pedido #{pedido_id}")
                flash('Análise salva, mas não foi possível notificar o médico.', 'warning')
            
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"[ERROR] Erro ao salvar análise manual: {str(e)}")
            print(f"[ERROR] ERRO DETALHADO: {str(e)}")
            traceback.print_exc()
            flash(f'Erro ao salvar análise manual: {str(e)}', 'danger')
            return redirect(url_for('analista.analise_manual', pedido_id=pedido_id))
    
    print("  - Analise manual routes registradas com NOTIFICAÇÕES")
    print("  - Rotas adicionais registradas com sucesso!")
    
    print("\n" + "=" * 50)
    print("BLUEPRINT DO ANALISTA INICIALIZADO COM SUCESSO!")
    print("=" * 50 + "\n")
    
    return analista_bp
