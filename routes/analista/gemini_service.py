"""Serviços de IA com Gemini para o módulo analista - VERSÃO AUTOCONFIGURÁVEL"""
import os
import logging
import traceback
import json
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from .file_utils import ensure_temp_folder, get_temp_folder

logger = logging.getLogger(__name__)

# ===== VARIÁVEIS GLOBAIS =====
_gemini_available = False
_model_name = None
_app = None
_api_key = None

# ===== FUNÇÃO DE AUTO-CONFIGURAÇÃO =====
def auto_configurar_gemini(force=False):
    """
    Auto-configura o Gemini verificando a chave API e modelos disponíveis
    Retorna: (disponivel, nome_modelo)
    """
    global _gemini_available, _model_name, _api_key
    
    print("\n" + "=" * 60)
    print("AUTO-CONFIGURANDO GEMINI")
    print("=" * 60)
    
    # 1. Busca a chave API
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY não encontrada nas variáveis de ambiente")
        _gemini_available = False
        _model_name = None
        return False, None
    
    _api_key = api_key
    print(f"✅ Chave API encontrada: {api_key[:10]}...{api_key[-4:]}")
    
    # 2. Configura a API
    try:
        genai.configure(api_key=api_key)
        print("✅ API Gemini configurada")
    except Exception as e:
        print(f"❌ Erro ao configurar API: {e}")
        _gemini_available = False
        return False, None
    
    # 3. Lista modelos disponíveis
    modelos_disponiveis = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos_disponiveis.append(m.name)
        print(f"📋 Modelos disponíveis: {modelos_disponiveis}")
    except Exception as e:
        print(f"⚠️ Não foi possível listar modelos: {e}")
    
    # 4. Testa modelos em ordem de preferência
    modelos_para_testar = [
        "gemini-2.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    
    for model_name in modelos_para_testar:
        # Verifica se o modelo está disponível
        if modelos_disponiveis and model_name not in modelos_disponiveis:
            print(f"  ⚠️ Modelo {model_name} não disponível")
            continue
        
        try:
            print(f"  🔄 Testando modelo: {model_name}")
            model = genai.GenerativeModel(model_name)
            
            # Teste rápido
            response = model.generate_content(
                "OK",
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=5
                )
            )
            
            if response and hasattr(response, 'text') and response.text:
                print(f"  ✅ SUCESSO! Modelo {model_name} respondeu: {response.text.strip()}")
                _gemini_available = True
                _model_name = model_name
                print("\n" + "=" * 60)
                print(f"✅ GEMINI CONFIGURADO COM SUCESSO!")
                print(f"   Modelo: {_model_name}")
                print("=" * 60 + "\n")
                return True, model_name
            else:
                print(f"  ❌ Modelo {model_name} respondeu vazio")
                
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                print(f"  ⚠️ Quota excedida para {model_name}")
            elif "not found" in error_msg.lower():
                print(f"  ⚠️ Modelo {model_name} não encontrado")
            else:
                print(f"  ❌ {model_name} falhou: {error_msg[:80]}")
            continue
    
    # 5. Se chegou aqui, nenhum modelo funcionou
    print("\n❌ NENHUM MODELO GEMINI FUNCIONOU")
    _gemini_available = False
    _model_name = None
    print("=" * 60 + "\n")
    return False, None

# ===== INICIALIZAÇÃO AUTOMÁTICA =====
# Quando o módulo é importado, tenta configurar automaticamente
auto_configurar_gemini()

# ===== FUNÇÕES EXPORTADAS =====
def set_gemini_config(gemini_available, MODEL_NAME, app):
    """Configura o serviço Gemini (mantido para compatibilidade)"""
    global _gemini_available, _model_name, _app
    
    # Se recebeu True, usa o valor recebido
    if gemini_available:
        _gemini_available = True
        _model_name = MODEL_NAME if MODEL_NAME else "gemini-2.5-flash"
        _app = app
        print(f"✅ Gemini configurado manualmente: {_model_name}")
    else:
        # Se recebeu False, tenta auto-configurar
        print("⚠️ Gemini não disponível via parâmetro - tentando auto-configuração...")
        disponivel, modelo = auto_configurar_gemini()
        if disponivel:
            _gemini_available = True
            _model_name = modelo
            _app = app
            print(f"✅ Gemini auto-configurado: {_model_name}")
        else:
            _gemini_available = False
            _model_name = None
            _app = app
            print("❌ Gemini não disponível")

