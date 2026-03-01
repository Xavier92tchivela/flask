# routes/medico/consulta/queries.py

def get_consultas_medico_query(filtros=None):
    """Retorna query base para consultas do médico"""
    query = """
        SELECT 
            c.id,
            p_u.nome as paciente_nome,
            p.data_nascimento,
            p.genero,
            p.telefone as paciente_telefone,
            p_u.email as paciente_email,
            c.data_hora,
            c.status,
            c.observacoes,
            c.sintomas,
            DAYNAME(c.data_hora) as dia_semana,
            DATE(c.data_hora) as data_consulta,
            TIME(c.data_hora) as hora_consulta,
            MONTH(c.data_hora) as mes,
            YEAR(c.data_hora) as ano
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios p_u ON p.usuario_id = p_u.id
        WHERE c.medico_id = %s
    """
    return query

def get_anos_disponiveis_query():
    """Retorna query para anos disponíveis"""
    return """
        SELECT DISTINCT YEAR(data_hora) as ano
        FROM consultas
        WHERE medico_id = %s
        ORDER BY ano DESC
    """

def get_medico_info_query():
    """Retorna query para informações do médico"""
    return """
        SELECT u.nome, m.especialidade 
        FROM medicos m
        JOIN usuarios u ON m.usuario_id = u.id
        WHERE m.id = %s
    """

def get_detalhes_consulta_query():
    """Retorna query para detalhes completos da consulta"""
    return """
        SELECT 
            c.id,
            m_u.nome as medico_nome,
            m.especialidade,
            m.crm,
            c.data_hora,
            c.status,
            c.observacoes,
            c.receita,
            p_u.nome as paciente_nome,
            p.data_nascimento,
            p.genero,
            p.telefone as paciente_telefone,
            p.endereco,
            m_u.email as medico_email,
            m.telefone as medico_telefone,
            p.id as paciente_id,
            m.id as medico_id,
            p_u.email as paciente_email,
            c.sintomas,
            DAYNAME(c.data_hora) as dia_semana,
            DATE(c.data_hora) as data_consulta,
            TIME(c.data_hora) as hora_consulta,
            MONTH(c.data_hora) as mes,
            YEAR(c.data_hora) as ano
        FROM consultas c 
        JOIN medicos m ON c.medico_id = m.id 
        JOIN usuarios m_u ON m.usuario_id = m_u.id 
        JOIN pacientes p ON c.paciente_id = p.id 
        JOIN usuarios p_u ON p.usuario_id = p_u.id 
        WHERE c.id = %s
    """

def get_diagnostico_query():
    """Retorna query para diagnóstico"""
    return """
        SELECT 
            d.id,
            d.tipo_exame,
            d.descricao,
            d.observacoes,
            d.resultado,
            d.diagnostico_preliminar,
            d.diagnostico_final,
            d.status,
            d.imagem_path,
            d.imagem_base64,
            d.formato_imagem,
            d.tamanho_imagem,
            d.criado_em,
            d.atualizado_em,
            m_u.nome as medico_nome,
            m.especialidade,
            m.crm
        FROM diagnostico d
        JOIN consultas c ON d.consulta_id = c.id
        JOIN medicos m ON c.medico_id = m.id
        JOIN usuarios m_u ON m.usuario_id = m_u.id
        WHERE d.consulta_id = %s
        ORDER BY d.id DESC
        LIMIT 1
    """

def get_pedido_analise_query():
    """Retorna query para pedido de análise"""
    return """
        SELECT 
            pa.id,
            pa.tipo_exame,
            pa.descricao,
            pa.observacoes,
            pa.urgencia,
            pa.status,
            pa.data_solicitacao,
            pa.data_conclusao,
            pa.resultado_analise,
            pa.diagnostico_analista,
            pa.recomendacoes_analista,
            pa.anexos,
            pa.status_aprovacao,
            pa.observacoes_medico,
            a.id as analista_id,
            ua.nome as analista_nome,
            a.especialidade as analista_especialidade
        FROM pedidos_analise pa
        LEFT JOIN analistas a ON pa.analista_id = a.id
        LEFT JOIN usuarios ua ON a.usuario_id = ua.id
        WHERE pa.consulta_id = %s
        ORDER BY pa.id DESC
        LIMIT 1
    """