from flask import request, render_template, redirect, url_for, flash, session, jsonify
from datetime import datetime
import pymysql
import traceback


def register_acoes_routes(bp, mysql):

    # ===================== SAFE INT =====================
    def safe_int(value):
        try:
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                value = value.decode("utf-8", errors="ignore")
            value = str(value).strip()
            if value == "" or value.lower() == "none":
                return None
            if not value.isdigit():
                return None
            return int(value)
        except:
            return None

    # ===================== SAFE STR =====================
    def safe_str(value):
        try:
            if value is None:
                return ""
            if isinstance(value, (bytes, bytearray)):
                return value.decode("utf-8", errors="ignore")
            return str(value).strip()
        except:
            return ""

    # ===================== DECODIFICAR BYTES =====================
    def decode_bytes(value):
        """Decodifica bytes para string UTF-8"""
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode('utf-8')
            except:
                return str(value)
        return value

    # ===================== GET VALUE FROM ROW (DICT OR TUPLE) =====================
    def get_row_value(row, index, key=None):
        """Obtém valor de uma linha que pode ser tupla ou dicionário"""
        if row is None:
            return None
        if isinstance(row, dict):
            # É dicionário - usar a chave se fornecida, senão tentar índice convertido
            if key:
                return row.get(key)
            # Tenta converter índice para nome de campo comum
            field_names = ['id', 'tipo', 'nome', 'email', 'crm', 'especialidade', 'status', 
                          'paciente_nome', 'medico_nome', 'observacoes', 'diagnostico', 
                          'sintomas', 'data_hora', 'telefone', 'endereco']
            if index < len(field_names):
                return row.get(field_names[index])
            return None
        else:
            # É tupla/lista - usar índice
            if index < len(row):
                return row[index]
            return None

    # ===================== MÉDICO ID CORRIGIDO (FUNCIONA COM DICT OU TUPLE) =====================
    def get_medico_id():
        """Obtém o ID do médico a partir do user_id na sessão"""
        try:
            # PEGAR O USER_ID DA SESSÃO
            user_id_raw = session.get("user_id")
            
            print("=" * 60)
            print("=== GET_MEDICO_ID ===")
            print(f"user_id_raw: {repr(user_id_raw)}")
            print(f"Tipo: {type(user_id_raw)}")
            
            if user_id_raw is None:
                print("ERRO: user_id não encontrado na sessão!")
                return None
            
            # Decodificar se for bytes
            if isinstance(user_id_raw, (bytes, bytearray)):
                user_id_raw = user_id_raw.decode("utf-8", errors="ignore")
                print(f"Após decode: {repr(user_id_raw)}")
            
            # Converter para inteiro
            try:
                user_id_int = int(user_id_raw)
                print(f"user_id_int: {user_id_int}")
            except ValueError as e:
                print(f"ERRO ao converter: {e}")
                return None
            
            cursor = mysql.connection.cursor()
            
            # VERIFICAR SE O USUÁRIO É MÉDICO
            query_usuario = "SELECT id, tipo FROM usuarios WHERE id = %s"
            cursor.execute(query_usuario, (user_id_int,))
            usuario = cursor.fetchone()
            
            if not usuario:
                print(f"ERRO: Usuário ID {user_id_int} não encontrado!")
                cursor.close()
                return None
            
            # 🔧 CORREÇÃO: Funciona com dicionário OU tupla
            tipo_usuario = None
            if isinstance(usuario, dict):
                # É dicionário
                tipo_usuario = usuario.get('tipo')
                print(f"usuario é dict, tipo: {tipo_usuario}")
            else:
                # É tupla
                tipo_usuario = usuario[1] if len(usuario) > 1 else None
                print(f"usuario é tuple, tipo: {tipo_usuario}")
            
            if isinstance(tipo_usuario, bytes):
                tipo_usuario = tipo_usuario.decode('utf-8', errors='ignore')
            
            print(f"tipo_usuario: {tipo_usuario}")
            
            if tipo_usuario != 'medico':
                print(f"ERRO: Usuário é do tipo '{tipo_usuario}', não é médico!")
                cursor.close()
                return None
            
            # BUSCAR MÉDICO
            query_medico = "SELECT id FROM medicos WHERE usuario_id = %s"
            cursor.execute(query_medico, (user_id_int,))
            medico = cursor.fetchone()
            cursor.close()
            
            if not medico:
                print(f"ERRO: Médico não encontrado para usuario_id {user_id_int}!")
                return None
            
            # 🔧 CORREÇÃO: Funciona com dicionário OU tupla
            medico_id = None
            if isinstance(medico, dict):
                medico_id = medico.get('id')
            else:
                medico_id = medico[0] if len(medico) > 0 else None
            
            print(f"Médico ID: {medico_id}")
            print("=" * 60)
            
            return medico_id
            
        except Exception as e:
            print(f"ERRO em get_medico_id: {e}")
            print(traceback.format_exc())
            return None

    # ===================== VISUALIZAR CONSULTA =====================
    @bp.route("/<int:consulta_id>/visualizar")
    def visualizar_consulta(consulta_id):
        """Rota para visualizar detalhes da consulta"""
        try:
            # VERIFICAR LOGIN
            if 'user_id' not in session:
                flash("Você precisa estar logado.", "danger")
                return redirect(url_for("auth.login"))
            
            medico_id = get_medico_id()
            if not medico_id:
                flash("Médico não encontrado.", "danger")
                return redirect(url_for("auth.login"))
            
            cursor = mysql.connection.cursor()
            
            # BUSCAR CONSULTA
            query = """
                SELECT 
                    c.id, 
                    c.paciente_id, 
                    c.medico_id,
                    c.status,
                    c.data_hora,
                    c.observacoes,
                    c.sintomas,
                    c.diagnostico_final,
                    u.nome as paciente_nome,
                    mu.nome as medico_nome,
                    m.crm,
                    m.especialidade,
                    p.telefone as paciente_telefone,
                    p.data_nascimento,
                    p.endereco as paciente_endereco,
                    u.email as paciente_email
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                WHERE c.id = %s AND c.medico_id = %s
            """
            
            cursor.execute(query, (consulta_id, medico_id))
            consulta_raw = cursor.fetchone()
            
            if not consulta_raw:
                cursor.close()
                flash("Consulta não encontrada.", "danger")
                return redirect(url_for("medico.consultas"))
            
            # DECODIFICAR CAMPOS (funciona com dict ou tuple)
            if isinstance(consulta_raw, dict):
                consulta = {
                    "id": consulta_raw.get('id'),
                    "paciente_id": consulta_raw.get('paciente_id'),
                    "medico_id": consulta_raw.get('medico_id'),
                    "status": decode_bytes(consulta_raw.get('status')),
                    "data_hora": consulta_raw.get('data_hora'),
                    "observacoes": decode_bytes(consulta_raw.get('observacoes')),
                    "sintomas": decode_bytes(consulta_raw.get('sintomas')),
                    "diagnostico_final": decode_bytes(consulta_raw.get('diagnostico_final')),
                    "paciente_nome": decode_bytes(consulta_raw.get('paciente_nome')),
                    "medico_nome": decode_bytes(consulta_raw.get('medico_nome')),
                    "crm": decode_bytes(consulta_raw.get('crm')),
                    "especialidade": decode_bytes(consulta_raw.get('especialidade')),
                    "paciente_telefone": decode_bytes(consulta_raw.get('paciente_telefone')),
                    "data_nascimento": consulta_raw.get('data_nascimento'),
                    "paciente_endereco": decode_bytes(consulta_raw.get('paciente_endereco')),
                    "paciente_email": decode_bytes(consulta_raw.get('paciente_email'))
                }
            else:
                consulta = {
                    "id": consulta_raw[0],
                    "paciente_id": consulta_raw[1],
                    "medico_id": consulta_raw[2],
                    "status": decode_bytes(consulta_raw[3]) if isinstance(consulta_raw[3], bytes) else consulta_raw[3],
                    "data_hora": consulta_raw[4],
                    "observacoes": decode_bytes(consulta_raw[5]) if consulta_raw[5] else None,
                    "sintomas": decode_bytes(consulta_raw[6]) if consulta_raw[6] else None,
                    "diagnostico_final": decode_bytes(consulta_raw[7]) if consulta_raw[7] else None,
                    "paciente_nome": decode_bytes(consulta_raw[8]) if isinstance(consulta_raw[8], bytes) else consulta_raw[8],
                    "medico_nome": decode_bytes(consulta_raw[9]) if isinstance(consulta_raw[9], bytes) else consulta_raw[9],
                    "crm": decode_bytes(consulta_raw[10]) if isinstance(consulta_raw[10], bytes) else consulta_raw[10],
                    "especialidade": decode_bytes(consulta_raw[11]) if isinstance(consulta_raw[11], bytes) else consulta_raw[11],
                    "paciente_telefone": decode_bytes(consulta_raw[12]) if isinstance(consulta_raw[12], bytes) else consulta_raw[12],
                    "data_nascimento": consulta_raw[13],
                    "paciente_endereco": decode_bytes(consulta_raw[14]) if isinstance(consulta_raw[14], bytes) else consulta_raw[14],
                    "paciente_email": decode_bytes(consulta_raw[15]) if isinstance(consulta_raw[15], bytes) else consulta_raw[15]
                }
            
            # CALCULAR IDADE
            if consulta.get("data_nascimento"):
                today = datetime.now().date()
                birth_date = consulta["data_nascimento"]
                if isinstance(birth_date, datetime):
                    birth_date = birth_date.date()
                idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                consulta["paciente_idade"] = f"{idade} anos"
            else:
                consulta["paciente_idade"] = None
            
            # STATUS CLASS
            status_classes = {
                'agendada': 'secondary',
                'confirmada': 'primary',
                'realizada': 'success',
                'cancelada': 'danger',
                'internado': 'info'
            }
            consulta["status_class"] = status_classes.get(consulta["status"], 'secondary')
            
            # VERIFICAR SE JÁ EXISTE INTERNAÇÃO
            cursor.execute("""
                SELECT id FROM internacoes 
                WHERE consulta_id = %s AND status = 'ativa'
            """, (consulta_id,))
            internacao = cursor.fetchone()
            internacao_existente = internacao is not None
            
            # BUSCAR SINAIS VITAIS
            cursor.execute("""
                SELECT * FROM sinais_vitais 
                WHERE consulta_id = %s 
                ORDER BY data_afericao DESC
            """, (consulta_id,))
            sinais_raw = cursor.fetchall()
            sinais_vitais = []
            for s in sinais_raw:
                if isinstance(s, dict):
                    sinais_vitais.append({
                        "id": s.get('id'),
                        "pressao_arterial": decode_bytes(s.get('pressao_arterial')),
                        "frequencia_cardiaca": s.get('frequencia_cardiaca'),
                        "frequencia_respiratoria": s.get('frequencia_respiratoria'),
                        "temperatura": s.get('temperatura'),
                        "saturacao_oxigenio": s.get('saturacao_oxigenio'),
                        "glicemia": s.get('glicemia'),
                        "peso": s.get('peso'),
                        "observacoes": decode_bytes(s.get('observacoes')),
                        "data_afericao": s.get('data_afericao')
                    })
                else:
                    sinais_vitais.append({
                        "id": s[0],
                        "pressao_arterial": decode_bytes(s[3]) if s[3] else None,
                        "frequencia_cardiaca": s[4],
                        "frequencia_respiratoria": s[5],
                        "temperatura": s[6],
                        "saturacao_oxigenio": s[7],
                        "glicemia": s[8],
                        "peso": s[9],
                        "observacoes": decode_bytes(s[10]) if s[10] else None,
                        "data_afericao": s[2]
                    })
            
            # BUSCAR SINTOMAS
            sintomas = []
            if consulta.get("sintomas"):
                try:
                    import json
                    sintomas = json.loads(consulta["sintomas"])
                except:
                    sintomas = [consulta["sintomas"]]
            
            cursor.close()
            
            return render_template(
                "consulta/detalhes_consulta.html",
                consulta=consulta,
                internacao_existente=internacao_existente,
                sinais_vitais=sinais_vitais,
                sintomas=sintomas,
                agora=datetime.now().strftime("%d/%m/%Y %H:%M")
            )
            
        except Exception as e:
            print("ERRO em visualizar_consulta:")
            print(traceback.format_exc())
            flash(str(e), "danger")
            return redirect(url_for("medico.consultas"))

    # ===================== INTERNAÇÃO =====================
    @bp.route("/<int:consulta_id>/internar", methods=["GET", "POST"])
    def internar_paciente(consulta_id):

        try:
            # VERIFICAR SE USUÁRIO ESTÁ LOGADO
            if 'user_id' not in session:
                flash("Você precisa estar logado para acessar esta página.", "danger")
                return redirect(url_for("auth.login"))
            
            # OBTER ID DO MÉDICO
            medico_id = get_medico_id()

            if not medico_id:
                flash("Médico não encontrado. Por favor, faça login novamente ou verifique seu cadastro.", "danger")
                return redirect(url_for("auth.login"))

            cursor = mysql.connection.cursor()

            # ===================== CONSULTA =====================
            query_consulta = """
                SELECT 
                    c.id, 
                    c.paciente_id, 
                    c.medico_id,
                    c.status,
                    c.data_hora,
                    c.observacoes,
                    c.sintomas,
                    c.diagnostico_final,
                    u.nome as paciente_nome,
                    mu.nome as medico_nome,
                    m.crm
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                WHERE c.id = %s AND c.medico_id = %s
            """
            
            print(f"=== BUSCANDO CONSULTA ===")
            print(f"consulta_id: {consulta_id}")
            print(f"medico_id: {medico_id}")
            
            cursor.execute(query_consulta, (consulta_id, medico_id))
            consulta_raw = cursor.fetchone()
            
            if not consulta_raw:
                cursor.close()
                flash("Consulta não encontrada ou não pertence a este médico.", "danger")
                return redirect(url_for("medico.consultas"))
            
            # DECODIFICAR CAMPOS (funciona com dict ou tuple)
            if isinstance(consulta_raw, dict):
                consulta = {
                    "id": consulta_raw.get('id'),
                    "paciente_id": consulta_raw.get('paciente_id'),
                    "medico_id": consulta_raw.get('medico_id'),
                    "status": decode_bytes(consulta_raw.get('status')),
                    "data_hora": consulta_raw.get('data_hora'),
                    "observacoes": decode_bytes(consulta_raw.get('observacoes')),
                    "sintomas": decode_bytes(consulta_raw.get('sintomas')),
                    "diagnostico_final": decode_bytes(consulta_raw.get('diagnostico_final')),
                    "paciente_nome": decode_bytes(consulta_raw.get('paciente_nome')),
                    "medico_nome": decode_bytes(consulta_raw.get('medico_nome')),
                    "crm": decode_bytes(consulta_raw.get('crm'))
                }
            else:
                consulta = {
                    "id": consulta_raw[0],
                    "paciente_id": consulta_raw[1],
                    "medico_id": consulta_raw[2],
                    "status": decode_bytes(consulta_raw[3]) if isinstance(consulta_raw[3], bytes) else consulta_raw[3],
                    "data_hora": consulta_raw[4],
                    "observacoes": decode_bytes(consulta_raw[5]) if consulta_raw[5] else None,
                    "sintomas": decode_bytes(consulta_raw[6]) if consulta_raw[6] else None,
                    "diagnostico_final": decode_bytes(consulta_raw[7]) if consulta_raw[7] else None,
                    "paciente_nome": decode_bytes(consulta_raw[8]) if isinstance(consulta_raw[8], bytes) else consulta_raw[8],
                    "medico_nome": decode_bytes(consulta_raw[9]) if isinstance(consulta_raw[9], bytes) else consulta_raw[9],
                    "crm": decode_bytes(consulta_raw[10]) if isinstance(consulta_raw[10], bytes) else consulta_raw[10]
                }
            
            print(f"Consulta encontrada - Paciente: {consulta['paciente_nome']}")
            print(f"Status da consulta: {consulta['status']}")

            # ===================== POST =====================
            if request.method == "POST":

                # PEGAR DADOS DO FORMULÁRIO
                leito_id_raw = request.form.get("leito_id", "")
                tipo_raw = request.form.get("tipo_internacao", "")
                diagnostico_raw = request.form.get("diagnostico", "")
                observacoes_raw = request.form.get("observacoes", "")

                # CONVERTER PARA STRING PURA
                tipo_str = safe_str(tipo_raw)
                diagnostico_str = safe_str(diagnostico_raw)
                observacoes_str = safe_str(observacoes_raw)
                
                # CONVERTER LEITO_ID PARA INTEIRO
                leito_id_str = safe_str(leito_id_raw)
                try:
                    leito_id_int = int(leito_id_str) if leito_id_str.isdigit() else None
                except:
                    leito_id_int = None

                # DEBUG
                print("=" * 60)
                print("=== DADOS DO POST ===")
                print(f"leito_id_int: {leito_id_int}")
                print(f"tipo_str: {repr(tipo_str)}")
                print(f"diagnostico_str: {repr(diagnostico_str)}")
                print("=" * 60)

                # VALIDAÇÕES
                if leito_id_int is None:
                    flash("Selecione um leito válido.", "danger")
                    return redirect(request.url)

                if not tipo_str or not diagnostico_str:
                    flash("Preencha todos os campos obrigatórios.", "danger")
                    return redirect(request.url)

                # VERIFICAR LEITO DISPONÍVEL
                cursor.execute("""
                    SELECT id, alas, numero FROM leitos
                    WHERE id = %s AND status = 'disponivel'
                """, (leito_id_int,))

                leito = cursor.fetchone()

                if not leito:
                    flash("Leito indisponível. Por favor, selecione outro leito.", "danger")
                    return redirect(request.url)

                try:
                    numero_prontuario = f"INT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    cursor_insert = mysql.connection.cursor()
                    
                    query_insert = """
                        INSERT INTO internacoes 
                        (paciente_id, medico_responsavel_id, leito_id, consulta_id,
                         data_internacao, tipo_internacao, diagnostico_inicial,
                         observacoes, status, numero_prontuario)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    valores = (
                        int(consulta["paciente_id"]),
                        int(medico_id),
                        leito_id_int,
                        int(consulta_id),
                        datetime.now(),
                        tipo_str,
                        diagnostico_str,
                        observacoes_str if observacoes_str else None,
                        'ativa',
                        numero_prontuario
                    )
                    
                    print("=== EXECUTANDO INSERT ===")
                    print(f"Valores: {valores}")
                    
                    cursor_insert.execute(query_insert, valores)
                    internacao_id = cursor_insert.lastrowid
                    
                    print(f"Internação criada com ID: {internacao_id}")
                    
                    # ATUALIZAR STATUS DO LEITO
                    cursor_insert.execute("""
                        UPDATE leitos 
                        SET status = 'ocupado' 
                        WHERE id = %s
                    """, (leito_id_int,))
                    
                    # ATUALIZAR STATUS DA CONSULTA
                    cursor_insert.execute("""
                        UPDATE consultas 
                        SET status = 'internado' 
                        WHERE id = %s
                    """, (int(consulta_id),))
                    
                    mysql.connection.commit()
                    cursor_insert.close()
                    cursor.close()
                    
                    flash(f"Internação realizada com sucesso! Prontuário: {numero_prontuario}", "success")
                    
                    # REDIRECIONAR PARA VISUALIZAR A CONSULTA
                    return redirect(f"/medico/consulta/{consulta_id}/visualizar")
                    
                except pymysql.Error as e:
                    mysql.connection.rollback()
                    cursor.close()
                    
                    print("=" * 60)
                    print("ERRO PYMYSQL:")
                    print(f"Código: {e.args[0]}")
                    print(f"Mensagem: {e.args[1]}")
                    print(traceback.format_exc())
                    print("=" * 60)
                    
                    flash(f"Erro no banco de dados: {e.args[1]}", "danger")
                    return redirect(request.url)
                    
                except Exception as e:
                    mysql.connection.rollback()
                    cursor.close()
                    
                    print("=" * 60)
                    print("ERRO GERAL:")
                    print(traceback.format_exc())
                    print(f"ERRO: {str(e)}")
                    print("=" * 60)
                    
                    flash(f"Erro ao realizar internação: {str(e)}", "danger")
                    return redirect(request.url)

            # ===================== GET =====================
            # Buscar leitos disponíveis
            cursor.execute("""
                SELECT id, alas, numero, tipo
                FROM leitos
                WHERE status = 'disponivel'
                ORDER BY alas, numero
            """)

            leitos = cursor.fetchall()
            leitos_list = []
            for leito in leitos:
                if isinstance(leito, dict):
                    leitos_list.append({
                        "id": leito.get('id'),
                        "alas": decode_bytes(leito.get('alas')),
                        "numero": leito.get('numero'),
                        "tipo": decode_bytes(leito.get('tipo'))
                    })
                else:
                    leitos_list.append({
                        "id": leito[0],
                        "alas": decode_bytes(leito[1]) if isinstance(leito[1], bytes) else leito[1],
                        "numero": leito[2],
                        "tipo": decode_bytes(leito[3]) if isinstance(leito[3], bytes) else leito[3]
                    })
            
            cursor.close()

            return render_template(
                "medico/internacao/internar_paciente.html",
                consulta=consulta,
                leitos_disponiveis=leitos_list
            )

        except Exception as e:
            print("=" * 60)
            print("ERRO GERAL NA ROTA:")
            print(traceback.format_exc())
            print(f"ERRO: {str(e)}")
            print("=" * 60)
            
            flash(str(e), "danger")
            return redirect(url_for("medico.consultas"))

    # ===================== PACIENTES INTERNADOS =====================
    @bp.route("/pacientes-internados")
    def pacientes_internados():
        """Lista todos os pacientes internados"""
        try:
            # VERIFICAR SE USUÁRIO ESTÁ LOGADO
            if 'user_id' not in session:
                flash("Você precisa estar logado.", "danger")
                return redirect(url_for("auth.login"))
            
            medico_id = get_medico_id()
            if not medico_id:
                flash("Médico não encontrado.", "danger")
                return redirect(url_for("auth.login"))
            
            cursor = mysql.connection.cursor()
            
            # Buscar todos os pacientes internados
            query = """
                SELECT 
                    i.id,
                    i.numero_prontuario,
                    i.data_internacao,
                    i.tipo_internacao,
                    i.diagnostico_inicial,
                    i.observacoes,
                    i.status,
                    i.consulta_id,
                    p.id as paciente_id,
                    u.nome as paciente_nome,
                    m.crm as medico_crm,
                    mu.nome as medico_nome,
                    l.alas,
                    l.numero as leito_numero,
                    l.tipo as leito_tipo
                FROM internacoes i
                JOIN pacientes p ON i.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN medicos m ON i.medico_responsavel_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                JOIN leitos l ON i.leito_id = l.id
                WHERE i.status = 'ativa'
                ORDER BY i.data_internacao DESC
            """
            
            cursor.execute(query)
            internacoes_raw = cursor.fetchall()
            
            # Contar leitos
            cursor.execute("SELECT COUNT(*) FROM leitos WHERE status = 'ocupado'")
            leitos_ocupados_raw = cursor.fetchone()
            leitos_ocupados = 0
            if leitos_ocupados_raw:
                if isinstance(leitos_ocupados_raw, dict):
                    leitos_ocupados = list(leitos_ocupados_raw.values())[0] if leitos_ocupados_raw else 0
                else:
                    leitos_ocupados = leitos_ocupados_raw[0] if len(leitos_ocupados_raw) > 0 else 0
            
            cursor.execute("SELECT COUNT(*) FROM leitos")
            total_leitos_raw = cursor.fetchone()
            total_leitos = 0
            if total_leitos_raw:
                if isinstance(total_leitos_raw, dict):
                    total_leitos = list(total_leitos_raw.values())[0] if total_leitos_raw else 0
                else:
                    total_leitos = total_leitos_raw[0] if len(total_leitos_raw) > 0 else 0
            
            cursor.execute("SELECT COUNT(*) FROM leitos WHERE status = 'disponivel'")
            leitos_disponiveis_raw = cursor.fetchone()
            leitos_disponiveis = 0
            if leitos_disponiveis_raw:
                if isinstance(leitos_disponiveis_raw, dict):
                    leitos_disponiveis = list(leitos_disponiveis_raw.values())[0] if leitos_disponiveis_raw else 0
                else:
                    leitos_disponiveis = leitos_disponiveis_raw[0] if len(leitos_disponiveis_raw) > 0 else 0
            
            pacientes_internados_lista = []
            for internacao in internacoes_raw:
                if isinstance(internacao, dict):
                    pacientes_internados_lista.append({
                        "id": internacao.get('id'),
                        "numero_prontuario": internacao.get('numero_prontuario'),
                        "data_internacao": internacao.get('data_internacao'),
                        "tipo_internacao": decode_bytes(internacao.get('tipo_internacao')),
                        "diagnostico_inicial": decode_bytes(internacao.get('diagnostico_inicial')),
                        "observacoes": decode_bytes(internacao.get('observacoes')),
                        "status": decode_bytes(internacao.get('status')),
                        "consulta_id": internacao.get('consulta_id'),
                        "paciente_id": internacao.get('paciente_id'),
                        "paciente_nome": decode_bytes(internacao.get('paciente_nome')),
                        "medico_crm": decode_bytes(internacao.get('medico_crm')),
                        "medico_nome": decode_bytes(internacao.get('medico_nome')),
                        "leito_alas": decode_bytes(internacao.get('leito_alas')),
                        "leito_numero": internacao.get('leito_numero'),
                        "leito_tipo": decode_bytes(internacao.get('leito_tipo'))
                    })
                else:
                    pacientes_internados_lista.append({
                        "id": internacao[0],
                        "numero_prontuario": internacao[1],
                        "data_internacao": internacao[2],
                        "tipo_internacao": decode_bytes(internacao[3]) if isinstance(internacao[3], bytes) else internacao[3],
                        "diagnostico_inicial": decode_bytes(internacao[4]) if internacao[4] else None,
                        "observacoes": decode_bytes(internacao[5]) if internacao[5] else None,
                        "status": decode_bytes(internacao[6]) if isinstance(internacao[6], bytes) else internacao[6],
                        "consulta_id": internacao[7],
                        "paciente_id": internacao[8],
                        "paciente_nome": decode_bytes(internacao[9]) if isinstance(internacao[9], bytes) else internacao[9],
                        "medico_crm": decode_bytes(internacao[10]) if isinstance(internacao[10], bytes) else internacao[10],
                        "medico_nome": decode_bytes(internacao[11]) if isinstance(internacao[11], bytes) else internacao[11],
                        "leito_alas": decode_bytes(internacao[12]) if isinstance(internacao[12], bytes) else internacao[12],
                        "leito_numero": internacao[13],
                        "leito_tipo": decode_bytes(internacao[14]) if isinstance(internacao[14], bytes) else internacao[14]
                    })
            
            cursor.close()
            
            return render_template(
                "medico/internados.html",
                pacientes_internados_lista=pacientes_internados_lista,
                pacientes_internados=len(pacientes_internados_lista),
                leitos_ocupados=leitos_ocupados,
                leitos_disponiveis=leitos_disponiveis,
                total_leitos=total_leitos,
                agora=datetime.now().strftime("%d/%m/%Y %H:%M")
            )
            
        except Exception as e:
            print(f"ERRO em pacientes_internados: {e}")
            print(traceback.format_exc())
            flash(str(e), "danger")
            return redirect(url_for("medico.dashboard"))

    # ===================== DAR ALTA =====================
    @bp.route("/internacao/<int:internacao_id>/alta", methods=["POST"])
    def dar_alta(internacao_id):
        """Dar alta a um paciente internado"""
        try:
            # VERIFICAR SE USUÁRIO ESTÁ LOGADO
            if 'user_id' not in session:
                return jsonify({"success": False, "error": "Não autorizado"}), 401
            
            medico_id = get_medico_id()
            if not medico_id:
                return jsonify({"success": False, "error": "Médico não encontrado"}), 404
            
            data = request.get_json()
            diagnostico_final = safe_str(data.get('diagnostico_final', ''))
            observacoes_alta = safe_str(data.get('observacoes_alta', ''))
            
            cursor = mysql.connection.cursor()
            
            # Verificar se a internação existe
            cursor.execute("SELECT id, leito_id, consulta_id FROM internacoes WHERE id = %s AND status = 'ativa'", (internacao_id,))
            internacao = cursor.fetchone()
            
            if not internacao:
                cursor.close()
                return jsonify({"success": False, "error": "Internação não encontrada ou já encerrada"}), 404
            
            # Funciona com dict ou tuple
            if isinstance(internacao, dict):
                leito_id = internacao.get('leito_id')
                consulta_id = internacao.get('consulta_id')
            else:
                leito_id = internacao[1] if len(internacao) > 1 else None
                consulta_id = internacao[2] if len(internacao) > 2 else None
            
            # Atualizar internação
            cursor.execute("""
                UPDATE internacoes 
                SET status = 'alta', 
                    data_alta = %s,
                    diagnostico_final = %s,
                    observacoes = %s
                WHERE id = %s
            """, (datetime.now(), diagnostico_final, observacoes_alta, internacao_id))
            
            # Liberar leito
            if leito_id:
                cursor.execute("UPDATE leitos SET status = 'disponivel' WHERE id = %s", (leito_id,))
            
            # Atualizar status da consulta (se houver)
            if consulta_id:
                cursor.execute("UPDATE consultas SET status = 'realizada' WHERE id = %s", (consulta_id,))
            
            mysql.connection.commit()
            cursor.close()
            
            return jsonify({"success": True, "message": "Alta realizada com sucesso!"})
            
        except Exception as e:
            print(f"ERRO em dar_alta: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500

    # ===================== DETALHES DA INTERNAÇÃO =====================
    @bp.route("/internacao/<int:internacao_id>")
    def detalhes_internacao(internacao_id):
        """Rota para visualizar detalhes da internação"""
        try:
            # VERIFICAR SE USUÁRIO ESTÁ LOGADO
            if 'user_id' not in session:
                flash("Você precisa estar logado para acessar esta página.", "danger")
                return redirect(url_for("auth.login"))
            
            cursor = mysql.connection.cursor()
            
            query = """
                SELECT 
                    i.id,
                    i.numero_prontuario,
                    i.data_internacao,
                    i.tipo_internacao,
                    i.diagnostico_inicial,
                    i.observacoes,
                    i.status,
                    i.consulta_id,
                    p.id as paciente_id,
                    u.nome as paciente_nome,
                    m.crm as medico_crm,
                    mu.nome as medico_nome,
                    l.alas,
                    l.numero as leito_numero,
                    l.tipo as leito_tipo
                FROM internacoes i
                JOIN pacientes p ON i.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN medicos m ON i.medico_responsavel_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                JOIN leitos l ON i.leito_id = l.id
                WHERE i.id = %s
            """
            
            cursor.execute(query, (internacao_id,))
            internacao_raw = cursor.fetchone()
            cursor.close()
            
            if not internacao_raw:
                flash("Internação não encontrada.", "danger")
                return redirect(url_for("medico.consultas"))
            
            # Decodificar campos (funciona com dict ou tuple)
            if isinstance(internacao_raw, dict):
                internacao = {
                    "id": internacao_raw.get('id'),
                    "numero_prontuario": internacao_raw.get('numero_prontuario'),
                    "data_internacao": internacao_raw.get('data_internacao'),
                    "tipo_internacao": decode_bytes(internacao_raw.get('tipo_internacao')),
                    "diagnostico_inicial": decode_bytes(internacao_raw.get('diagnostico_inicial')),
                    "observacoes": decode_bytes(internacao_raw.get('observacoes')),
                    "status": decode_bytes(internacao_raw.get('status')),
                    "consulta_id": internacao_raw.get('consulta_id'),
                    "paciente_id": internacao_raw.get('paciente_id'),
                    "paciente_nome": decode_bytes(internacao_raw.get('paciente_nome')),
                    "medico_crm": decode_bytes(internacao_raw.get('medico_crm')),
                    "medico_nome": decode_bytes(internacao_raw.get('medico_nome')),
                    "leito_alas": decode_bytes(internacao_raw.get('leito_alas')),
                    "leito_numero": internacao_raw.get('leito_numero'),
                    "leito_tipo": decode_bytes(internacao_raw.get('leito_tipo'))
                }
            else:
                internacao = {
                    "id": internacao_raw[0],
                    "numero_prontuario": internacao_raw[1],
                    "data_internacao": internacao_raw[2],
                    "tipo_internacao": decode_bytes(internacao_raw[3]) if isinstance(internacao_raw[3], bytes) else internacao_raw[3],
                    "diagnostico_inicial": decode_bytes(internacao_raw[4]) if internacao_raw[4] else None,
                    "observacoes": decode_bytes(internacao_raw[5]) if internacao_raw[5] else None,
                    "status": decode_bytes(internacao_raw[6]) if isinstance(internacao_raw[6], bytes) else internacao_raw[6],
                    "consulta_id": internacao_raw[7],
                    "paciente_id": internacao_raw[8],
                    "paciente_nome": decode_bytes(internacao_raw[9]) if isinstance(internacao_raw[9], bytes) else internacao_raw[9],
                    "medico_crm": decode_bytes(internacao_raw[10]) if isinstance(internacao_raw[10], bytes) else internacao_raw[10],
                    "medico_nome": decode_bytes(internacao_raw[11]) if isinstance(internacao_raw[11], bytes) else internacao_raw[11],
                    "leito_alas": decode_bytes(internacao_raw[12]) if isinstance(internacao_raw[12], bytes) else internacao_raw[12],
                    "leito_numero": internacao_raw[13],
                    "leito_tipo": decode_bytes(internacao_raw[14]) if isinstance(internacao_raw[14], bytes) else internacao_raw[14]
                }
            
            return render_template(
                "medico/internacao/detalhes_internacao.html",
                internacao=internacao
            )
            
        except Exception as e:
            print(f"ERRO ao buscar internação: {e}")
            print(traceback.format_exc())
            flash(f"Erro ao carregar detalhes da internação: {str(e)}", "danger")
            return redirect(url_for("medico.consultas"))

    # ===================== ROTA DE DIAGNÓSTICO =====================
    @bp.route("/diagnostico-sessao")
    def diagnostico_sessao():
        """Rota de diagnóstico para verificar a sessão e o médico"""
        
        resultado = {
            "status": "ok",
            "sessao_existe": 'user_id' in session,
            "user_id_raw": None,
            "user_id_type": None,
            "user_id_decodificado": None,
            "usuario": None,
            "medico": None,
            "erros": []
        }
        
        if 'user_id' not in session:
            resultado["erros"].append("Usuário não está logado na sessão")
            resultado["status"] = "erro"
            return jsonify(resultado)
        
        user_id_raw = session.get('user_id')
        resultado["user_id_raw"] = repr(user_id_raw)
        resultado["user_id_type"] = str(type(user_id_raw))
        
        try:
            if isinstance(user_id_raw, bytes):
                user_id_decoded = user_id_raw.decode('utf-8')
                resultado["user_id_decodificado"] = user_id_decoded
                user_id_int = int(user_id_decoded)
            else:
                user_id_int = int(user_id_raw)
                resultado["user_id_decodificado"] = str(user_id_int)
        except Exception as e:
            resultado["erros"].append(f"Erro ao converter user_id: {str(e)}")
            resultado["status"] = "erro"
            return jsonify(resultado)
        
        try:
            cursor = mysql.connection.cursor()
            
            cursor.execute("SELECT id, nome, email, tipo, ativo FROM usuarios WHERE id = %s", (user_id_int,))
            usuario_raw = cursor.fetchone()
            
            if usuario_raw:
                if isinstance(usuario_raw, dict):
                    usuario = {
                        "id": usuario_raw.get('id'),
                        "nome": decode_bytes(usuario_raw.get('nome')),
                        "email": decode_bytes(usuario_raw.get('email')),
                        "tipo": decode_bytes(usuario_raw.get('tipo')),
                        "ativo": usuario_raw.get('ativo')
                    }
                else:
                    usuario = {
                        "id": usuario_raw[0],
                        "nome": decode_bytes(usuario_raw[1]),
                        "email": decode_bytes(usuario_raw[2]),
                        "tipo": decode_bytes(usuario_raw[3]) if isinstance(usuario_raw[3], bytes) else usuario_raw[3],
                        "ativo": usuario_raw[4]
                    }
                resultado["usuario"] = usuario
                
                if usuario['tipo'] == 'medico':
                    cursor.execute("SELECT id, crm, especialidade, status FROM medicos WHERE usuario_id = %s", (user_id_int,))
                    medico_raw = cursor.fetchone()
                    if medico_raw:
                        if isinstance(medico_raw, dict):
                            medico = {
                                "id": medico_raw.get('id'),
                                "crm": decode_bytes(medico_raw.get('crm')),
                                "especialidade": decode_bytes(medico_raw.get('especialidade')),
                                "status": decode_bytes(medico_raw.get('status'))
                            }
                        else:
                            medico = {
                                "id": medico_raw[0],
                                "crm": decode_bytes(medico_raw[1]) if isinstance(medico_raw[1], bytes) else medico_raw[1],
                                "especialidade": decode_bytes(medico_raw[2]) if isinstance(medico_raw[2], bytes) else medico_raw[2],
                                "status": decode_bytes(medico_raw[3]) if isinstance(medico_raw[3], bytes) else medico_raw[3]
                            }
                        resultado["medico"] = medico
                    else:
                        resultado["erros"].append("Usuário é médico mas não tem registro na tabela medicos")
                else:
                    resultado["erros"].append(f"Usuário não é médico. Tipo: {usuario['tipo']}")
            else:
                resultado["erros"].append(f"Usuário ID {user_id_int} não encontrado no banco")
            
            cursor.close()
            
        except Exception as e:
            resultado["erros"].append(f"Erro no banco: {str(e)}")
            resultado["status"] = "erro"
        
        return jsonify(resultado)
