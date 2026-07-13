"""Serviços de IA com Gemini para o módulo analista"""
import os
import logging
import traceback
import json
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from .file_utils import ensure_temp_folder, get_temp_folder

logger = logging.getLogger(__name__)

_gemini_available = False
_model_name = "gemini-2.5-flash"  # 🔥 MODELO ATUALIZADO
_app = None

def set_gemini_config(gemini_available, MODEL_NAME, app):
    """Configura o serviço Gemini"""
    global _gemini_available, _model_name, _app
    _gemini_available = gemini_available
    _model_name = MODEL_NAME if MODEL_NAME else "gemini-2.5-flash"
    _app = app

def salvar_imagem_temporaria(file):
    """Salva imagem temporariamente para análise"""
    try:
        temp_dir = ensure_temp_folder()
        
        # Gera nome único com timestamp e hash
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"temp_{timestamp}_{file.filename}"
        filepath = os.path.join(temp_dir, filename)
        
        file.save(filepath)
        logger.info(f"📸 Imagem temporária salva: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar imagem: {e}")
        return None

def preparar_contexto_clinico(pedido_info, observacoes_analista=''):
    """Prepara contexto clínico para análise"""
    from .helpers import calcular_idade
    
    try:
        if not pedido_info or len(pedido_info) < 15:
            return "Informações do pedido não disponíveis."
        
        tipo_exame = pedido_info[1] or 'Não especificado'
        descricao = pedido_info[2] or 'Não informada'
        observacoes = pedido_info[3] or 'Nenhuma'
        urgencia = pedido_info[4] or 'normal'
        paciente_nome = pedido_info[12] or 'Não informado'
        data_nascimento = pedido_info[13] if len(pedido_info) > 13 else None
        genero = pedido_info[14] if len(pedido_info) > 14 else ''
        
        idade = calcular_idade(data_nascimento) if data_nascimento else ''
        
        contexto = f"""
INFORMAÇÕES DO PACIENTE:
- Nome: {paciente_nome}
- Idade: {idade}
- Gênero: {genero}
- Tipo de exame: {tipo_exame}
- Urgência: {urgencia.upper()}

DESCRIÇÃO DO EXAME:
{descricao}

OBSERVAÇÕES MÉDICAS:
{observacoes}

OBSERVAÇÕES DO ANALISTA:
{observacoes_analista or 'Nenhuma'}
"""
        
        return contexto
        
    except Exception as e:
        logger.error(f"❌ Erro ao preparar contexto: {e}")
        return "Erro ao preparar contexto clínico."

def analisar_imagem_com_gemini(imagem_path, contexto_clinico):
    """
    Analisa imagem usando Gemini 2.5 Flash
    Retorna: (resultado, erro)
    """
    try:
        # ====== VERIFICAÇÕES INICIAIS ======
        # 1. Verifica se Gemini está disponível
        if not _gemini_available:
            logger.warning("⚠️ Gemini não disponível")
            return None, "API Gemini não configurada"
        
        # 2. Verifica se a imagem existe
        if not os.path.exists(imagem_path):
            logger.error(f"❌ Imagem não encontrada: {imagem_path}")
            return None, "Arquivo de imagem não encontrado"
        
        # 3. Verifica tamanho da imagem
        tamanho = os.path.getsize(imagem_path)
        if tamanho > 20 * 1024 * 1024:  # 20MB
            logger.warning(f"⚠️ Imagem muito grande: {tamanho/1024/1024:.2f}MB")
            return None, "Imagem muito grande (máx: 20MB)"
        
        # ====== CARREGA IMAGEM ======
        try:
            # Abre a imagem UMA ÚNICA VEZ
            img = Image.open(imagem_path)
            
            # Redimensiona se necessário (para evitar timeout)
            max_dimension = 2048  # 2048x2048 pixels
            if img.size[0] > max_dimension or img.size[1] > max_dimension:
                logger.info(f"📏 Redimensionando imagem de {img.size} para evitar timeout")
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
            # Converte para RGB se necessário
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
        except Exception as e:
            logger.error(f"❌ Erro ao abrir imagem: {e}")
            return None, f"Erro ao abrir imagem: {str(e)}"
        
        # ====== PREPARA PROMPT ======
        prompt = f"""
Você é um analista médico especialista. Analise esta imagem médica e forneça um diagnóstico detalhado.

CONTEXTO CLÍNICO:
{contexto_clinico}

Por favor, forneça um relatório estruturado com:
1. Descrição da imagem e qualidade técnica
2. Achados principais
3. Diagnóstico sugerido
4. Recomendações
5. Nível de urgência (baixa, média, alta, emergência)

Use linguagem médica apropriada mas clara. Seja objetivo e baseie-se apenas na imagem fornecida.
"""
        
        # ====== CHAMA GEMINI 2.5 FLASH ======
        try:
            # Modelos priorizando o 2.5 Flash
            modelos_tentar = [
                "gemini-2.5-flash",      # 🔥 PRIORIDADE MÁXIMA
                "gemini-2.5-pro",         # Versão Pro se disponível
                "gemini-2.0-flash-exp",   # Fallback
                "gemini-1.5-flash",       # Fallback estável
                "gemini-1.5-pro"          # Último fallback
            ]
            
            # Se tiver um modelo específico configurado, coloca no topo
            if _model_name and _model_name not in modelos_tentar:
                modelos_tentar.insert(0, _model_name)
            
            ultimo_erro = None
            
            for modelo in modelos_tentar:
                try:
                    logger.info(f"🤖 Tentando modelo: {modelo}")
                    model = genai.GenerativeModel(modelo)
                    
                    # Configurações otimizadas para 2.5 Flash
                    config = {
                        "temperature": 0.7,
                        "max_output_tokens": 2048,
                        "top_p": 0.95,
                        "top_k": 40
                    }
                    
                    response = model.generate_content(
                        [prompt, img],
                        generation_config=config
                    )
                    
                    if response and hasattr(response, 'text') and response.text:
                        resultado = response.text
                        logger.info(f"✅ Análise concluída com modelo {modelo}")
                        
                        # Tenta extrair diagnóstico estruturado
                        diagnostico = extrair_diagnostico_estruturado(resultado)
                        return diagnostico, None
                    else:
                        logger.warning(f"⚠️ Modelo {modelo} retornou resposta vazia")
                        
                except Exception as e:
                    ultimo_erro = e
                    logger.warning(f"⚠️ Modelo {modelo} falhou: {str(e)}")
                    continue
            
            # Se chegou aqui, todos os modelos falharam
            logger.error("❌ Todos os modelos falharam")
            return None, f"Todos os modelos falharam. Último erro: {str(ultimo_erro)}"
            
        except Exception as e:
            logger.error(f"❌ Erro ao chamar Gemini: {e}")
            logger.error(traceback.format_exc())
            return None, f"Erro na API Gemini: {str(e)}"
            
    except Exception as e:
        logger.error(f"❌ Erro geral na análise: {e}")
        logger.error(traceback.format_exc())
        return None, f"Erro interno: {str(e)}"

