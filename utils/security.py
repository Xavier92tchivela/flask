from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
import logging
import base64

logger = logging.getLogger(__name__)
load_dotenv()

class SecurityManager:
    def __init__(self):
        key_str = os.environ.get('ENCRYPTION_KEY')
        
        if not key_str:
            self.key = Fernet.generate_key()
            print("\n" + "="*60)
            print("[SECURITY] NOVA CHAVE GERADA! Guarde com seguranca:")
            print("="*60)
            print(f"ENCRYPTION_KEY={self.key.decode()}")
            print("="*60)
            print("Adicione esta linha ao seu arquivo .env")
            print("="*60 + "\n")
        else:
            self.key = key_str.encode() if isinstance(key_str, str) else key_str
        
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data):
        """Criptografa dados - ACEITA STRING OU BYTES"""
        if data is None:
            return None
        
        # Se for string, converte para bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Se já for bytes, usa direto
        if isinstance(data, bytes):
            try:
                return self.cipher.encrypt(data)
            except Exception as e:
                logger.error(f"Erro ao criptografar: {e}")
                return data
        
        return None
    
    def decrypt(self, encrypted_data):
        """Descriptografa dados - VERSÃO CORRIGIDA"""
        if encrypted_data is None:
            return None
        
        # CASO 1: Já é bytes - tenta descriptografar
        if isinstance(encrypted_data, bytes):
            try:
                decrypted = self.cipher.decrypt(encrypted_data)
                return decrypted.decode('utf-8')
            except Exception as e:
                # Se não conseguir descriptografar, pode ser texto puro
                try:
                    return encrypted_data.decode('utf-8')
                except:
                    return str(encrypted_data)
        
        # CASO 2: É string - pode ser base64 ou texto puro
        if isinstance(encrypted_data, str):
            # Verifica se parece base64 (tamanho múltiplo de 4, caracteres válidos)
            if len(encrypted_data) % 4 == 0 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in encrypted_data):
                try:
                    # Tenta converter de base64 para bytes
                    data_bytes = base64.b64decode(encrypted_data)
                    decrypted = self.cipher.decrypt(data_bytes)
                    return decrypted.decode('utf-8')
                except:
                    pass
            
            # Se não conseguir, retorna a string original
            return encrypted_data
        
        # CASO 3: Outro tipo - converte para string
        return str(encrypted_data)


# Instância global
security = SecurityManager()