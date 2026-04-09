# routes/medico/medico_pacientes.py
from flask import render_template, flash, redirect, url_for, session
import logging

logger = logging.getLogger(__name__)

def init_medico_pacientes(mysql, base):
    """Inicializa rotas de pacientes do médico"""
    
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    calcular_idade = base['calcular_idade']
    obter_info_medico = base['obter_info_medico']
    medico_required = base['medico_required']
    
    # ===== FUNÇÃO AUXILIAR PARA CONVERTER BYTES =====
    def converter_bytes_para_string(valor):
        """Converte bytes para string se necessário"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8', errors='ignore')
            except:
                return str(valor)
        return str(valor) if valor else ''
    
    # ========== ROTA: MEUS PACIENTES ==========
    @medico_required
    def meus_pacientes():
        try:
            medico_info = obter_info_medico()
            if not isinstance(medico_info, dict):
                medico_info = {'nome': 'Erro', 'especialidade': 'Erro', 'crm': ''}
            
            pacientes_lista = []
            medico_id = medico_info.get('id')
            
            if medico_id and medico_id > 0:
                pacientes_db = execute_query("""
                    SELECT DISTINCT
                        p.id, u.nome, p.data_nascimento, p.genero,
                        p.telefone, p.endereco, u.email,
                        COUNT(c.id) as total_consultas,
                        MAX(c.data_hora) as ultima_consulta
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE c.medico_id = %s
                    GROUP BY p.id, u.nome, p.data_nascimento, p.genero,
                             p.telefone, p.endereco, u.email
                    ORDER BY u.nome
                """, (medico_id,), fetch=True)
                
                if pacientes_db:
                    for p in pacientes_db:
                        # ===== CONVERSÃO DE TODOS OS CAMPOS =====
                        nome = converter_bytes_para_string(p[1])
                        telefone = converter_bytes_para_string(p[4])
                        endereco = converter_bytes_para_string(p[5])
                        email = converter_bytes_para_string(p[6])
                        
                        idade = calcular_idade(p[2]) if p[2] else ''
                        
                        # Processar gênero
                        genero = p[3]
                        if genero == 'M':
                            genero_display = 'Masculino'
                        elif genero == 'F':
                            genero_display = 'Feminino'
                        else:
                            genero_display = converter_bytes_para_string(genero) if genero else ''
                        
                        pacientes_lista.append({
                            'id': p[0],
                            'nome': nome or 'Não informado',
                            'data_nascimento': formatar_data(p[2], '%d/%m/%Y') if p[2] else '',
                            'idade': idade,
                            'genero': genero_display,
                            'telefone': telefone,
                            'endereco': endereco,
                            'email': email,
                            'total_consultas': p[7] or 0,
                            'ultima_consulta': formatar_data(p[8]) if p[8] else 'Nunca'
                        })
            else:
                flash('Complete seu cadastro no perfil para ver seus pacientes.', 'warning')
            
            return render_template('medico/pacientes.html',
                                 pacientes=pacientes_lista,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar pacientes: {e}")
            import traceback
            traceback.print_exc()
            flash('Erro ao carregar pacientes.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    return {
        'routes': [
            {'rule': '/meus-pacientes', 'view_func': meus_pacientes, 'methods': ['GET']}
        ]
    }

# Exportar a função com o nome correto
__all__ = ['init_medico_pacientes']