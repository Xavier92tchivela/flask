# services/receita_service.py - VERSÃO CORRIGIDA
# Correção: Gera receitas APENAS com medicamentos específicos para o diagnóstico atual
# Formatação profissional e organizada

import os
import tempfile
import logging
from datetime import datetime
from io import BytesIO
import traceback
import json
import re

from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

# Importar funções de classificação
from utils.classificacoes import (
    classificar_peso,
    classificar_imc,
    calcular_dosagem_por_peso as calc_dose_util,
    interpretar_sinais_vitais
)

logger = logging.getLogger(__name__)

# ===== FUNÇÃO PARA LIMPAR FORMATAÇÃO MARKDOWN =====
def limpar_formatacao_markdown(texto):
    """
    Remove formatação Markdown de um texto para exibição limpa
    """
    if not texto or not isinstance(texto, str):
        return texto
    
    # Salvar uma cópia original para log
    original = texto[:200] if len(texto) > 200 else texto
    
    # Remover cabeçalhos (##, ###, etc)
    texto = re.sub(r'#{1,6}\s+', '', texto)
    
    # Remover negrito (**texto**)
    texto = re.sub(r'\*\*(.*?)\*\*', r'\1', texto)
    
    # Remover itálico (*texto*)
    texto = re.sub(r'\*(.*?)\*', r'\1', texto)
    
    # Converter marcadores de lista para bullet points
    texto = re.sub(r'^-\s+', '• ', texto, flags=re.MULTILINE)
    texto = re.sub(r'^\*\s+', '• ', texto, flags=re.MULTILINE)
    texto = re.sub(r'^\+\s+', '• ', texto, flags=re.MULTILINE)
    
    # Remover linhas horizontais (---, ***)
    texto = re.sub(r'^[-*]{3,}$', '', texto, flags=re.MULTILINE)
    
    # Remover blocos de código (```)
    texto = re.sub(r'```\w*\n', '', texto)
    texto = re.sub(r'```', '', texto)
    
    # Remover links [texto](url)
    texto = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', texto)
    
    # Remover imagens ![alt](url)
    texto = re.sub(r'!\[.*?\]\(.*?\)', '', texto)
    
    # Remover citações (> texto)
    texto = re.sub(r'^>\s+', '', texto, flags=re.MULTILINE)
    
    # Remover código inline (`texto`)
    texto = re.sub(r'`(.*?)`', r'\1', texto)
    
    # Remover linhas em branco excessivas (mais de 2)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    
    logger.debug(f"Formatação Markdown removida: original={original[:50]}... → limpo={texto[:50]}...")
    
    return texto.strip()


