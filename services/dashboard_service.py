# services/dashboard_service.py
"""
Serviço otimizado para o dashboard do médico
Busca todos os dados em UMA ÚNICA consulta ao banco de dados
Com cache para melhor performance
"""

import json
import time
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache em memória (substituir por Redis em produção)
_dashboard_cache = {}

class DashboardService:
    """Serviço otimizado para o dashboard do médico"""
    
    CACHE_TEMPO = 300  # 5 minutos
    
    @staticmethod
    def get_dados_dashboard(medico_id, mysql, usar_cache=True):
        """
        Busca todos os dados do dashboard em UMA ÚNICA consulta
        
        Args:
            medico_id: ID do médico logado
            mysql: Conexão com MySQL
            usar_cache: Se deve usar cache (True por padrão)
            
        Returns:
            dict: Dados do dashboard
        """
        start_time = time.time()
        
        # Verificar cache
        cache_key = f"dashboard:{medico_id}"
        if usar_cache and cache_key in _dashboard_cache:
            cached = _dashboard_cache[cache_key]
            if time.time() - cached['timestamp'] < DashboardService.CACHE_TEMPO:
                logger.debug(f"Cache hit para dashboard do médico {medico_id}")
                return cached['data']
        
        try:
            cur = mysql.connection.cursor()
            
            # Query otimizada com subconsultas
            query = """
                SELECT
                    -- Consultas hoje
                    (SELECT COUNT(*) FROM consultas 
                     WHERE medico_id = %s AND DATE(data_hora) = CURDATE()) as consultas_hoje,
                    
                    -- Consultas pendentes (agendadas ou confirmadas)
                    (SELECT COUNT(*) FROM consultas 
                     WHERE medico_id = %s AND status IN ('agendada', 'confirmada')) as pendentes,
                    
                    -- Consultas realizadas no mês
                    (SELECT COUNT(*) FROM consultas 
                     WHERE medico_id = %s AND status = 'realizada'
                     AND MONTH(data_hora) = MONTH(CURDATE())
                     AND YEAR(data_hora) = YEAR(CURDATE())) as consultas_mes,
                    
                    -- Pacientes com sinais críticos (últimos 7 dias)
                    (SELECT COUNT(DISTINCT c.paciente_id)
                     FROM consultas c
                     JOIN sinais_vitais sv ON c.id = sv.consulta_id
                     WHERE c.medico_id = %s 
                     AND sv.data_afericao >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                     AND (
                         sv.pressao_arterial LIKE '%140%' 
                         OR sv.pressao_arterial LIKE '%150%'
                         OR sv.frequencia_cardiaca > 100 
                         OR sv.temperatura > 37.5 
                         OR sv.saturacao_oxigenio < 95
                         OR sv.glicemia > 200
                         OR sv.glicemia < 70
                     )) as pacientes_criticos,
                    
                    -- Últimas 8 consultas (para mostrar no dashboard)
                    (
                        SELECT JSON_ARRAYAGG(
                            JSON_OBJECT(
                                'id', c.id,
                                'paciente_id', p.id,
                                'paciente_nome', u.nome,
                                'data_hora', DATE_FORMAT(c.data_hora, '%d/%m/%Y %H:%i'),
                                'data_consulta', DATE_FORMAT(c.data_hora, '%d/%m/%Y'),
                                'hora_consulta', DATE_FORMAT(c.data_hora, '%H:%i'),
                                'status', c.status,
                                'status_class', 
                                CASE 
                                    WHEN c.status = 'agendada' THEN 'primary'
                                    WHEN c.status = 'confirmada' THEN 'info'
                                    WHEN c.status = 'realizada' THEN 'success'
                                    WHEN c.status = 'cancelada' THEN 'danger'
                                    ELSE 'secondary'
                                END,
                                'tem_sintomas', EXISTS(
                                    SELECT 1 FROM consultas c2 
                                    WHERE c2.id = c.id AND c2.sintomas IS NOT NULL AND c2.sintomas != ''
                                ),
                                'tem_analise_pendente', EXISTS(
                                    SELECT 1 FROM pedidos_analise pa 
                                    WHERE pa.consulta_id = c.id AND pa.status IN ('pendente', 'em_andamento')
                                ),
                                'tem_resultado', EXISTS(
                                    SELECT 1 FROM pedidos_analise pa 
                                    WHERE pa.consulta_id = c.id AND pa.status = 'concluido'
                                )
                            )
                        ) 
                        FROM consultas c
                        JOIN pacientes p ON c.paciente_id = p.id
                        JOIN usuarios u ON p.usuario_id = u.id
                        WHERE c.medico_id = %s
                        ORDER BY c.data_hora DESC
                        LIMIT 8
                    ) as ultimas_consultas,
                    
                    -- Estatísticas do médico
                    (SELECT COUNT(DISTINCT paciente_id) 
                     FROM consultas 
                     WHERE medico_id = %s) as total_pacientes,
                    
                    (SELECT COUNT(*) 
                     FROM consultas 
                     WHERE medico_id = %s) as total_consultas,
                    
                    -- Resultados pendentes (pedidos concluídos aguardando revisão)
                    (SELECT COUNT(*) 
                     FROM pedidos_analise 
                     WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente') as resultados_pendentes,
                    
                    -- Análises solicitadas (pedidos em andamento)
                    (SELECT COUNT(*) 
                     FROM pedidos_analise 
                     WHERE medico_id = %s AND status IN ('pendente', 'em_andamento')) as analises_solicitadas,
                    
                    -- Total de pedidos
                    (SELECT COUNT(*) 
                     FROM pedidos_analise 
                     WHERE medico_id = %s) as total_pedidos,
                    
                    -- Notificações (pedidos concluídos nos últimos 7 dias)
                    (SELECT COUNT(*) 
                     FROM pedidos_analise 
                     WHERE medico_id = %s AND status = 'concluido' 
                     AND data_conclusao >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as notificacoes
            """
            
            # Executar query com 10 parâmetros (medico_id repetido)
            params = [medico_id] * 10
            cur.execute(query, params)
            result = cur.fetchone()
            cur.close()
            
            if not result:
                logger.error(f"Nenhum resultado para médico {medico_id}")
                return DashboardService._get_dashboard_vazio()
            
            # Processar JSON das últimas consultas
            ultimas_consultas = []
            if result[4] and result[4] != 'null':
                try:
                    ultimas_consultas = json.loads(result[4])
                except json.JSONDecodeError as e:
                    logger.error(f"Erro ao decodificar JSON: {e}")
                    ultimas_consultas = []
            
            # Montar dicionário de resultado
            dados = {
                'consultas_hoje': result[0] or 0,
                'pendentes': result[1] or 0,
                'consultas_mes': result[2] or 0,
                'pacientes_criticos': result[3] or 0,
                'ultimas_consultas': ultimas_consultas,
                'total_pacientes': result[5] or 0,
                'total_consultas': result[6] or 0,
                'resultados_pendentes': result[7] or 0,
                'analises_solicitadas': result[8] or 0,
                'total_pedidos': result[9] or 0,
                'notificacoes': result[10] or 0,
                'contadorResultados': result[7] or 0,
                'contadorAnalises': result[8] or 0,
                'contadorPedidos': (result[7] or 0) + (result[8] or 0),
                'timestamp': int(time.time())
            }
            
            # Guardar em cache
            _dashboard_cache[cache_key] = {
                'data': dados,
                'timestamp': time.time()
            }
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Dashboard carregado em {elapsed:.2f}ms para médico {medico_id}")
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao buscar dashboard: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return DashboardService._get_dashboard_vazio()
    
    @staticmethod
    def _get_dashboard_vazio():
        """Retorna um dashboard vazio em caso de erro"""
        return {
            'consultas_hoje': 0,
            'pendentes': 0,
            'consultas_mes': 0,
            'pacientes_criticos': 0,
            'ultimas_consultas': [],
            'total_pacientes': 0,
            'total_consultas': 0,
            'resultados_pendentes': 0,
            'analises_solicitadas': 0,
            'total_pedidos': 0,
            'notificacoes': 0,
            'contadorResultados': 0,
            'contadorAnalises': 0,
            'contadorPedidos': 0,
            'timestamp': int(time.time())
        }
    
    @staticmethod
    def invalidar_cache(medico_id):
        """Invalida o cache do dashboard para um médico"""
        cache_key = f"dashboard:{medico_id}"
        if cache_key in _dashboard_cache:
            del _dashboard_cache[cache_key]
            logger.info(f"Cache invalidado para médico {medico_id}")
    
    @staticmethod
    def limpar_cache_expirado():
        """Limpa entradas expiradas do cache"""
        agora = time.time()
        expirados = []
        
        for key, value in _dashboard_cache.items():
            if agora - value['timestamp'] > DashboardService.CACHE_TEMPO:
                expirados.append(key)
        
        for key in expirados:
            del _dashboard_cache[key]
        
        if expirados:
            logger.info(f"Cache limpo: {len(expirados)} entradas removidas")