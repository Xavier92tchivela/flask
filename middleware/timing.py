# middleware/timing.py
import time
from flask import request

class TimingMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        start = time.time()
        
        def custom_start_response(status, headers, exc_info=None):
            # Calcular tempo
            end = time.time()
            duration = (end - start) * 1000
            
            # Pegar informações da requisição
            path = environ.get('PATH_INFO', '')
            method = environ.get('REQUEST_METHOD', '')
            
            # Log da duração
            print(f"[TIMING] {method} {path} - {duration:.2f}ms - Status: {status}")
            
            # Adicionar header de tempo
            headers.append(('X-Response-Time', f'{duration:.2f}ms'))
            
            return start_response(status, headers, exc_info)
        
        return self.app(environ, custom_start_response)