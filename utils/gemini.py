# utils/gemini.py
import google.generativeai as genai
import logging
import traceback

# Suprimir o FutureWarning (opcional)
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

PREFERRED_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash", 
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.5"
]

def configurar_gemini(api_key):
    """Configura e testa conexão com Gemini AI"""
    
    client = None
    gemini_available = False
    MODEL_NAME = None
    
    print("\n" + "=" * 60)
    print("INICIANDO CONFIGURAÇÃO DO GEMINI AI")
    print("=" * 60)
    
    if api_key and api_key.strip() and api_key.lower() != 'root':
        try:
            print(f"[CONECTANDO] Conectando à API Gemini...")
            print(f"   Chave API: {api_key[:10]}...{api_key[-4:]}")
            
            genai.configure(api_key=api_key)
            print("[OK] API Gemini configurada")
            
            print("[TESTE] Testando modelos...")
            
            for model_name in PREFERRED_MODELS:
                try:
                    print(f"   Tentando modelo: {model_name}")
                    
                    model = genai.GenerativeModel(model_name)
                    
                    response = model.generate_content(
                        "Responda apenas com a palavra 'CONECTADO'",
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=10
                        )
                    )
                    
                    if response and response.text:
                        resposta = response.text.strip()
                        print(f"   [SUCESSO] Modelo {model_name} respondeu: {resposta}")
                        
                        MODEL_NAME = model_name
                        gemini_available = True
                        
                        client = {
                            'configured': True,
                            'model_name': model_name,
                            'model': model,
                            'genai': genai
                        }
                        break
                    else:
                        print(f"   [AVISO] Resposta vazia de: {model_name}")
                        
                except Exception as model_error:
                    error_msg = str(model_error)
                    if "not found" in error_msg.lower():
                        print(f"   [INFO] Modelo {model_name} não disponível")
                    elif "quota" in error_msg.lower():
                        print(f"   [ERRO] Limite excedido para {model_name}")
                    else:
                        print(f"   [ERRO] {model_name} falhou: {error_msg[:100]}...")
                    continue
            
            if not gemini_available:
                print("\n[TENTANDO] Tentando modelo genérico...")
                try:
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content("Teste de conexão")
                    
                    if response and response.text:
                        MODEL_NAME = 'gemini-pro'
                        gemini_available = True
                        client = {
                            'configured': True,
                            'model_name': 'gemini-pro',
                            'model': model,
                            'genai': genai
                        }
                        print(f"   [SUCESSO] Conexão com modelo genérico: {MODEL_NAME}")
                    else:
                        print("   [ERRO] Resposta vazia do modelo genérico")
                        
                except Exception as generic_error:
                    print(f"   [ERRO] Modelo genérico também falhou: {generic_error}")
                    gemini_available = False
                    
        except Exception as e:
            print(f"[ERRO CRÍTICO] Erro geral ao configurar Gemini: {str(e)[:200]}")
            gemini_available = False
            logger.error(f"Erro Gemini: {e}")
            logger.error(traceback.format_exc())
    else:
        print("[AVISO] Chave API não configurada ou inválida")
        gemini_available = False

    print("\n" + "=" * 60)
    print(f"RESULTADO GEMINI:")
    print(f"  Disponível: {'SIM [OK]' if gemini_available else 'NÃO [ERRO]'}")
    print(f"  Modelo: {MODEL_NAME or 'Nenhum'}")
    print(f"  Cliente: {'Configurado' if client else 'Não configurado'}")
    print("=" * 60)
    
    return client, gemini_available, MODEL_NAME