def extrair_diagnostico_estruturado(texto):
    """
    Extrai diagnóstico estruturado do texto do Gemini
    """
    try:
        # Tenta encontrar seções
        secoes = {
            "descricao": "",
            "achados": "",
            "diagnostico": "",
            "recomendacoes": "",
            "urgencia": ""
        }
        
        # Mapeia palavras-chave para seções
        mapeamento = {
            "descrição da imagem": "descricao",
            "qualidade técnica": "descricao",
            "achados principais": "achados",
            "diagnóstico sugerido": "diagnostico",
            "recomendações": "recomendacoes",
            "nível de urgência": "urgencia",
            "nivel de urgencia": "urgencia"
        }
        
        linhas = texto.split('\n')
        secao_atual = None
        
        for linha in linhas:
            linha_lower = linha.lower().strip()
            
            # Verifica se é um cabeçalho de seção
            for chave, valor in mapeamento.items():
                if chave in linha_lower:
                    secao_atual = valor
                    # Remove o cabeçalho da linha
                    linha = linha.split(':', 1)[-1].strip() if ':' in linha else linha
                    break
            
            # Adiciona à seção atual
            if secao_atual and linha:
                if secoes[secao_atual]:
                    secoes[secao_atual] += " " + linha
                else:
                    secoes[secao_atual] = linha
        
        # Se não encontrou seções, usa o texto completo
        if not any(secoes.values()):
            return {
                "diagnostico_completo": texto,
                "descricao": texto[:200] + "..." if len(texto) > 200 else texto
            }
        
        # Determina nível de urgência
        urgencia = secoes.get("urgencia", "").lower()
        nivel_urgencia = "media"
        if "emergência" in urgencia or "urgente" in urgencia or "alta" in urgencia:
            nivel_urgencia = "alta"
        elif "baixa" in urgencia:
            nivel_urgencia = "baixa"
        
        return {
            "descricao_imagem": secoes["descricao"].strip(),
            "achados_principais": secoes["achados"].strip(),
            "diagnostico_sugerido": secoes["diagnostico"].strip(),
            "recomendacoes": secoes["recomendacoes"].strip(),
            "nivel_urgencia": nivel_urgencia,
            "diagnostico_completo": texto
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao estruturar diagnóstico: {e}")
        return {"diagnostico_completo": texto}

def testar_conexao_gemini():
    """
    Função para testar se a API Gemini está funcionando
    Retorna: (success, message, available_models, used_model)
    """
    try:
        # Verifica se está configurado
        if not _gemini_available:
            return False, "Gemini não está disponível (configuração ausente)", [], None
        
        # Verifica chave API
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return False, "GEMINI_API_KEY não encontrada nas variáveis de ambiente", [], None
        
        # Testa com 2.5 Flash primeiro
        modelos_teste = [
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash"
        ]
        
        for modelo in modelos_teste:
            try:
                logger.info(f"🧪 Testando modelo: {modelo}")
                model = genai.GenerativeModel(modelo)
                response = model.generate_content("Responda apenas com 'OK' para confirmar conexão")
                
                if response and response.text:
                    # Lista modelos disponíveis
                    models = genai.list_models()
                    available = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
                    
                    return True, f"Conexão com Gemini estabelecida com sucesso usando {modelo}", available, modelo
                    
            except Exception as e:
                logger.warning(f"⚠️ Modelo {modelo} falhou no teste: {str(e)}")
                continue
        
        return False, "Nenhum modelo Gemini respondeu", [], None
            
    except Exception as e:
        return False, f"Erro ao testar Gemini: {str(e)}", [], None

def listar_modelos_disponiveis():
    """
    Lista todos os modelos Gemini disponíveis
    """
    try:
        if not _gemini_available:
            return []
        
        models = genai.list_models()
        available = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        return available
    except Exception as e:
        logger.error(f"❌ Erro ao listar modelos: {e}")
        return []
