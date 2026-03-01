# utils/classificacoes.py
"""
Módulo com funções para classificação de sinais vitais
Baseado em diretrizes médicas padrão
"""

def classificar_pressao_arterial(valor):
    """
    Classifica a pressão arterial de acordo com as diretrizes
    Formato esperado: "120 x 80" ou "120/80"
    """
    if not valor:
        return "Não informado"
    
    try:
        # Extrair valores sistólica e diastólica
        if 'x' in valor:
            partes = valor.split('x')
        elif '/' in valor:
            partes = valor.split('/')
        else:
            return "Formato inválido"
        
        sistolica = int(partes[0].strip())
        diastolica = int(partes[1].strip())
        
        # Classificação baseada nas diretrizes
        if sistolica < 90 or diastolica < 60:
            return "Hipotensão"
        elif sistolica < 120 and diastolica < 80:
            return "Normal"
        elif sistolica < 130 and diastolica < 80:
            return "Elevada"
        elif sistolica < 140 or diastolica < 90:
            return "Hipertensão Estágio 1"
        elif sistolica >= 140 or diastolica >= 90:
            return "Hipertensão Estágio 2"
        elif sistolica > 180 or diastolica > 120:
            return "Crise Hipertensiva"
        else:
            return "Limítrofe"
    except:
        return "Erro na classificação"

def classificar_frequencia_cardiaca(valor):
    """
    Classifica a frequência cardíaca (bpm)
    """
    if not valor:
        return "Não informado"
    
    try:
        # Converter para inteiro
        if isinstance(valor, str):
            import re
            numeros = re.findall(r'\d+', valor)
            if numeros:
                fc = int(numeros[0])
            else:
                return "Valor inválido"
        else:
            fc = int(valor)
        
        # Classificação
        if fc < 60:
            return "Bradicardia"
        elif 60 <= fc <= 100:
            return "Normal"
        elif 101 <= fc <= 120:
            return "Taquicardia leve"
        elif 121 <= fc <= 140:
            return "Taquicardia moderada"
        else:
            return "Taquicardia severa"
    except:
        return "Erro na classificação"

def classificar_frequencia_respiratoria(valor):
    """
    Classifica a frequência respiratória (respirações/minuto)
    """
    if not valor:
        return "Não informado"
    
    try:
        # Converter para inteiro
        if isinstance(valor, str):
            import re
            numeros = re.findall(r'\d+', valor)
            if numeros:
                fr = int(numeros[0])
            else:
                return "Valor inválido"
        else:
            fr = int(valor)
        
        # Classificação para adultos
        if fr < 12:
            return "Bradipneia"
        elif 12 <= fr <= 20:
            return "Normal"
        elif 21 <= fr <= 24:
            return "Taquipneia leve"
        elif 25 <= fr <= 30:
            return "Taquipneia moderada"
        else:
            return "Taquipneia severa"
    except:
        return "Erro na classificação"

def classificar_temperatura(valor):
    """
    Classifica a temperatura corporal (°C)
    """
    if not valor:
        return "Não informado"
    
    try:
        # Converter para float
        if isinstance(valor, str):
            import re
            numeros = re.findall(r'[\d.]+', valor)
            if numeros:
                temp = float(numeros[0])
            else:
                return "Valor inválido"
        else:
            temp = float(valor)
        
        # Classificação
        if temp < 35.0:
            return "Hipotermia"
        elif 35.0 <= temp < 36.0:
            return "Hipotermia leve"
        elif 36.0 <= temp <= 37.2:
            return "Normal"
        elif 37.3 <= temp <= 37.7:
            return "Febrícula (estado febril)"
        elif 37.8 <= temp <= 38.9:
            return "Febre"
        elif 39.0 <= temp <= 39.9:
            return "Febre alta"
        else:
            return "Febre muito alta (hipertermia)"
    except:
        return "Erro na classificação"

