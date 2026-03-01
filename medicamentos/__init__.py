# medicamentos/__init__.py
"""Pacote de medicamentos - Farmácia Virtual"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class FarmaciaVirtual:
    """Gerencia todos os medicamentos como uma farmácia"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent
        self.base_path = Path(base_path)
        self.cache = {}
        self.carregar_todos_medicamentos()
    
    def carregar_todos_medicamentos(self):
        """Carrega todos os medicamentos da farmácia"""
        try:
            # Carregar índice primeiro
            index_path = self.base_path / "index_medicamentos.json"
            if index_path.exists():
                with open(index_path, 'r', encoding='utf-8') as f:
                    self.cache['index'] = json.load(f)
            
            # Carregar todos os arquivos JSON
            for arquivo in self.base_path.rglob("*.json"):
                if arquivo.name != "index_medicamentos.json":
                    try:
                        with open(arquivo, 'r', encoding='utf-8') as f:
                            categoria = arquivo.stem
                            self.cache[categoria] = json.load(f)
                            logger.info(f"Carregado: {categoria}")
                    except Exception as e:
                        logger.error(f"Erro ao carregar {arquivo}: {e}")
            
            logger.info(f"Farmácia carregada com {len(self.cache)} categorias")
            
        except Exception as e:
            logger.error(f"Erro ao carregar farmácia: {e}")
    
    def buscar_medicamentos(self, doenca, condicoes_especiais=None):
        """Busca medicamentos para uma doença específica"""
        resultados = []
        condicoes = condicoes_especiais or {}
        
        # Mapear doença para arquivo
        mapa = {
            'malaria': 'malaria_nao_complicada',
            'malaria_grave': 'malaria_grave',
            'malaria_gestante': 'malaria_gestante',
            'pneumonia': 'pneumonia',
            'tuberculose': 'tuberculose',
            'febre_tifoide': 'febre_tifoide',
            'itu': 'infeccao_urinaria',
            'hipertensao': 'hipertensao',
            'diabetes': 'diabetes',
            'anemia': 'anemia',
            'dengue': 'dengue',
            'gravidez': 'prenatal'
        }
        
        arquivo = mapa.get(doenca)
        if arquivo and arquivo in self.cache:
            medicamentos = self.cache[arquivo]
            
            # Filtrar por condições especiais
            if condicoes.get('gestante'):
                medicamentos = [m for m in medicamentos if m.get('seguro_gestante', False)]
            
            if condicoes.get('crianca'):
                medicamentos = [m for m in medicamentos if m.get('pediatrico', False)]
            
            if condicoes.get('alergia_penicilina'):
                medicamentos = [m for m in medicamentos if not m.get('penicilinico', False)]
            
            resultados.extend(medicamentos)
        
        return resultados
    
    def buscar_combinacoes(self, doenca):
        """Busca combinações possíveis de medicamentos"""
        combinacoes_path = self.base_path / f"{doenca}_combinacoes.json"
        if combinacoes_path.exists():
            try:
                with open(combinacoes_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []

# Instância global da farmácia
farmacia = FarmaciaVirtual()