class ReceitaService:
    """Serviço para gerenciar receitas médicas com formatação profissional"""
    
    # ===== MEDICAMENTOS ORGANIZADOS POR CONDIÇÃO =====
    MEDICAMENTOS_POR_CONDICAO = {
        'cristaluria': [
            {
                'nome': 'Citrato de Potássio',
                'apresentacao': 'Comprimidos 10 mEq (1080 mg)',
                'posologia': '1 comprimido',
                'frequencia': '2 vezes ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Tomar com as refeições. Aumenta o pH urinário e inibe a formação de cristais de oxalato.',
                'dosagem_peso': '0.5-1 mEq/kg/dia'
            },
            {
                'nome': 'Hidratação Oral',
                'apresentacao': 'Água',
                'posologia': '2-3 litros por dia',
                'frequencia': 'Distribuído ao longo do dia',
                'duracao': 'Contínuo',
                'via': 'Oral',
                'quantidade': '90 litros (30 dias)',
                'observacoes': 'FUNDAMENTAL - aumentar ingestão de líquidos para diluir a urina e prevenir formação de cristais.',
                'dosagem_peso': '30-40 ml/kg/dia'
            },
            {
                'nome': 'Alopurinol',
                'apresentacao': 'Comprimidos 300 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'Reduz a excreção de oxalato urinário em casos de hiperoxalúria.',
                'dosagem_peso': '5-10 mg/kg/dia'
            },
            {
                'nome': 'Piridoxina (Vitamina B6)',
                'apresentacao': 'Comprimidos 100 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'Reduz a produção endógena de oxalato em pacientes com hiperoxalúria primária.',
                'dosagem_peso': '2-5 mg/kg/dia'
            },
            {
                'nome': 'Dieta Pobre em Oxalato',
                'apresentacao': 'Orientação nutricional',
                'posologia': 'Evitar espinafre, chocolate, nozes, beterraba, chá preto',
                'frequencia': 'Diariamente',
                'duracao': 'Contínuo',
                'via': 'Orientação',
                'quantidade': 'N/A',
                'observacoes': 'Reduzir alimentos ricos em oxalato e aumentar ingestão de cálcio na dieta.',
                'dosagem_peso': 'N/A'
            }
        ],
        
        'hipertensao': [
            {
                'nome': 'Hidroclorotiazida',
                'apresentacao': 'Comprimidos 25 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Tomar pela manhã. Tiazídico - primeira linha para hipertensão arterial.',
                'dosagem_peso': '12.5-25 mg/dia'
            },
            {
                'nome': 'Losartana Potássica',
                'apresentacao': 'Comprimidos 50 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'BRA - primeira linha para hipertensão, especialmente em diabéticos.',
                'dosagem_peso': '50-100 mg/dia'
            },
            {
                'nome': 'Anlodipino',
                'apresentacao': 'Comprimidos 5 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'BCC - pode ser associado se necessário.',
                'dosagem_peso': '5-10 mg/dia'
            }
        ],
        
        'diabetes': [
            {
                'nome': 'Metformina',
                'apresentacao': 'Comprimidos 500 mg',
                'posologia': '1 comprimido',
                'frequencia': '3 vezes ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'PRIMEIRA LINHA ABSOLUTA para Diabetes Mellitus tipo 2. Tomar com as refeições.',
                'dosagem_peso': '1500-2000 mg/dia'
            },
            {
                'nome': 'Gliclazida',
                'apresentacao': 'Comprimidos 60 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Sulfonilureia se metformina não for suficiente.',
                'dosagem_peso': '30-120 mg/dia'
            },
            {
                'nome': 'Sitagliptina',
                'apresentacao': 'Comprimidos 100 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Inibidor DPP-4, baixo risco de hipoglicemia.'
            }
        ],
        
        'infeccao_urinaria': [
            {
                'nome': 'Fosfomicina Trometamol',
                'apresentacao': 'Sachê 3 g',
                'posologia': '1 sachê',
                'frequencia': 'Dose única',
                'duracao': '1 dia',
                'via': 'Oral',
                'quantidade': '1 sachê',
                'observacoes': 'Primeira linha para cistite não complicada. Tomar em jejum.'
            },
            {
                'nome': 'Nitrofurantoína',
                'apresentacao': 'Comprimidos 100 mg',
                'posologia': '1 comprimido',
                'frequencia': '12/12 horas',
                'duracao': '5 dias',
                'via': 'Oral',
                'quantidade': '10 comprimidos',
                'observacoes': 'Alternativa de primeira linha para infecção urinária.',
                'dosagem_peso': '5-7 mg/kg/dia'
            }
        ],
        
        'dengue': [
            {
                'nome': 'Paracetamol',
                'apresentacao': 'Comprimidos 500 mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas',
                'duracao': 'Durante febre',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'ÚNICO ANALGÉSICO SEGURO - NÃO USAR AAS OU AINES.',
                'dosagem_peso': '10-15 mg/kg/dose'
            },
            {
                'nome': 'Dipirona',
                'apresentacao': 'Comprimidos 500 mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas se dor intensa',
                'duracao': 'Durante dor',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Alternativa para dor, se necessário.',
                'dosagem_peso': '10-20 mg/kg/dose'
            },
            {
                'nome': 'Hidratação Oral',
                'apresentacao': 'Soro de reidratação oral',
                'posologia': '60-80 ml/kg/dia',
                'frequencia': 'Contínua',
                'duracao': 'ATÉ MELHORA',
                'via': 'Oral',
                'quantidade': '6 litros',
                'observacoes': 'FUNDAMENTAL - base do tratamento da dengue.',
                'dosagem_peso': '60-80 ml/kg/dia'
            }
        ],
        
        'malaria': [
            {
                'nome': 'Artemeter + Lumefantrina (ACT)',
                'apresentacao': 'Comprimidos 20/120 mg',
                'posologia': '4 comprimidos por dose',
                'frequencia': '2 vezes ao dia',
                'duracao': '3 dias',
                'via': 'Oral',
                'quantidade': '24 comprimidos',
                'observacoes': 'Terapia Combinada à Base de Artemisinina - primeira linha OMS.',
                'dosagem_peso': '1.5-2.5 mg/kg/dose'
            },
            {
                'nome': 'Primaquina',
                'apresentacao': 'Comprimidos 15 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '14 dias',
                'via': 'Oral',
                'quantidade': '14 comprimidos',
                'observacoes': 'APÓS teste G6PD - para eliminar formas hepáticas.',
                'dosagem_peso': '0.5 mg/kg/dia'
            }
        ],
        
        'pneumonia': [
            {
                'nome': 'Amoxicilina',
                'apresentacao': 'Comprimidos 500 mg',
                'posologia': '1 comprimido',
                'frequencia': '8/8 horas',
                'duracao': '10 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Primeira linha para pneumonia comunitária.',
                'dosagem_peso': '50 mg/kg/dia'
            },
            {
                'nome': 'Azitromicina',
                'apresentacao': 'Comprimidos 500 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '5 dias',
                'via': 'Oral',
                'quantidade': '5 comprimidos',
                'observacoes': 'Para cobertura de atípicos.',
                'dosagem_peso': '10 mg/kg/dia'
            }
        ],
        
        'anemia': [
            {
                'nome': 'Sulfato Ferroso',
                'apresentacao': 'Comprimidos 300 mg',
                'posologia': '1 comprimido',
                'frequencia': '2 vezes ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Primeira linha para anemia ferropriva. Tomar com suco cítrico.',
                'dosagem_peso': '3-5 mg/kg/dia'
            },
            {
                'nome': 'Ácido Fólico',
                'apresentacao': 'Comprimidos 5 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'Associar ao ferro no tratamento da anemia.'
            }
        ],
        
        'gravidez': [
            {
                'nome': 'Sulfato Ferroso',
                'apresentacao': 'Comprimidos 300 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': 'ATÉ O PARTO',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Suplementação obrigatória na gestação.'
            },
            {
                'nome': 'Ácido Fólico',
                'apresentacao': 'Comprimidos 5 mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': 'ATÉ O PARTO',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Prevenção de defeitos do tubo neural.'
            }
        ]
    }
    
    # Medicamentos de suporte (apenas quando realmente necessário)
    MEDICAMENTOS_SUPORTE = [
        {
            'nome': 'Paracetamol',
            'apresentacao': 'Comprimidos 500 mg',
            'posologia': '1-2 comprimidos',
            'frequencia': '6/6 horas se febre ou dor',
            'duracao': 'Conforme necessidade',
            'via': 'Oral',
            'quantidade': '20 comprimidos',
            'observacoes': 'Controle da dor e febre.',
            'dosagem_peso': '10-15 mg/kg/dose'
        },
        {
            'nome': 'Dipirona',
            'apresentacao': 'Comprimidos 500 mg',
            'posologia': '1-2 comprimidos',
            'frequencia': '6/6 horas se dor intensa',
            'duracao': 'Conforme necessidade',
            'via': 'Oral',
            'quantidade': '20 comprimidos',
            'observacoes': 'Alternativa para dor.',
            'dosagem_peso': '10-20 mg/kg/dose'
        }
    ]
    
    MAPEAMENTO_DOENCAS = {
        'malária': 'malaria',
        'malaria': 'malaria',
        'plasmodium': 'malaria',
        'vivax': 'malaria',
        'falciparum': 'malaria',
        'febre tifoide': 'febre_tifoide',
        'febre tifóide': 'febre_tifoide',
        'salmonella': 'febre_tifoide',
        'pneumonia': 'pneumonia',
        'infiltrado pulmonar': 'pneumonia',
        'tuberculose': 'tuberculose',
        'tb pulmonar': 'tuberculose',
        'infeccao urinaria': 'infeccao_urinaria',
        'itu': 'infeccao_urinaria',
        'cistite': 'infeccao_urinaria',
        'hipertensao': 'hipertensao',
        'pressao alta': 'hipertensao',
        'has': 'hipertensao',
        'diabetes': 'diabetes',
        'dm2': 'diabetes',
        'anemia': 'anemia',
        'hemoglobina baixa': 'anemia',
        'ferropriva': 'anemia',
        'gravidez': 'gravidez',
        'gestante': 'gravidez',
        'prenatal': 'gravidez',
        'pré-natal': 'gravidez',
        'dengue': 'dengue',
        'arbovirose': 'dengue',
        
        # Palavras-chave para cristalúria
        'cristaluria': 'cristaluria',
        'cristalúria': 'cristaluria',
        'oxalato': 'cristaluria',
        'oxalato de cálcio': 'cristaluria',
        'cristais': 'cristaluria',
        'cristais na urina': 'cristaluria',
        'cristalúria por oxalato': 'cristaluria',
        'calculos renais': 'cristaluria',
        'cálculos renais': 'cristaluria',
        'litíase': 'cristaluria',
        'litíase renal': 'cristaluria',
        'pedra nos rins': 'cristaluria',
        'hiperoxalúria': 'cristaluria',
        'hipercalciúria': 'cristaluria',
        'urina concentrada': 'cristaluria',
        'sedimento urinário': 'cristaluria'
    }
    
    def __init__(self, mysql, app, gemini_available=False, MODEL_NAME=None):
        self.mysql = mysql
        self.app = app
        self.gemini_available = gemini_available
        self.MODEL_NAME = MODEL_NAME or "gemini-2.5-flash"
        
        if gemini_available:
            try:
                import google.generativeai as genai
                self.genai = genai
                logger.info(f"Gemini AI configurado com modelo: {self.MODEL_NAME}")
            except ImportError:
                self.gemini_available = False
                self.genai = None
                logger.warning("Google Generative AI não está instalado")
        else:
            self.genai = None
    
    def execute_query(self, query, params=None, fetch=False, one=False):
        try:
            cur = self.mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                if one:
                    return result[0] if result else None
                return result
            else:
                self.mysql.connection.commit()
                cur.close()
                return True
        except Exception as e:
            self.mysql.connection.rollback()
            logger.error(f"Database error in ReceitaService: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            logger.error(traceback.format_exc())
            return None
    
    def _extrair_palavras_chave(self, diagnostico, sintomas=None, sinais_vitais=None):
        """Extrai condições APENAS do diagnóstico atual"""
        texto_completo = diagnostico.lower() if diagnostico else ""
        
        if sintomas:
            if isinstance(sintomas, str):
                texto_completo += " " + sintomas.lower()
            elif isinstance(sintomas, list):
                for sintoma in sintomas:
                    texto_completo += " " + sintoma.lower()
            elif isinstance(sintomas, dict):
                for key, value in sintomas.items():
                    texto_completo += " " + str(value).lower()
        
        if sinais_vitais:
            if isinstance(sinais_vitais, dict):
                for key, value in sinais_vitais.items():
                    if value:
                        texto_completo += " " + str(value).lower()
        
        condicoes_encontradas = []
        for palavra, doenca in self.MAPEAMENTO_DOENCAS.items():
            if palavra in texto_completo:
                if doenca not in condicoes_encontradas:
                    condicoes_encontradas.append(doenca)
        
        logger.info(f"Condições identificadas no diagnóstico ATUAL: {condicoes_encontradas}")
        return condicoes_encontradas
    
    def _extrair_sintomas_estruturados(self, sintomas):
        if not sintomas:
            return []
        
        if isinstance(sintomas, list):
            return sintomas
        elif isinstance(sintomas, str):
            try:
                sintomas_json = json.loads(sintomas)
                if isinstance(sintomas_json, list):
                    return sintomas_json
                elif isinstance(sintomas_json, dict):
                    return [f"{k}: {v}" for k, v in sintomas_json.items()]
            except:
                return [s.strip() for s in sintomas.split(',') if s.strip()]
        elif isinstance(sintomas, dict):
            return [f"{k}: {v}" for k, v in sintomas.items()]
        
        return []
    
    def _buscar_sinais_vitais_consulta(self, consulta_id):
        """Busca os sinais vitais mais recentes da consulta no banco de dados"""
        try:
            query = """
                SELECT 
                    pressao_arterial,
                    frequencia_cardiaca,
                    frequencia_respiratoria,
                    temperatura,
                    saturacao_oxigenio,
                    glicemia,
                    peso,
                    data_afericao,
                    observacoes
                FROM sinais_vitais 
                WHERE consulta_id = %s 
                ORDER BY data_afericao DESC 
                LIMIT 1
            """
            resultado = self.execute_query(query, (consulta_id,), fetch=True, one=True)
            
            if resultado:
                sinais = {
                    'pressao_arterial': resultado[0],
                    'frequencia_cardiaca': resultado[1],
                    'frequencia_respiratoria': resultado[2],
                    'temperatura': float(resultado[3]) if resultado[3] else None,
                    'saturacao_oxigenio': resultado[4],
                    'glicemia': resultado[5],
                    'peso': float(resultado[6]) if resultado[6] else None,
                    'data_afericao': resultado[7].strftime('%d/%m/%Y %H:%M') if resultado[7] else None,
                    'observacoes': resultado[8] or ''
                }
                
                # Usar função de classificação
                try:
                    classificacoes = interpretar_sinais_vitais(sinais)
                    sinais.update(classificacoes)
                except Exception as e:
                    logger.error(f"Erro ao classificar sinais: {e}")
                
                logger.info(f"Sinais vitais encontrados: peso={sinais['peso']}")
                return sinais
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar sinais vitais: {e}")
            return None
    
    def _formatar_sinais_vitais_texto(self, sinais_vitais):
        if not sinais_vitais:
            return "Não informados"
        
        texto = []
        if sinais_vitais.get('pressao_arterial'):
            texto.append(f"Pressão Arterial: {sinais_vitais['pressao_arterial']}")
        if sinais_vitais.get('frequencia_cardiaca'):
            texto.append(f"Frequência Cardíaca: {sinais_vitais['frequencia_cardiaca']} bpm")
        if sinais_vitais.get('frequencia_respiratoria'):
            texto.append(f"Frequência Respiratória: {sinais_vitais['frequencia_respiratoria']} rpm")
        if sinais_vitais.get('temperatura'):
            texto.append(f"Temperatura: {sinais_vitais['temperatura']} °C")
        if sinais_vitais.get('saturacao_oxigenio'):
            texto.append(f"Saturação O2: {sinais_vitais['saturacao_oxigenio']}%")
        if sinais_vitais.get('glicemia'):
            texto.append(f"Glicemia: {sinais_vitais['glicemia']} mg/dL")
        if sinais_vitais.get('peso'):
            texto.append(f"Peso: {sinais_vitais['peso']} kg")
        if sinais_vitais.get('data_afericao'):
            texto.append(f"Data da Aferição: {sinais_vitais['data_afericao']}")
        if sinais_vitais.get('observacoes'):
            texto.append(f"Obs: {sinais_vitais['observacoes']}")
        
        return "\n".join(texto) if texto else "Não informados"
    
    def _calcular_dosagem_por_peso(self, medicamento, peso):
        """Calcula a dosagem recomendada baseada no peso do paciente"""
        if not peso or not medicamento.get('dosagem_peso'):
            return None
        
        try:
            peso_float = float(peso)
            
            # Extrair a faixa de dosagem do texto
            dosagem_texto = medicamento['dosagem_peso']
            
            # Procurar padrões como "10-15mg/kg" ou "50mg/kg"
            padrao = r'(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*mg/kg'
            match = re.search(padrao, dosagem_texto.lower())
            
            if match:
                min_dose = float(match.group(1))
                max_dose = float(match.group(2)) if match.group(2) else min_dose
                
                # Usar a dose média para cálculo
                dose_media = (min_dose + max_dose) / 2
                
                # Usar a função do utils
                try:
                    resultado = calc_dose_util(peso_float, dose_media, medicamento['nome'])
                    if resultado:
                        return f"{resultado['dose_total']} mg (baseado em {dose_media} mg/kg × {peso_float} kg)"
                except:
                    # Fallback se a função do utils falhar
                    dose_total = round(peso_float * dose_media)
                    if min_dose != max_dose:
                        return f"{dose_total} mg (faixa recomendada: {round(peso_float * min_dose)}-{round(peso_float * max_dose)} mg)"
                    else:
                        return f"{dose_total} mg (baseado em {dose_media} mg/kg × {peso_float} kg)"
            
            return None
        except Exception as e:
            logger.error(f"Erro ao calcular dosagem: {e}")
            return None
    
    # ===== NOVA FUNÇÃO - GERA PRESCRIÇÃO APENAS PARA O DIAGNÓSTICO ATUAL =====
    def _gerar_prescricao_especifica(self, condicoes, tem_gravidez=False, sinais_vitais=None):
        """
        Gera prescrição APENAS para as condições identificadas no diagnóstico atual
        SEM misturar com outras condições pré-existentes
        """
        try:
            if not condicoes:
                return self._gerar_prescricao_generica(sinais_vitais)
            
            prescricao = []
            medicamentos_adicionados = set()
            peso = sinais_vitais.get('peso') if sinais_vitais else None
            
            # MAPEAMENTO EXPLÍCITO de quais medicamentos pertencem a cada condição
            # Isso garante que não haja mistura de condições
            medicamentos_permitidos_por_condicao = {
                'cristaluria': ['Citrato de Potássio', 'Hidratação Oral', 'Alopurinol', 'Piridoxina (Vitamina B6)', 'Dieta Pobre em Oxalato'],
                'hipertensao': ['Hidroclorotiazida', 'Losartana Potássica', 'Anlodipino'],
                'diabetes': ['Metformina', 'Gliclazida', 'Sitagliptina'],
                'infeccao_urinaria': ['Fosfomicina Trometamol', 'Nitrofurantoína'],
                'dengue': ['Paracetamol', 'Dipirona', 'Hidratação Oral'],
                'malaria': ['Artemeter + Lumefantrina (ACT)', 'Primaquina'],
                'pneumonia': ['Amoxicilina', 'Azitromicina'],
                'anemia': ['Sulfato Ferroso', 'Ácido Fólico'],
                'gravidez': ['Sulfato Ferroso', 'Ácido Fólico']
            }
            
            # Coletar todos os medicamentos permitidos para as condições atuais
            medicamentos_permitidos = []
            for condicao in condicoes:
                if condicao in medicamentos_permitidos_por_condicao:
                    medicamentos_permitidos.extend(medicamentos_permitidos_por_condicao[condicao])
            
            logger.info(f"Condições atuais: {condicoes}")
            logger.info(f"Medicamentos PERMITIDOS: {medicamentos_permitidos}")
            
            # Destacar o peso no início
            if peso:
                nota_peso = f"NOTA: Prescrição baseada no peso do paciente: {peso} kg"
                prescricao.append(nota_peso)
                prescricao.append("")
            
            # Para cada condição identificada, adicionar APENAS seus medicamentos específicos
            for condicao in condicoes:
                if condicao in self.MEDICAMENTOS_POR_CONDICAO:
                    medicamentos = self.MEDICAMENTOS_POR_CONDICAO[condicao]
                    
                    logger.info(f"Adicionando medicamentos para condição: {condicao}")
                    
                    for med in medicamentos:
                        # VERIFICAÇÃO CRÍTICA: Só adiciona se o medicamento for permitido para esta condição
                        if med['nome'] in medicamentos_permitidos and med['nome'] not in medicamentos_adicionados:
                            # Formatar o medicamento
                            med_formatado = self._formatar_medicamento(med, tem_gravidez, sinais_vitais)
                            prescricao.append(med_formatado)
                            medicamentos_adicionados.add(med['nome'])
                            
                            # Adicionar uma linha em branco entre medicamentos
                            prescricao.append("")
            
            # Se ainda não há medicamentos, usar medicamentos de suporte (apenas se estiverem na lista permitida)
            if len(medicamentos_adicionados) < 2:
                logger.warning("Poucos medicamentos específicos, verificando suporte")
                for med in self.MEDICAMENTOS_SUPORTE:
                    # Só adiciona medicamentos de suporte se fizerem sentido para a condição
                    if 'febre' in str(condicoes).lower() or 'dor' in str(condicoes).lower():
                        if med['nome'] not in medicamentos_adicionados:
                            med_formatado = self._formatar_medicamento(med, tem_gravidez, sinais_vitais)
                            prescricao.append(med_formatado)
                            medicamentos_adicionados.add(med['nome'])
                            prescricao.append("")
                            if len(medicamentos_adicionados) >= 3:
                                break
            
            if not prescricao:
                return self._gerar_prescricao_generica(sinais_vitais)
            
            # Remover a última linha em branco se existir
            if prescricao and prescricao[-1] == "":
                prescricao.pop()
            
            return "\n".join(prescricao)
            
        except Exception as e:
            logger.error(f"Erro ao gerar prescrição específica: {e}")
            return self._gerar_prescricao_generica(sinais_vitais)
    
    def _formatar_medicamento(self, med, tem_gravidez=False, sinais_vitais=None):
        """Formata um medicamento de forma limpa e profissional"""
        linhas = []
        
        # Nome do medicamento em negrito visual
        linhas.append(f"{med['nome']}")
        
        # Apresentação
        if med.get('apresentacao'):
            linhas.append(f"  Apresentação: {med['apresentacao']}")
        
        # Posologia
        if med.get('posologia'):
            linhas.append(f"  Posologia: {med['posologia']}")
        
        # Frequência
        if med.get('frequencia'):
            linhas.append(f"  Frequência: {med['frequencia']}")
        
        # Duração
        if med.get('duracao'):
            linhas.append(f"  Duração: {med['duracao']}")
        
        # Via
        if med.get('via'):
            linhas.append(f"  Via: {med['via']}")
        
        # Quantidade
        if med.get('quantidade'):
            linhas.append(f"  Quantidade: {med['quantidade']}")
        
        # Calcular e mostrar dosagem baseada no peso
        if sinais_vitais and sinais_vitais.get('peso'):
            peso = float(sinais_vitais['peso'])
            dosagem_calculada = self._calcular_dosagem_por_peso(med, peso)
            if dosagem_calculada:
                linhas.append(f"  Dosagem calculada: {dosagem_calculada}")
        
        # Observações
        if med.get('observacoes'):
            linhas.append(f"  Observações: {med['observacoes']}")
        
        return "\n".join(linhas)
    
    def _gerar_recomendacoes_especificas(self, condicoes, tem_gravidez=False, sinais_vitais=None):
        """Gera recomendações específicas para as condições identificadas"""
        recomendacoes = []
        peso = sinais_vitais.get('peso') if sinais_vitais else None
        
        # Recomendação específica sobre o peso
        if peso:
            if peso < 50:
                recomendacoes.append(f"• ATENÇÃO: Paciente com peso baixo ({peso} kg). Observar sinais de superdosagem e ajustar conforme resposta.")
            elif peso > 100:
                recomendacoes.append(f"• ATENÇÃO: Paciente com peso elevado ({peso} kg). Considerar dose máxima das faixas terapêuticas e monitorar resposta.")
            else:
                recomendacoes.append(f"• Peso do paciente: {peso} kg - dosagens calculadas conforme faixa recomendada.")
        
        recomendacoes.append("• Seguir rigorosamente a posologia dos medicamentos prescritos.")
        recomendacoes.append("• Manter-se bem hidratado, ingerindo bastante líquidos.")
        recomendacoes.append("• Repousar adequadamente para auxiliar na recuperação.")
        recomendacoes.append("• Evitar automedicação e bebidas alcoólicas durante o tratamento.")
        
        # Recomendações específicas por condição
        for condicao in condicoes:
            if condicao == 'cristaluria':
                recomendacoes.append("")
                recomendacoes.append("• 💧 HIDRATAÇÃO: Aumentar ingestão de água para mínimo 2-3 litros por dia.")
                recomendacoes.append("• 🥗 DIETA: Evitar alimentos ricos em oxalato: espinafre, chocolate, nozes, beterraba, chá preto.")
                recomendacoes.append("• 🥛 Manter dieta equilibrada com ingestão adequada de cálcio.")
                recomendacoes.append("• 📊 Monitorar pH urinário - manter entre 6.5 e 7.0.")
                recomendacoes.append("• ☀️ Evitar desidratação, especialmente em dias quentes.")
            elif condicao == 'hipertensao':
                recomendacoes.append("")
                recomendacoes.append("• 🧂 Reduzir consumo de sal e alimentos processados.")
                recomendacoes.append("• 🏃 Praticar atividade física regular (caminhada 30 min/dia).")
                recomendacoes.append("• 📉 Monitorar pressão arterial regularmente.")
            elif condicao == 'diabetes':
                recomendacoes.append("")
                recomendacoes.append("• 🍎 Manter dieta equilibrada, evitar açúcares e carboidratos simples.")
                recomendacoes.append("• 📈 Monitorar glicemia conforme orientação médica.")
                recomendacoes.append("• 🏃 Praticar atividade física regular.")
            elif condicao == 'dengue':
                recomendacoes.append("")
                recomendacoes.append("• 🚫 NÃO USAR AAS, ibuprofeno ou outros anti-inflamatórios.")
                recomendacoes.append("• 💧 HIDRATAÇÃO INTENSIVA - fundamental para recuperação.")
                recomendacoes.append("• 🩸 Monitorar sinais de sangramento (gengivas, nariz, manchas na pele).")
        
        recomendacoes.append("")
        recomendacoes.append("• ⚠️ SINAIS DE ALERTA - PROCURAR URGÊNCIA SE:")
        recomendacoes.append("    • Febre persistente ou alta (>24h sem melhora)")
        recomendacoes.append("    • Falta de ar ou dificuldade para respirar")
        recomendacoes.append("    • Confusão mental, sonolência excessiva ou desmaios")
        recomendacoes.append("    • Sangramentos incomuns (gengivas, nariz, urina escura)")
        recomendacoes.append("    • Vômitos persistentes")
        
        recomendacoes.append("")
        recomendacoes.append("• 📅 Retorno: Agendar em 7-10 dias ou antes se necessário.")
        
        return "\n".join(recomendacoes)
    
    def _gerar_prescricao_generica(self, sinais_vitais=None):
        """Gera prescrição genérica quando não há condições identificadas"""
        prescricao = []
        peso = sinais_vitais.get('peso') if sinais_vitais else None
        
        if peso:
            prescricao.append(f"NOTA: Prescrição baseada no peso do paciente: {peso} kg")
            prescricao.append("")
        
        # Usar apenas medicamentos de suporte básicos
        for med in self.MEDICAMENTOS_SUPORTE[:2]:  # Apenas os mais básicos
            prescricao.append(self._formatar_medicamento(med, False, sinais_vitais))
            prescricao.append("")
        
        return "\n".join(prescricao)
    
    # ===== FUNÇÃO PRINCIPAL CORRIGIDA =====
    def gerar_receita_ia(self, diagnostico, paciente_info, medico_info, sintomas=None, consulta_id=None):
        """
        Gera receita médica usando Gemini APENAS para o diagnóstico atual
        """
        try:
            # Buscar sinais vitais da consulta (registrados pelo enfermeiro)
            sinais_vitais = None
            if consulta_id:
                sinais_vitais = self._buscar_sinais_vitais_consulta(consulta_id)
                if sinais_vitais:
                    peso = sinais_vitais.get('peso')
                    logger.info(f"Sinais vitais encontrados para consulta {consulta_id}: peso={peso}")
                    if peso:
                        logger.info(f"✅ Peso do paciente: {peso} kg - será considerado nas dosagens")
                else:
                    logger.info(f"Nenhum sinal vital encontrado para consulta {consulta_id}")
            
            if not self.gemini_available or not self.genai:
                logger.error("API Gemini não configurada, usando geração manual")
                return self._gerar_receita_manual(diagnostico, paciente_info, medico_info, sintomas, sinais_vitais)
            
            logger.info("=" * 60)
            logger.info(f"GERANDO RECEITA COM GEMINI {self.MODEL_NAME}")
            logger.info("=" * 60)
            
            if not diagnostico:
                return None, "Diagnóstico vazio"
            
            if not paciente_info:
                paciente_info = {'nome': 'Não informado', 'idade': '', 'genero': ''}
            
            if not medico_info:
                medico_info = {'nome': 'Dr. Não Informado', 'especialidade': 'Clínico Geral', 'crm': 'CRM não informado'}
            
            sintomas_lista = self._extrair_sintomas_estruturados(sintomas)
            condicoes = self._extrair_palavras_chave(diagnostico, sintomas_lista, sinais_vitais)
            
            logger.info(f"Condições identificadas: {condicoes}")
            
            try:
                prompt = self._criar_prompt_receita(
                    diagnostico, paciente_info, medico_info, 
                    sintomas_lista, condicoes, sinais_vitais
                )
                
                model = self.genai.GenerativeModel(self.MODEL_NAME)
                generation_config = {
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "max_output_tokens": 4096,
                }
                
                response = model.generate_content(prompt, generation_config=generation_config)
                
                if response and hasattr(response, 'text'):
                    receita = response.text
                else:
                    # Fallback para geração manual
                    prescricao = self._gerar_prescricao_especifica(condicoes, False, sinais_vitais)
                    recomendacoes = self._gerar_recomendacoes_especificas(condicoes, False, sinais_vitais)
                    
                    receita = self._criar_receita_formatada(
                        diagnostico, paciente_info, medico_info,
                        prescricao, recomendacoes, sinais_vitais
                    )
                
            except Exception as e:
                logger.warning(f"Erro ao usar Gemini, usando fallback: {e}")
                prescricao = self._gerar_prescricao_especifica(condicoes, False, sinais_vitais)
                recomendacoes = self._gerar_recomendacoes_especificas(condicoes, False, sinais_vitais)
                
                receita = self._criar_receita_formatada(
                    diagnostico, paciente_info, medico_info,
                    prescricao, recomendacoes, sinais_vitais
                )
            
            partes = self._extrair_partes_receita(receita)
            
            return {
                'receita_completa': receita,
                'prescricao': partes['prescricao'],
                'recomendacoes': partes['recomendacoes'],
                'diagnostico_resumo': diagnostico,
                'sintomas_considerados': sintomas_lista,
                'sinais_vitais_considerados': sinais_vitais,
                'condicoes_identificadas': condicoes
            }, None
            
        except Exception as e:
            logger.error(f"Erro ao gerar receita: {e}")
            logger.error(traceback.format_exc())
            return self._gerar_receita_manual(diagnostico, paciente_info, medico_info, sintomas, sinais_vitais)
    
    def _gerar_receita_manual(self, diagnostico, paciente_info, medico_info, sintomas=None, sinais_vitais=None):
        """Gera receita manualmente APENAS para o diagnóstico atual"""
        try:
            sintomas_lista = self._extrair_sintomas_estruturados(sintomas)
            condicoes = self._extrair_palavras_chave(diagnostico, sintomas_lista, sinais_vitais)
            
            logger.info(f"Gerando receita manual para condições: {condicoes}")
            
            # Usar a função específica para gerar APENAS medicamentos da condição atual
            prescricao = self._gerar_prescricao_especifica(condicoes, False, sinais_vitais)
            recomendacoes = self._gerar_recomendacoes_especificas(condicoes, False, sinais_vitais)
            
            receita_completa = self._criar_receita_formatada(
                diagnostico, paciente_info, medico_info,
                prescricao, recomendacoes, sinais_vitais
            )
            
            partes = self._extrair_partes_receita(receita_completa)
            
            return {
                'receita_completa': receita_completa,
                'prescricao': partes['prescricao'],
                'recomendacoes': partes['recomendacoes'],
                'diagnostico_resumo': diagnostico,
                'sintomas_considerados': sintomas_lista,
                'sinais_vitais_considerados': sinais_vitais,
                'condicoes_identificadas': condicoes
            }, None
            
        except Exception as e:
            logger.error(f"Erro na geração manual: {e}")
            # Fallback para prescrição genérica
            prescricao = self._gerar_prescricao_generica(sinais_vitais)
            recomendacoes = "• Seguir orientações médicas."
            
            receita_generica = self._criar_receita_formatada(
                diagnostico or "Diagnóstico não especificado",
                paciente_info,
                medico_info,
                prescricao,
                recomendacoes,
                sinais_vitais
            )
            return {
                'receita_completa': receita_generica,
                'prescricao': prescricao,
                'recomendacoes': recomendacoes,
                'diagnostico_resumo': diagnostico or "Diagnóstico não especificado"
            }, None
    
    def _criar_prompt_receita(self, diagnostico, paciente_info, medico_info, 
                              sintomas_lista, condicoes, sinais_vitais=None):
        """Cria prompt para o Gemini enfatizando que use APENAS medicamentos para as condições atuais"""
        sintomas_texto = "Nenhum sintoma informado"
        if sintomas_lista:
            sintomas_texto = "\n".join([f"  - {s}" for s in sintomas_lista])
        
        condicoes_texto = ', '.join(condicoes) if condicoes else 'a condição diagnosticada'
        sinais_vitais_texto = self._formatar_sinais_vitais_texto(sinais_vitais)
        peso = sinais_vitais.get('peso') if sinais_vitais else None
        
        prompt = f"""
VOCÊ É UM MÉDICO ESPECIALISTA. CRIE UMA RECEITA MÉDICA BASEADA EXCLUSIVAMENTE NO DIAGNÓSTICO ATUAL.

IMPORTANTE: A receita deve conter APENAS medicamentos relacionados DIRETAMENTE ao diagnóstico abaixo.
NÃO inclua medicamentos para condições crônicas não mencionadas (como diabetes ou hipertensão) a menos que explicitamente citadas no diagnóstico.

===== DADOS DO PACIENTE =====
Nome: {paciente_info.get('nome', 'Não informado')}
Idade: {paciente_info.get('idade', 'Não informada')}
Gênero: {paciente_info.get('genero', 'Não informado')}
{f'PESO: {peso} kg' if peso else ''}

===== DADOS DO MÉDICO =====
Nome: {medico_info.get('nome', 'Dr. Não Informado')}
CRM: {medico_info.get('crm', 'CRM não informado')}

===== DIAGNÓSTICO ATUAL =====
{diagnostico}

===== SINTOMAS =====
{sintomas_texto}

===== SINAIS VITAIS =====
{sinais_vitais_texto}

===== CONDIÇÕES IDENTIFICADAS =====
{condicoes_texto}

===== INSTRUÇÕES OBRIGATÓRIAS =====
1. A receita deve conter APENAS medicamentos para tratar AS CONDIÇÕES IDENTIFICADAS ACIMA
2. NÃO inclua medicamentos para outras condições crônicas
3. Mínimo de 2 medicamentos, máximo 5
4. Considere o peso do paciente para cálculos de dosagem
5. Use formatação limpa, organizada e profissional

FORMATO EXATO:

[NOME DO MEDICAMENTO]
  Apresentação: [dosagem]
  Posologia: [como tomar]
  Frequência: [intervalo]
  Duração: [dias]
  Via: [oral, etc]
  Quantidade: [total]
  Observações: [informações relevantes]

[PRÓXIMO MEDICAMENTO]
  Apresentação: [dosagem]
  Posologia: [como tomar]
  Frequência: [intervalo]
  Duração: [dias]
  Via: [oral, etc]
  Quantidade: [total]
  Observações: [informações relevantes]
"""
        
        return prompt
    
    def _criar_receita_formatada(self, diagnostico, paciente_info, medico_info, 
                                  prescricao, recomendacoes, sinais_vitais=None):
        """Cria a receita formatada de forma profissional"""
        data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        peso = sinais_vitais.get('peso') if sinais_vitais else None
        
        # Limpar formatação do diagnóstico
        diagnostico_limpo = limpar_formatacao_markdown(diagnostico)
        
        # Informações do paciente formatadas
        paciente_texto = f"{paciente_info.get('nome', '')}"
        if paciente_info.get('idade'):
            paciente_texto += f", {paciente_info.get('idade')}"
        
        receita = f"""
╔════════════════════════════════════════════════════════════════╗
║                      RECEITA MÉDICA                            ║
╚════════════════════════════════════════════════════════════════╝

MÉDICO: {medico_info.get('nome', '')}
CRM: {medico_info.get('crm', '')}
ESPECIALIDADE: {medico_info.get('especialidade', '')}
DATA: {data_atual}

PACIENTE: {paciente_texto}
{'PESO: ' + str(peso) + ' kg' if peso else ''}
{'GÊNERO: ' + paciente_info.get('genero', '') if paciente_info.get('genero') else ''}

──────────────────────────────────────────────────────────────────

1. DIAGNÓSTICO
{diagnostico_limpo}

──────────────────────────────────────────────────────────────────

2. PRESCRIÇÃO DE MEDICAMENTOS
{prescricao}

──────────────────────────────────────────────────────────────────

3. RECOMENDAÇÕES MÉDICAS
{recomendacoes}

──────────────────────────────────────────────────────────────────

________________________________________
Assinatura do Médico
{medico_info.get('nome', '')}
CRM: {medico_info.get('crm', '')}

Validade: 30 dias
"""
        return receita
    
    def _extrair_partes_receita(self, receita_completa):
        """Extrai partes da receita para exibição"""
        try:
            if not receita_completa:
                return {
                    'prescricao': 'Sem prescrição',
                    'recomendacoes': 'Sem recomendações',
                }
            
            linhas = receita_completa.split('\n')
            prescricao = []
            recomendacoes = []
            
            na_prescricao = False
            nas_recomendacoes = False
            
            palavras_prescricao = ['2. PRESCRIÇÃO DE MEDICAMENTOS', 'PRESCRIÇÃO DE MEDICAMENTOS']
            palavras_recomendacoes = ['3. RECOMENDAÇÕES MÉDICAS', 'RECOMENDAÇÕES MÉDICAS']
            
            for linha in linhas:
                linha_stripped = linha.strip()
                
                if any(p in linha for p in palavras_prescricao):
                    na_prescricao = True
                    nas_recomendacoes = False
                    continue
                elif any(p in linha for p in palavras_recomendacoes):
                    nas_recomendacoes = True
                    na_prescricao = False
                    continue
                
                if linha_stripped and not linha.startswith('─') and not linha.startswith('═') and not linha.startswith('╔') and not linha.startswith('║') and not linha.startswith('╚'):
                    if na_prescricao:
                        prescricao.append(linha_stripped)
                    elif nas_recomendacoes:
                        recomendacoes.append(linha_stripped)
            
            return {
                'prescricao': '\n'.join(prescricao) if prescricao else 'Conforme orientação médica.',
                'recomendacoes': '\n'.join(recomendacoes) if recomendacoes else 'Seguir orientações médicas.',
            }
            
        except Exception as e:
            logger.error(f"Erro ao extrair partes: {e}")
            return {
                'prescricao': receita_completa if receita_completa else 'Erro ao processar',
                'recomendacoes': 'Seguir orientações médicas.',
            }
    
    def salvar_receita_no_banco(self, consulta_id, diagnostico, prescricao, recomendacoes, medico_id):
        """Salva receita no banco de dados"""
        try:
            logger.info(f"SALVANDO RECEITA - Consulta ID: {consulta_id}")
            
            if not consulta_id:
                logger.error("consulta_id obrigatório")
                return None
            
            existing = self.execute_query("""
                SELECT id FROM receita WHERE consulta_id = %s
            """, (consulta_id,), fetch=True, one=True)
            
            if existing:
                result = self.execute_query("""
                    UPDATE receita 
                    SET diagnostico = %s,
                        prescricao = %s,
                        recomendacoes = %s,
                        status = 'ativa',
                        pdf_gerado = 0
                    WHERE consulta_id = %s
                """, (
                    diagnostico[:50000] if diagnostico else '',
                    prescricao[:50000] if prescricao else '',
                    recomendacoes[:20000] if recomendacoes else '',
                    consulta_id
                ))
                
                if result:
                    logger.info(f"Receita atualizada ID {existing[0]}")
                    return existing[0]
                return None
            else:
                result = self.execute_query("""
                    INSERT INTO receita 
                    (consulta_id, diagnostico, prescricao, recomendacoes, status, created_at, pdf_gerado)
                    VALUES (%s, %s, %s, %s, 'ativa', NOW(), 0)
                """, (
                    consulta_id,
                    diagnostico[:50000] if diagnostico else '',
                    prescricao[:50000] if prescricao else '',
                    recomendacoes[:20000] if recomendacoes else ''
                ))
                
                if result:
                    receita_id = self.execute_query("SELECT LAST_INSERT_ID()", fetch=True, one=True)
                    if receita_id and receita_id[0]:
                        logger.info(f"Nova receita ID {receita_id[0]}")
                        return receita_id[0]
                return None
            
        except Exception as e:
            logger.error(f"Erro ao salvar receita: {e}")
            return None
    
    def gerar_pdf_receita(self, receita_id, receita_data, paciente_info, medico_info):
        """Gera PDF da receita"""
        try:
            logger.info(f"GERANDO PDF PARA RECEITA #{receita_id}")
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                pdf_path = tmp_file.name
            
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            # Título
            elements.append(Paragraph("RECEITA MÉDICA", styles['Title']))
            elements.append(Spacer(1, 12))
            
            # Linha separadora
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
            elements.append(Spacer(1, 12))
            
            # Informações do médico
            elements.append(Paragraph(f"<b>Médico:</b> {medico_info.get('nome', '')}", styles['Normal']))
            elements.append(Paragraph(f"<b>CRM:</b> {medico_info.get('crm', '')}", styles['Normal']))
            elements.append(Paragraph(f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # Informações do paciente
            elements.append(Paragraph(f"<b>Paciente:</b> {paciente_info.get('nome', '')}", styles['Normal']))
            if paciente_info.get('idade'):
                elements.append(Paragraph(f"<b>Idade:</b> {paciente_info.get('idade')}", styles['Normal']))
            if paciente_info.get('genero'):
                elements.append(Paragraph(f"<b>Gênero:</b> {paciente_info.get('genero')}", styles['Normal']))
            
            # Destacar o peso
            if receita_data.get('sinais_vitais_considerados'):
                sv = receita_data['sinais_vitais_considerados']
                if sv.get('peso'):
                    peso = sv['peso']
                    elements.append(Paragraph(f"<b>Peso:</b> {peso} kg", styles['Normal']))
            
            elements.append(Spacer(1, 12))
            
            # Diagnóstico
            elements.append(Paragraph("<b>1. DIAGNÓSTICO</b>", styles['Heading2']))
            diagnostico_limpo = limpar_formatacao_markdown(receita_data.get('diagnostico_resumo', ''))
            elements.append(Paragraph(diagnostico_limpo.replace('\n', '<br/>'), styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # Prescrição
            if receita_data.get('prescricao'):
                elements.append(Paragraph("<b>2. PRESCRIÇÃO DE MEDICAMENTOS</b>", styles['Heading2']))
                prescricao_texto = receita_data['prescricao'].replace('\n', '<br/>')
                elements.append(Paragraph(prescricao_texto, styles['Normal']))
                elements.append(Spacer(1, 12))
            
            # Recomendações
            if receita_data.get('recomendacoes'):
                elements.append(Paragraph("<b>3. RECOMENDAÇÕES MÉDICAS</b>", styles['Heading2']))
                recomendacoes_texto = receita_data['recomendacoes'].replace('\n', '<br/>')
                elements.append(Paragraph(recomendacoes_texto, styles['Normal']))
            
            # Linha para assinatura
            elements.append(Spacer(1, 24))
            elements.append(HRFlowable(width="50%", thickness=1, color=colors.black))
            elements.append(Paragraph(f"{medico_info.get('nome', '')}", styles['Normal']))
            elements.append(Paragraph(f"CRM: {medico_info.get('crm', '')}", styles['Normal']))
            
            doc.build(elements)
            
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            
            upload_folder = self.app.config.get('UPLOAD_FOLDER', 'static/uploads')
            receitas_folder = os.path.join(upload_folder, 'receitas')
            os.makedirs(receitas_folder, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"receita_{receita_id}_{timestamp}.pdf"
            final_path = os.path.join(receitas_folder, filename)
            
            with open(final_path, 'wb') as f:
                f.write(pdf_bytes)
            
            pdf_relative_path = os.path.join('uploads', 'receitas', filename).replace('\\', '/')
            
            self.execute_query("""
                UPDATE receita 
                SET receita_pdf_path = %s, pdf_gerado = 1, data_geracao_pdf = NOW()
                WHERE id = %s
            """, (pdf_relative_path, receita_id))
            
            try:
                os.remove(pdf_path)
            except:
                pass
            
            return pdf_relative_path, pdf_bytes, None
            
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            return None, None, str(e)
    
    def listar_receitas_medico(self, medico_id):
        """Lista receitas do médico"""
        try:
            receitas = self.execute_query("""
                SELECT 
                    r.id, r.consulta_id, r.diagnostico, r.prescricao,
                    r.recomendacoes, r.status, r.created_at, r.receita_pdf_path,
                    r.pdf_gerado, r.data_geracao_pdf,
                    COALESCE(p_u.nome, 'Não informado') as paciente_nome,
                    p.data_nascimento, p.genero, c.data_hora as consulta_data
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE c.medico_id = %s
                ORDER BY r.created_at DESC
            """, (medico_id,), fetch=True)
            
            return receitas if receitas else []
            
        except Exception as e:
            logger.error(f"Erro ao listar receitas: {e}")
            return []
    
    def buscar_receita_por_id(self, receita_id, medico_id):
        """Busca receita por ID"""
        try:
            receita = self.execute_query("""
                SELECT 
                    r.id, r.consulta_id, r.diagnostico, r.prescricao,
                    r.recomendacoes, r.status, r.created_at, r.receita_pdf_path,
                    r.pdf_gerado, r.data_geracao_pdf, c.paciente_id,
                    COALESCE(p_u.nome, 'Não informado') as paciente_nome,
                    p.data_nascimento, p.genero, p.telefone, m.id as medico_id
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                JOIN medicos m ON c.medico_id = m.id
                WHERE r.id = %s AND m.id = %s
            """, (receita_id, medico_id), fetch=True, one=True)
            
            return receita
            
        except Exception as e:
            logger.error(f"Erro ao buscar receita: {e}")
            return None
    
    def get_pdf_receita_path(self, receita_id, medico_id):
        """Retorna caminho do PDF da receita"""
        try:
            receita = self.execute_query("""
                SELECT r.receita_pdf_path, COALESCE(p_u.nome, 'Paciente')
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                JOIN medicos m ON c.medico_id = m.id
                WHERE r.id = %s AND m.id = %s
            """, (receita_id, medico_id), fetch=True, one=True)
            
            if not receita or not receita[0]:
                return None, None
            
            upload_folder = self.app.config.get('UPLOAD_FOLDER', 'static/uploads')
            filename = os.path.basename(receita[0])
            pdf_full_path = os.path.join(upload_folder, 'receitas', filename)
            
            if os.path.exists(pdf_full_path):
                return pdf_full_path, receita[1]
            return None, None
            
        except Exception as e:
            logger.error(f"Erro ao buscar PDF: {e}")
            return None, None