def classificar_saturacao_oxigenio(valor):
    """
    Classifica a saturação de oxigênio (%)
    """
    if not valor:
        return "Não informado"
    
    try:
        # Converter para inteiro
        if isinstance(valor, str):
            import re
            numeros = re.findall(r'\d+', valor)
            if numeros:
                spo2 = int(numeros[0])
            else:
                return "Valor inválido"
        else:
            spo2 = int(valor)
        
        # Classificação
        if spo2 >= 95:
            return "Normal"
        elif 90 <= spo2 <= 94:
            return "Hipóxia leve"
        elif 85 <= spo2 <= 89:
            return "Hipóxia moderada"
        else:
            return "Hipóxia severa"
    except:
        return "Erro na classificação"

def classificar_glicemia(valor):
    """
    Classifica a glicemia (mg/dL)
    """
    if not valor:
        return "Não informado"
    
    try:
        # Converter para inteiro
        if isinstance(valor, str):
            import re
            numeros = re.findall(r'\d+', valor)
            if numeros:
                glicemia = int(numeros[0])
            else:
                return "Valor inválido"
        else:
            glicemia = int(valor)
        
        # Classificação (jejum)
        if glicemia < 70:
            return "Hipoglicemia"
        elif 70 <= glicemia <= 99:
            return "Normal"
        elif 100 <= glicemia <= 125:
            return "Pré-diabetes (glicemia de jejum alterada)"
        elif 126 <= glicemia <= 199:
            return "Diabetes (confirmar com outro exame)"
        else:
            return "Diabetes não controlado"
    except:
        return "Erro na classificação"

# ===== NOVA FUNÇÃO: CLASSIFICAR PESO =====
def classificar_peso(valor):
    """
    Classifica o peso corporal com base no IMC (aproximado)
    Como não temos altura, usamos faixas de peso absoluto
    """
    if not valor:
        return "Não informado"
    
    try:
        # Converter para float
        if isinstance(valor, str):
            import re
            numeros = re.findall(r'[\d.]+', valor)
            if numeros:
                peso = float(numeros[0])
            else:
                return "Valor inválido"
        else:
            peso = float(valor)
        
        # Classificação baseada em faixas de peso (para adulto médio)
        if peso < 30:
            return "Abaixo do peso severo"
        elif 30 <= peso < 50:
            return "Abaixo do peso"
        elif 50 <= peso < 60:
            return "Peso baixo"
        elif 60 <= peso < 70:
            return "Peso normal (60-69kg)"
        elif 70 <= peso < 80:
            return "Peso normal (70-79kg)"
        elif 80 <= peso < 90:
            return "Sobrepeso (80-89kg)"
        elif 90 <= peso < 100:
            return "Obesidade Grau I (90-99kg)"
        elif 100 <= peso < 120:
            return "Obesidade Grau II (100-119kg)"
        else:
            return "Obesidade Grau III (≥120kg)"
    except:
        return "Erro na classificação"

def classificar_imc(peso, altura):
    """
    Classifica o IMC (Índice de Massa Corporal)
    Requer peso (kg) e altura (m)
    """
    if not peso or not altura:
        return "Não informado"
    
    try:
        # Converter para float
        peso_float = float(peso)
        altura_float = float(altura)
        
        if altura_float <= 0 or peso_float <= 0:
            return "Valores inválidos"
        
        # Calcular IMC
        imc = peso_float / (altura_float * altura_float)
        
        # Classificação OMS
        if imc < 16:
            return "Magreza grau III"
        elif 16 <= imc < 17:
            return "Magreza grau II"
        elif 17 <= imc < 18.5:
            return "Magreza grau I"
        elif 18.5 <= imc < 25:
            return "Peso normal"
        elif 25 <= imc < 30:
            return "Sobrepeso"
        elif 30 <= imc < 35:
            return "Obesidade grau I"
        elif 35 <= imc < 40:
            return "Obesidade grau II"
        else:
            return "Obesidade grau III"
    except:
        return "Erro na classificação"

