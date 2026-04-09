# utils/receitas_data.py

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
            'observacoes': 'Tomar com as refeições. Aumenta o pH urinário e inibe a formação de cristais de oxalato.'
        },
        {
            'nome': 'Hidratação Oral',
            'apresentacao': 'Água',
            'posologia': '2-3 litros por dia',
            'frequencia': 'Distribuído ao longo do dia',
            'duracao': 'Contínuo',
            'via': 'Oral',
            'quantidade': '90 litros (30 dias)',
            'observacoes': 'FUNDAMENTAL - aumentar ingestão de líquidos para diluir a urina e prevenir formação de cristais.'
        },
        {
            'nome': 'Alopurinol',
            'apresentacao': 'Comprimidos 300 mg',
            'posologia': '1 comprimido',
            'frequencia': '1 vez ao dia',
            'duracao': '90 dias',
            'via': 'Oral',
            'quantidade': '90 comprimidos',
            'observacoes': 'Reduz a excreção de oxalato urinário em casos de hiperoxalúria.'
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
            'observacoes': 'Tomar pela manhã. Tiazídico - primeira linha para hipertensão arterial.'
        },
        {
            'nome': 'Losartana Potássica',
            'apresentacao': 'Comprimidos 50 mg',
            'posologia': '1 comprimido',
            'frequencia': '1 vez ao dia',
            'duracao': '30 dias',
            'via': 'Oral',
            'quantidade': '30 comprimidos',
            'observacoes': 'BRA - primeira linha para hipertensão, especialmente em diabéticos.'
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
            'observacoes': 'PRIMEIRA LINHA ABSOLUTA para Diabetes Mellitus tipo 2. Tomar com as refeições.'
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
            'observacoes': 'Alternativa de primeira linha para infecção urinária.'
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
            'observacoes': 'ÚNICO ANALGÉSICO SEGURO - NÃO USAR AAS OU AINES.'
        },
        {
            'nome': 'Hidratação Oral',
            'apresentacao': 'Soro de reidratação oral',
            'posologia': '60-80 ml/kg/dia',
            'frequencia': 'Contínua',
            'duracao': 'ATÉ MELHORA',
            'via': 'Oral',
            'quantidade': '6 litros',
            'observacoes': 'FUNDAMENTAL - base do tratamento da dengue.'
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
            'observacoes': 'Primeira linha para pneumonia comunitária.'
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
            'observacoes': 'Primeira linha para anemia ferropriva. Tomar com suco cítrico.'
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
    
    'malaria': [
        {
            'nome': 'Artemeter + Lumefantrina (ACT)',
            'apresentacao': 'Comprimidos 20/120 mg',
            'posologia': '4 comprimidos por dose',
            'frequencia': '2 vezes ao dia',
            'duracao': '3 dias',
            'via': 'Oral',
            'quantidade': '24 comprimidos',
            'observacoes': 'Terapia Combinada à Base de Artemisinina - primeira linha OMS.'
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