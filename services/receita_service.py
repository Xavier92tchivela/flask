# services/receita_service.py - VERSÃO COMPLETA COM SINAIS VITAIS E PESO

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

logger = logging.getLogger(__name__)

class ReceitaService:
    """Serviço para gerenciar receitas médicas com formatação profissional"""
    
    MEDICAMENTOS_PRIMEIRA_LINHA = {
        'malaria': [
            {
                'nome': 'Artemeter + Lumefantrina (ACT)',
                'apresentacao': 'Comprimidos 20/120mg',
                'posologia': '4 comprimidos por dose (adulto)',
                'frequencia': '2 vezes ao dia',
                'duracao': '3 dias',
                'via': 'Oral',
                'quantidade': '24 comprimidos',
                'observacoes': 'Terapia Combinada à Base de Artemisinina - primeira linha OMS'
            },
            {
                'nome': 'Primaquina',
                'apresentacao': 'Comprimidos 15mg',
                'posologia': '1 comprimido ao dia',
                'frequencia': '1 vez ao dia',
                'duracao': '14 dias',
                'via': 'Oral',
                'quantidade': '14 comprimidos',
                'observacoes': 'APÓS teste G6PD - para eliminar formas hepáticas'
            },
            {
                'nome': 'Paracetamol',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas se febre',
                'duracao': 'Durante febre',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Para controle da febre e dor'
            }
        ],
        
        'febre_tifoide': [
            {
                'nome': 'Ceftriaxona',
                'apresentacao': 'Ampola 1g',
                'posologia': '2g IV',
                'frequencia': '1 vez ao dia',
                'duracao': '10 dias',
                'via': 'Intravenosa',
                'quantidade': '10 ampolas',
                'observacoes': 'Primeira linha para febre tifoide'
            },
            {
                'nome': 'Azitromicina',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1g no primeiro dia, depois 500mg',
                'frequencia': '1 vez ao dia',
                'duracao': '7 dias',
                'quantidade': '8 comprimidos',
                'via': 'Oral',
                'observacoes': 'Alternativa oral para casos leves'
            },
            {
                'nome': 'Paracetamol',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas se febre',
                'duracao': 'Durante febre',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Controle da febre'
            }
        ],
        
        'pneumonia': [
            {
                'nome': 'Amoxicilina',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1 comprimido',
                'frequencia': '8/8 horas',
                'duracao': '10 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Primeira linha para pneumonia comunitária'
            },
            {
                'nome': 'Azitromicina',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '500mg',
                'frequencia': '1 vez ao dia',
                'duracao': '5 dias',
                'via': 'Oral',
                'quantidade': '5 comprimidos',
                'observacoes': 'Para cobertura de atípicos'
            },
            {
                'nome': 'N-Acetilcisteína',
                'apresentacao': 'Comprimidos 600mg',
                'posologia': '1 comprimido',
                'frequencia': '12/12 horas',
                'duracao': '10 dias',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Expectorante e fluidificante'
            }
        ],
        
        'tuberculose': [
            {
                'nome': 'Rifampicina',
                'apresentacao': 'Comprimidos 300mg',
                'posologia': '2 comprimidos',
                'frequencia': '1 vez ao dia',
                'duracao': '2 meses (fase intensiva)',
                'via': 'Oral',
                'quantidade': '60 comprimidos',
                'observacoes': 'Esquema básico - não interromper'
            },
            {
                'nome': 'Isoniazida',
                'apresentacao': 'Comprimidos 100mg',
                'posologia': '3 comprimidos',
                'frequencia': '1 vez ao dia',
                'duracao': '2 meses (fase intensiva)',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Associar piridoxina para neuropatia'
            },
            {
                'nome': 'Pirazinamida',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '2 comprimidos',
                'frequencia': '1 vez ao dia',
                'duracao': '2 meses (fase intensiva)',
                'via': 'Oral',
                'quantidade': '120 comprimidos',
                'observacoes': 'Proteger função hepática'
            }
        ],
        
        'infeccao_urinaria': [
            {
                'nome': 'Fosfomicina Trometamol',
                'apresentacao': 'Sachê 3g',
                'posologia': '1 sachê',
                'frequencia': 'Dose única',
                'duracao': '1 dia',
                'via': 'Oral',
                'quantidade': '1 sachê',
                'observacoes': 'Primeira linha para cistite não complicada'
            },
            {
                'nome': 'Nitrofurantoína',
                'apresentacao': 'Comprimidos 100mg',
                'posologia': '1 comprimido',
                'frequencia': '12/12 horas',
                'duracao': '5 dias',
                'via': 'Oral',
                'quantidade': '10 comprimidos',
                'observacoes': 'Alternativa de primeira linha'
            },
            {
                'nome': 'Escina + Hialuronato',
                'apresentacao': 'Drágeas',
                'posologia': '1 drágea',
                'frequencia': '12/12 horas',
                'duracao': '5 dias',
                'via': 'Oral',
                'quantidade': '10 drágeas',
                'observacoes': 'Alívio dos sintomas urinários'
            }
        ],
        
        'hipertensao': [
            {
                'nome': 'Hidroclorotiazida',
                'apresentacao': 'Comprimidos 25mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Tiazídico - primeira linha HAS'
            },
            {
                'nome': 'Losartana Potássica',
                'apresentacao': 'Comprimidos 50mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'BRA - primeira linha, especialmente em diabéticos'
            },
            {
                'nome': 'Anlodipino',
                'apresentacao': 'Comprimidos 5mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'BCC - pode associar se necessário'
            }
        ],
        
        'diabetes': [
            {
                'nome': 'Metformina',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1 comprimido',
                'frequencia': '3 vezes ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'PRIMEIRA LINHA ABSOLUTA para DM2'
            },
            {
                'nome': 'Gliclazida',
                'apresentacao': 'Comprimidos 60mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Sulfonilureia se metformina não for suficiente'
            },
            {
                'nome': 'Sitagliptina',
                'apresentacao': 'Comprimidos 100mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '30 dias',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Inibidor DPP-4, baixo risco de hipoglicemia'
            }
        ],
        
        'anemia': [
            {
                'nome': 'Sulfato Ferroso',
                'apresentacao': 'Comprimidos 300mg',
                'posologia': '1 comprimido',
                'frequencia': '2 vezes ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Primeira linha para anemia ferropriva'
            },
            {
                'nome': 'Ácido Fólico',
                'apresentacao': 'Comprimidos 5mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'Associar ao ferro'
            },
            {
                'nome': 'Vitamina B12',
                'apresentacao': 'Comprimidos 1000mcg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': '90 dias',
                'via': 'Oral',
                'quantidade': '90 comprimidos',
                'observacoes': 'Se anemia megaloblástica ou deficiência associada'
            }
        ],
        
        'gravidez': [
            {
                'nome': 'Sulfato Ferroso',
                'apresentacao': 'Comprimidos 300mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': 'ATÉ O PARTO',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Suplementação obrigatória na gestação'
            },
            {
                'nome': 'Ácido Fólico',
                'apresentacao': 'Comprimidos 5mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia',
                'duracao': 'ATÉ O PARTO',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Prevenção de defeitos do tubo neural'
            },
            {
                'nome': 'Carbonato de Cálcio',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1 comprimido',
                'frequencia': '2 vezes ao dia',
                'duracao': 'ATÉ O PARTO',
                'via': 'Oral',
                'quantidade': '180 comprimidos',
                'observacoes': 'Prevenção de pré-eclâmpsia e osteoporose'
            }
        ],
        
        'dengue': [
            {
                'nome': 'Paracetamol',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas',
                'duracao': 'Durante febre',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'ÚNICO ANALGÉSICO SEGURO - NÃO USAR AAS OU AINES'
            },
            {
                'nome': 'Dipirona',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas se dor intensa',
                'duracao': 'Durante dor',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Alternativa para dor, se necessário'
            },
            {
                'nome': 'Hidratação Oral',
                'apresentacao': 'Soro de reidratação oral',
                'posologia': '60-80ml/kg/dia',
                'frequencia': 'Contínua',
                'duracao': 'ATÉ MELHORA',
                'via': 'Oral',
                'quantidade': '6 litros',
                'observacoes': 'FUNDAMENTAL - base do tratamento da dengue'
            }
        ]
    }
    
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
        'arbovirose': 'dengue'
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
        
        logger.info(f"Condições identificadas: {condicoes_encontradas}")
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
        
        return "\n".join(texto) if texto else "Não informados"
    
    def _gerar_prescricao_primeira_linha(self, condicoes, tem_gravidez=False):
        try:
            if not condicoes:
                return self._gerar_prescricao_generica()
            
            prescricao = []
            medicamentos_adicionados = set()
            
            for condicao in condicoes:
                if condicao in self.MEDICAMENTOS_PRIMEIRA_LINHA:
                    medicamentos = self.MEDICAMENTOS_PRIMEIRA_LINHA[condicao]
                    
                    for med in medicamentos:
                        if med['nome'] not in medicamentos_adicionados:
                            prescricao.append(self._formatar_medicamento(med, tem_gravidez))
                            medicamentos_adicionados.add(med['nome'])
            
            if len(medicamentos_adicionados) < 3:
                suporte = self._gerar_medicamentos_suporte()
                for med in suporte:
                    if med['nome'] not in medicamentos_adicionados:
                        prescricao.append(self._formatar_medicamento(med, tem_gravidez))
                        medicamentos_adicionados.add(med['nome'])
                        if len(medicamentos_adicionados) >= 3:
                            break
            
            if not prescricao:
                return self._gerar_prescricao_generica()
            
            return "\n".join(prescricao)
            
        except Exception as e:
            logger.error(f"Erro ao gerar prescrição: {e}")
            return self._gerar_prescricao_generica()
    
    def _formatar_medicamento(self, med, tem_gravidez=False):
        linhas = []
        linhas.append(f"\n{med['nome']}")
        linhas.append(f"* Apresentação: {med['apresentacao']}")
        linhas.append(f"* Posologia: {med['posologia']}")
        linhas.append(f"* Frequência: {med['frequencia']}")
        linhas.append(f"* Duração: {med['duracao']}")
        linhas.append(f"* Via: {med['via']}")
        linhas.append(f"* Quantidade: {med['quantidade']}")
        linhas.append(f"* {med['observacoes']}")
        
        if tem_gravidez and 'gravidez' not in med.get('nome', '').lower():
            linhas.append("* ⚠️ GESTANTE: avaliar risco/benefício com obstetra")
        
        return "\n".join(linhas)
    
    def _gerar_medicamentos_suporte(self):
        return [
            {
                'nome': 'Paracetamol',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas se febre ou dor',
                'duracao': 'Conforme necessidade',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Controle da dor e febre'
            },
            {
                'nome': 'Dipirona',
                'apresentacao': 'Comprimidos 500mg',
                'posologia': '1-2 comprimidos',
                'frequencia': '6/6 horas se dor intensa',
                'duracao': 'Conforme necessidade',
                'via': 'Oral',
                'quantidade': '20 comprimidos',
                'observacoes': 'Alternativa para dor'
            },
            {
                'nome': 'Omeprazol',
                'apresentacao': 'Comprimidos 20mg',
                'posologia': '1 comprimido',
                'frequencia': '1 vez ao dia em jejum',
                'duracao': 'Durante o tratamento',
                'via': 'Oral',
                'quantidade': '30 comprimidos',
                'observacoes': 'Proteção gástrica durante antibioticoterapia'
            }
        ]
    
    def _gerar_prescricao_generica(self):
        return """
Paracetamol
* Apresentação: Comprimidos 500mg
* Posologia: 1-2 comprimidos
* Frequência: 6/6 horas se febre ou dor
* Duração: Conforme necessidade
* Via: Oral
* Quantidade: 20 comprimidos
* Controle da dor e febre

Dipirona
* Apresentação: Comprimidos 500mg
* Posologia: 1-2 comprimidos
* Frequência: 6/6 horas se dor intensa
* Duração: Conforme necessidade
* Via: Oral
* Quantidade: 20 comprimidos
* Alternativa para dor, se necessário

Omeprazol
* Apresentação: Comprimidos 20mg
* Posologia: 1 comprimido
* Frequência: 1 vez ao dia em jejum
* Duração: Durante o tratamento
* Via: Oral
* Quantidade: 30 comprimidos
* Proteção gástrica
"""
    
    def _gerar_recomendacoes_padrao(self, condicoes, tem_gravidez=False, sinais_vitais=None):
        recomendacoes = []
        
        recomendacoes.append("Seguir rigorosamente a posologia dos medicamentos prescritos")
        recomendacoes.append("Manter-se bem hidratado, ingerindo bastante líquidos")
        recomendacoes.append("Repousar adequadamente para auxiliar na recuperação")
        recomendacoes.append("Evitar automedicação e bebidas alcoólicas durante o tratamento")
        
        # Recomendações baseadas em sinais vitais
        if sinais_vitais:
            if sinais_vitais.get('peso') and float(sinais_vitais['peso']) > 100:
                recomendacoes.append("Devido ao peso elevado, atenção especial à dosagem dos medicamentos")
            if sinais_vitais.get('pressao_arterial') and '140' in str(sinais_vitais['pressao_arterial']):
                recomendacoes.append("Monitorar pressão arterial regularmente")
            if sinais_vitais.get('glicemia') and int(sinais_vitais['glicemia']) > 200:
                recomendacoes.append("Glicemia elevada - reforçar dieta e monitoramento")
        
        for condicao in condicoes:
            if 'malaria' in condicao:
                recomendacoes.append("COMPLETAR O TRATAMENTO mesmo após melhora dos sintomas")
                recomendacoes.append("Realizar teste G6PD antes de iniciar Primaquina")
                recomendacoes.append("Usar mosquiteiro impregnado com inseticida")
            elif 'tuberculose' in condicao:
                recomendacoes.append("TRATAMENTO SUPERVISIONADO - Não interromper o tratamento")
                recomendacoes.append("Retorno mensal obrigatório para reavaliação")
            elif 'hipertensao' in condicao:
                recomendacoes.append("Reduzir consumo de sal e alimentos processados")
                recomendacoes.append("Praticar atividade física regular")
            elif 'diabetes' in condicao:
                recomendacoes.append("Manter dieta equilibrada, evitar açúcares")
                recomendacoes.append("Monitorar glicemia conforme orientação")
            elif 'dengue' in condicao:
                recomendacoes.append("NÃO USAR AAS, ibuprofeno ou outros anti-inflamatórios")
                recomendacoes.append("HIDRATAÇÃO INTENSIVA - fundamental para recuperação")
        
        recomendacoes.append("\n⚠️ SINAIS DE ALERTA - PROCURAR URGÊNCIA SE:")
        recomendacoes.append("• Febre persistente ou alta (>24h sem melhora)")
        recomendacoes.append("• Falta de ar ou dificuldade para respirar")
        recomendacoes.append("• Confusão mental, sonolência excessiva ou desmaios")
        recomendacoes.append("• Sangramentos incomuns (gengivas, nariz, urina escura)")
        recomendacoes.append("• Vômitos persistentes")
        
        recomendacoes.append("\nRetorno: Agendar em 7-10 dias ou antes se necessário")
        
        return "\n".join([f"• {r}" for r in recomendacoes])
    
    def gerar_receita_ia(self, diagnostico, paciente_info, medico_info, sintomas=None, sinais_vitais=None):
        """
        Gera receita médica usando Gemini com GARANTIA DE MÍNIMO 3 MEDICAMENTOS
        """
        try:
            if not self.gemini_available or not self.genai:
                logger.error("API Gemini não configurada")
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
            
            diagnostico_lower = diagnostico.lower() if diagnostico else ""
            sintomas_lower = " ".join(sintomas_lista).lower() if sintomas_lista else ""
            texto_completo = diagnostico_lower + " " + sintomas_lower
            
            tem_gravidez = any(p in texto_completo for p in ['gravidez', 'gestante', 'grávida'])
            
            logger.info(f"Condições: {condicoes}")
            logger.info(f"Gravidez: {tem_gravidez}")
            
            prescricao_primeira_linha = self._gerar_prescricao_primeira_linha(condicoes, tem_gravidez)
            recomendacoes = self._gerar_recomendacoes_padrao(condicoes, tem_gravidez, sinais_vitais)
            
            try:
                prompt = self._criar_prompt_receita(
                    diagnostico, paciente_info, medico_info, 
                    sintomas_lista, condicoes, tem_gravidez, sinais_vitais
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
                    
                    if self._contar_medicamentos(receita) < 3:
                        logger.warning("Gemini gerou menos de 3 medicamentos, usando fallback")
                        receita = self._criar_receita_formatada(
                            diagnostico, paciente_info, medico_info,
                            prescricao_primeira_linha, recomendacoes
                        )
                else:
                    receita = self._criar_receita_formatada(
                        diagnostico, paciente_info, medico_info,
                        prescricao_primeira_linha, recomendacoes
                    )
                
            except Exception as e:
                logger.warning(f"Erro ao usar Gemini, usando fallback: {e}")
                receita = self._criar_receita_formatada(
                    diagnostico, paciente_info, medico_info,
                    prescricao_primeira_linha, recomendacoes
                )
            
            partes = self._extrair_partes_receita(receita)
            
            return {
                'receita_completa': receita,
                'prescricao': partes['prescricao'],
                'recomendacoes': partes['recomendacoes'],
                'diagnostico_resumo': diagnostico,
                'sintomas_considerados': sintomas_lista,
                'sinais_vitais_considerados': sinais_vitais,
                'medicamentos_primeira_linha': True
            }, None
            
        except Exception as e:
            logger.error(f"Erro ao gerar receita: {e}")
            logger.error(traceback.format_exc())
            return self._gerar_receita_manual(diagnostico, paciente_info, medico_info, sintomas, sinais_vitais)
    
    def _gerar_receita_manual(self, diagnostico, paciente_info, medico_info, sintomas=None, sinais_vitais=None):
        try:
            sintomas_lista = self._extrair_sintomas_estruturados(sintomas)
            condicoes = self._extrair_palavras_chave(diagnostico, sintomas_lista, sinais_vitais)
            
            texto_completo = diagnostico.lower() if diagnostico else ""
            if sintomas_lista:
                texto_completo += " " + " ".join(sintomas_lista).lower()
            
            tem_gravidez = any(p in texto_completo for p in ['gravidez', 'gestante', 'grávida'])
            
            prescricao = self._gerar_prescricao_primeira_linha(condicoes, tem_gravidez)
            recomendacoes = self._gerar_recomendacoes_padrao(condicoes, tem_gravidez, sinais_vitais)
            
            receita_completa = self._criar_receita_formatada(
                diagnostico, paciente_info, medico_info,
                prescricao, recomendacoes
            )
            
            partes = self._extrair_partes_receita(receita_completa)
            
            return {
                'receita_completa': receita_completa,
                'prescricao': partes['prescricao'],
                'recomendacoes': partes['recomendacoes'],
                'diagnostico_resumo': diagnostico,
                'sintomas_considerados': sintomas_lista,
                'sinais_vitais_considerados': sinais_vitais,
                'medicamentos_primeira_linha': True
            }, None
            
        except Exception as e:
            logger.error(f"Erro na geração manual: {e}")
            receita_generica = self._criar_receita_formatada(
                diagnostico or "Diagnóstico não especificado",
                paciente_info,
                medico_info,
                self._gerar_prescricao_generica(),
                self._gerar_recomendacoes_padrao([])
            )
            return {
                'receita_completa': receita_generica,
                'prescricao': self._gerar_prescricao_generica(),
                'recomendacoes': self._gerar_recomendacoes_padrao([]),
                'diagnostico_resumo': diagnostico or "Diagnóstico não especificado"
            }, None
    
    def _contar_medicamentos(self, receita_texto):
        if not receita_texto:
            return 0
        
        padroes = [
            r'^\d+\.\s+\*\*?[A-Za-z]',
            r'^\*\s*\*\*?[A-Za-z]',
            r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*\*',
        ]
        
        linhas = receita_texto.split('\n')
        contador = 0
        
        for linha in linhas:
            linha = linha.strip()
            for padrao in padroes:
                if re.match(padrao, linha):
                    contador += 1
                    break
        
        return max(contador, 0)
    
    def _criar_prompt_receita(self, diagnostico, paciente_info, medico_info, 
                              sintomas_lista, condicoes, tem_gravidez, sinais_vitais=None):
        sintomas_texto = "Nenhum sintoma informado"
        if sintomas_lista:
            sintomas_texto = "\n".join([f"  • {s}" for s in sintomas_lista])
        
        condicoes_texto = ', '.join(condicoes) if condicoes else 'a condição diagnosticada'
        
        sinais_vitais_texto = self._formatar_sinais_vitais_texto(sinais_vitais)
        
        prompt = f"""
VOCÊ É UM MÉDICO ESPECIALISTA. CRIE UMA RECEITA MÉDICA BASEADA NO DIAGNÓSTICO, SINTOMAS E SINAIS VITAIS.

===== DADOS DO PACIENTE =====
Nome: {paciente_info.get('nome', 'Não informado')}
Idade: {paciente_info.get('idade', 'Não informada')}
Gênero: {paciente_info.get('genero', 'Não informado')}

===== DADOS DO MÉDICO =====
Nome: {medico_info.get('nome', 'Dr. Não Informado')}
Especialidade: {medico_info.get('especialidade', 'Clínico Geral')}
CRM: {medico_info.get('crm', 'CRM não informado')}

===== DIAGNÓSTICO =====
{diagnostico}

===== SINTOMAS RELATADOS =====
{sintomas_texto}

===== SINAIS VITAIS =====
{sinais_vitais_texto}

===== CONDIÇÕES IDENTIFICADAS =====
{condicoes_texto}
{'GRAVIDEZ: Sim - CONSIDERAR NAS PRESCRIÇÕES' if tem_gravidez else ''}

===== INSTRUÇÕES OBRIGATÓRIAS =====
1. A RECEITA DEVE CONTER PELO MENOS 3 MEDICAMENTOS DIFERENTES
2. Use apenas medicamentos de primeira linha baseados em evidências
3. Considere os sinais vitais na escolha dos medicamentos
4. Se houver peso informado, considere para cálculo de dosagens
5. Siga o formato exato abaixo

FORMATO OBRIGATÓRIO:

─────────────────────────────────────────────────────────
                      RECEITA MÉDICA
─────────────────────────────────────────────────────────

MÉDICO: {medico_info.get('nome', '')}
CRM: {medico_info.get('crm', '')}
ESPECIALIDADE: {medico_info.get('especialidade', '')}
DATA: {datetime.now().strftime('%d/%m/%Y')}

PACIENTE: {paciente_info.get('nome', '')}
IDADE: {paciente_info.get('idade', '')}
GÊNERO: {paciente_info.get('genero', '')}

─────────────────────────────────────────────────────────

**1. DIAGNÓSTICO**
[Resumo do diagnóstico baseado APENAS no conteúdo fornecido]

─────────────────────────────────────────────────────────

**2. PRESCRIÇÃO DE MEDICAMENTOS**
[LISTA COM PELO MENOS 3 MEDICAMENTOS ESPECÍFICOS]

Para cada medicamento:
1. NOME COMPLETO
   * Apresentação: [dosagem]
   * Posologia: [como tomar]
   * Frequência: [intervalo]
   * Duração: [dias]
   * Via: [oral, etc]
   * Quantidade: [total]

─────────────────────────────────────────────────────────

**3. RECOMENDAÇÕES MÉDICAS**
• [Recomendação 1 baseada nos sintomas e sinais vitais]
• [Recomendação 2 baseada nos sintomas e sinais vitais]
• [Recomendação 3 baseada nos sintomas e sinais vitais]
• Sinais de alerta:
• Retorno:

─────────────────────────────────────────────────────────

________________________________________
Assinatura do Médico
{medico_info.get('nome', '')}
CRM: {medico_info.get('crm', '')}

─────────────────────────────────────────────────────────
"""
        
        return prompt
    
    def _criar_receita_formatada(self, diagnostico, paciente_info, medico_info, 
                                  prescricao, recomendacoes):
        data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        receita = f"""
RECEITA MÉDICA
{'='*60}

MÉDICO: {medico_info.get('nome', '')}
CRM: {medico_info.get('crm', '')}
ESPECIALIDADE: {medico_info.get('especialidade', '')}
DATA: {data_atual}

PACIENTE: {paciente_info.get('nome', '')}
IDADE: {paciente_info.get('idade', '')}
GÊNERO: {paciente_info.get('genero', '')}

{'-'*60}

**1. DIAGNÓSTICO**
{diagnostico}

{'-'*60}

**2. PRESCRIÇÃO DE MEDICAMENTOS**
{prescricao}

{'-'*60}

**3. RECOMENDAÇÕES MÉDICAS**
{recomendacoes}

{'-'*60}

________________________________________
Assinatura do Médico
{medico_info.get('nome', '')}
CRM: {medico_info.get('crm', '')}

Validade: 30 dias
"""
        return receita
    
    def _extrair_partes_receita(self, receita_completa):
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
            
            palavras_prescricao = ['PRESCRIÇÃO DE MEDICAMENTOS', '**2. PRESCRIÇÃO', '2. PRESCRIÇÃO']
            palavras_recomendacoes = ['RECOMENDAÇÕES MÉDICAS', '**3. RECOMENDAÇÕES', '3. RECOMENDAÇÕES']
            
            for linha in linhas:
                linha_stripped = linha.strip()
                linha_upper = linha_stripped.upper()
                
                if '---' in linha or '===' in linha:
                    continue
                
                if any(p in linha_upper for p in palavras_prescricao):
                    na_prescricao = True
                    nas_recomendacoes = False
                    continue
                elif any(p in linha_upper for p in palavras_recomendacoes):
                    nas_recomendacoes = True
                    na_prescricao = False
                    continue
                
                if linha_stripped:
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
        try:
            logger.info(f"GERANDO PDF PARA RECEITA #{receita_id}")
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                pdf_path = tmp_file.name
            
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("RECEITA MÉDICA", styles['Title']))
            elements.append(Spacer(1, 12))
            
            elements.append(Paragraph(f"<b>Médico:</b> {medico_info.get('nome', '')}", styles['Normal']))
            elements.append(Paragraph(f"<b>CRM:</b> {medico_info.get('crm', '')}", styles['Normal']))
            elements.append(Paragraph(f"<b>Paciente:</b> {paciente_info.get('nome', '')}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            if receita_data.get('prescricao'):
                elements.append(Paragraph("<b>PRESCRIÇÃO:</b>", styles['Normal']))
                elements.append(Paragraph(receita_data['prescricao'].replace('\n', '<br/>'), styles['Normal']))
                elements.append(Spacer(1, 12))
            
            if receita_data.get('recomendacoes'):
                elements.append(Paragraph("<b>RECOMENDAÇÕES:</b>", styles['Normal']))
                elements.append(Paragraph(receita_data['recomendacoes'].replace('\n', '<br/>'), styles['Normal']))
            
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