def interpretar_sinais_vitais(sinais_vitais):
    """
    Função completa para interpretar todos os sinais vitais de uma vez
    Retorna um dicionário com todas as classificações
    """
    if not sinais_vitais:
        return {}
    
    interpretacao = {}
    
    # Pressão arterial
    if sinais_vitais.get('pressao_arterial'):
        interpretacao['pa_classificacao'] = classificar_pressao_arterial(
            sinais_vitais['pressao_arterial']
        )
    
    # Frequência cardíaca
    if sinais_vitais.get('frequencia_cardiaca'):
        interpretacao['fc_classificacao'] = classificar_frequencia_cardiaca(
            sinais_vitais['frequencia_cardiaca']
        )
    
    # Frequência respiratória
    if sinais_vitais.get('frequencia_respiratoria'):
        interpretacao['fr_classificacao'] = classificar_frequencia_respiratoria(
            sinais_vitais['frequencia_respiratoria']
        )
    
    # Temperatura
    if sinais_vitais.get('temperatura'):
        interpretacao['temp_classificacao'] = classificar_temperatura(
            sinais_vitais['temperatura']
        )
    
    # Saturação de oxigênio
    if sinais_vitais.get('saturacao_oxigenio'):
        interpretacao['spo2_classificacao'] = classificar_saturacao_oxigenio(
            sinais_vitais['saturacao_oxigenio']
        )
    
    # Glicemia
    if sinais_vitais.get('glicemia'):
        interpretacao['glicemia_classificacao'] = classificar_glicemia(
            sinais_vitais['glicemia']
        )
    
    # ===== NOVA CLASSIFICAÇÃO DE PESO =====
    if sinais_vitais.get('peso'):
        interpretacao['peso_classificacao'] = classificar_peso(
            sinais_vitais['peso']
        )
    
    return interpretacao

def gerar_alerta_sinais_vitais(sinais_vitais):
    """
    Gera alertas baseados em sinais vitais alterados
    """
    if not sinais_vitais:
        return []
    
    alertas = []
    interpretacao = interpretar_sinais_vitais(sinais_vitais)
    
    # Verificar cada classificação e gerar alerta se necessário
    if interpretacao.get('pa_classificacao') in ['Hipotensão', 'Hipertensão Estágio 2', 'Crise Hipertensiva']:
        alertas.append(f"Pressão arterial: {interpretacao['pa_classificacao']}")
    
    if interpretacao.get('fc_classificacao') in ['Bradicardia', 'Taquicardia severa']:
        alertas.append(f"Frequência cardíaca: {interpretacao['fc_classificacao']}")
    
    if interpretacao.get('fr_classificacao') in ['Bradipneia', 'Taquipneia severa']:
        alertas.append(f"Frequência respiratória: {interpretacao['fr_classificacao']}")
    
    if interpretacao.get('temp_classificacao') in ['Hipotermia', 'Febre muito alta (hipertermia)']:
        alertas.append(f"Temperatura: {interpretacao['temp_classificacao']}")
    
    if interpretacao.get('spo2_classificacao') in ['Hipóxia moderada', 'Hipóxia severa']:
        alertas.append(f"Saturação de O2: {interpretacao['spo2_classificacao']}")
    
    if interpretacao.get('glicemia_classificacao') in ['Hipoglicemia', 'Diabetes não controlado']:
        alertas.append(f"Glicemia: {interpretacao['glicemia_classificacao']}")
    
    # ===== NOVO ALERTA DE PESO =====
    if interpretacao.get('peso_classificacao') in ['Abaixo do peso severo', 'Obesidade Grau II', 'Obesidade Grau III']:
        alertas.append(f"Peso: {interpretacao['peso_classificacao']} - Requer acompanhamento nutricional")
    
    return alertas

def calcular_dosagem_por_peso(peso, dose_por_kg, medicamento):
    """
    Calcula a dosagem de medicamento baseada no peso
    """
    if not peso or peso <= 0:
        return None
    
    try:
        peso_float = float(peso)
        dose_total = peso_float * dose_por_kg
        
        return {
            'peso': peso_float,
            'dose_por_kg': dose_por_kg,
            'dose_total': round(dose_total, 2),
            'medicamento': medicamento,
            'observacao': f"Dose calculada com base no peso de {peso_float}kg"
        }
    except:
        return None