def salvar_imagem_temporaria(file):
    """Salva imagem temporariamente para análise"""
    try:
        temp_dir = ensure_temp_folder()
        
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
        if not pedido_info:
            return "Informações do pedido não disponíveis."
        
        # Suporte para dict e tuple
        if isinstance(pedido_info, dict):
            tipo_exame = pedido_info.get('tipo_exame', 'Não especificado')
            descricao = pedido_info.get('descricao', 'Não informada')
            observacoes = pedido_info.get('observacoes', 'Nenhuma')
            urgencia = pedido_info.get('urgencia', 'normal')
            paciente_nome = pedido_info.get('paciente_nome', 'Não informado')
            data_nascimento = pedido_info.get('data_nascimento')
            genero = pedido_info.get('genero', '')
        else:
            tipo_exame = pedido_info[1] if len(pedido_info) > 1 else 'Não especificado'
            descricao = pedido_info[2] if len(pedido_info) > 2 else 'Não informada'
            observacoes = pedido_info[3] if len(pedido_info) > 3 else 'Nenhuma'
            urgencia = pedido_info[4] if len(pedido_info) > 4 else 'normal'
            paciente_nome = pedido_info[12] if len(pedido_info) > 12 else 'Não informado'
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
    Analisa imagem usando Gemini - AUTO-CONFIGURÁVEL
    Retorna: (resultado, erro)
    """
    global _gemini_available, _model_name, _api_key
    
    try:
        # ===== VERIFICA E AUTO-CONFIGURA SE NECESSÁRIO =====
        if not _gemini_available:
            logger.warning("⚠️ Gemini não disponível - tentando auto-configurar...")
            disponivel, modelo = auto_configurar_gemini()
            if not disponivel:
                return None, "API Gemini não configurada. Verifique a chave API."
            _gemini_available = True
            _model_name = modelo
        
        # ===== VERIFICA A IMAGEM =====
        if not os.path.exists(imagem_path):
            logger.error(f"❌ Imagem não encontrada: {imagem_path}")
            return None, "Arquivo de imagem não encontrado"
        
        tamanho = os.path.getsize(imagem_path)
        if tamanho > 20 * 1024 * 1024:
            logger.warning(f"⚠️ Imagem muito grande: {tamanho/1024/1024:.2f}MB")
            return None, "Imagem muito grande (máx: 20MB)"
        
        # ===== CARREGA IMAGEM =====
        try:
            img = Image.open(imagem_path)
            
            max_dimension = 2048
            if img.size[0] > max_dimension or img.size[1] > max_dimension:
                logger.info(f"📏 Redimensionando imagem de {img.size}")
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
        except Exception as e:
            logger.error(f"❌ Erro ao abrir imagem: {e}")
            return None, f"Erro ao abrir imagem: {str(e)}"
        
        # ===== PREPARA PROMPT =====
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
        
        # ===== CHAMA GEMINI =====
        try:
            # Usa o modelo que funcionou na auto-configuração
            model_name = _model_name or "gemini-2.5-flash"
            logger.info(f"🤖 Usando modelo: {model_name}")
            
            model = genai.GenerativeModel(model_name)
            
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
                logger.info(f"✅ Análise concluída com sucesso! Tamanho: {len(resultado)} caracteres")
                
                diagnostico = extrair_diagnostico_estruturado(resultado)
                return diagnostico, None
            else:
                logger.error("❌ Resposta vazia do Gemini")
                return None, "Resposta vazia do Gemini"
            
        except Exception as e:
            logger.error(f"❌ Erro ao chamar Gemini: {e}")
            logger.error(traceback.format_exc())
            return None, f"Erro na API Gemini: {str(e)}"
            
    except Exception as e:
        logger.error(f"❌ Erro geral na análise: {e}")
        logger.error(traceback.format_exc())
        return None, f"Erro interno: {str(e)}"

def extrair_diagnostico_estruturado(texto):
    """Extrai diagnóstico estruturado do texto do Gemini"""
    try:
        secoes = {
            "descricao": "",
            "achados": "",
            "diagnostico": "",
            "recomendacoes": "",
            "urgencia": ""
        }
        
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
            
            for chave, valor in mapeamento.items():
                if chave in linha_lower:
                    secao_atual = valor
                    linha = linha.split(':', 1)[-1].strip() if ':' in linha else linha
                    break
            
            if secao_atual and linha:
                if secoes[secao_atual]:
                    secoes[secao_atual] += " " + linha
                else:
                    secoes[secao_atual] = linha
        
        if not any(secoes.values()):
            return {"diagnostico_completo": texto}
        
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
    """Testa se a API Gemini está funcionando"""
    try:
        global _gemini_available, _model_name
        
        if not _gemini_available:
            auto_configurar_gemini()
        
        if not _gemini_available:
            return False, "Gemini não disponível", [], None
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return False, "GEMINI_API_KEY não encontrada", [], None
        
        model = genai.GenerativeModel(_model_name or "gemini-2.5-flash")
        response = model.generate_content("OK")
        
        if response and response.text:
            models = genai.list_models()
            available = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
            return True, f"Gemini funcionando com {_model_name}", available, _model_name
        
        return False, "Resposta vazia", [], None
            
    except Exception as e:
        return False, f"Erro: {str(e)}", [], None

def listar_modelos_disponiveis():
    """Lista todos os modelos Gemini disponíveis"""
    try:
        if not _gemini_available:
            auto_configurar_gemini()
        
        if not _gemini_available:
            return []
        
        models = genai.list_models()
        available = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        return available
    except Exception as e:
        logger.error(f"❌ Erro ao listar modelos: {e}")
        return []
