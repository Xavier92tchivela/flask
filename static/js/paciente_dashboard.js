// static/js/paciente_dashboard.js

let pacienteId = null;
let calendar = null;

document.addEventListener('DOMContentLoaded', function() {
    // Verificar se estamos na página do paciente
    if (!document.body.classList.contains('paciente-page')) {
        return;
    }
    
    // Obter ID do paciente
    pacienteId = document.getElementById('pacienteId')?.value || 
                document.querySelector('[data-paciente-id]')?.dataset.pacienteId;
    
    // Configurar eventos
    configurarEventListeners();
    
    // Inicializar funcionalidades específicas
    inicializarFuncionalidades();
    
    console.log('Script paciente_dashboard.js carregado');
});

function configurarEventListeners() {
    // Botões de ação
    const botoesMap = {
        'btnEditarPerfil': editarPerfil,
        'btnBaixarReceita': baixarReceita,
        'btnBaixarLaudo': baixarLaudo,
        'btnAgendarConsulta': agendarConsulta,
        'btnVerConsultas': verConsultas,
        'btnVerDiagnosticos': verDiagnosticos,
        'btnImprimirConsulta': imprimirConsulta,
        'btnExportarPDF': exportarParaPDF
    };
    
    Object.entries(botoesMap).forEach(([id, handler]) => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', handler);
        }
    });
    
    // Formulários
    const formPerfil = document.getElementById('formPerfil');
    if (formPerfil) {
        formPerfil.addEventListener('submit', salvarPerfil);
    }
    
    const formAgendar = document.getElementById('formAgendarConsulta');
    if (formAgendar) {
        formAgendar.addEventListener('submit', submitAgendarConsulta);
        
        // Configurar datepicker
        const dateInput = document.getElementById('dataConsulta');
        if (dateInput) {
            dateInput.min = new Date().toISOString().split('T')[0];
            dateInput.addEventListener('change', verificarDisponibilidade);
        }
    }
}

function inicializarFuncionalidades() {
    // Inicializar calendário se existir
    const calendarEl = document.getElementById('calendar');
    if (calendarEl) {
        inicializarCalendario();
    }
    
    // Inicializar gráficos se existirem
    const ctxConsultas = document.getElementById('chartConsultas');
    if (ctxConsultas) {
        inicializarGraficoConsultas(ctxConsultas);
    }
    
    const ctxDiagnosticos = document.getElementById('chartDiagnosticos');
    if (ctxDiagnosticos) {
        inicializarGraficoDiagnosticos(ctxDiagnosticos);
    }
}

function inicializarCalendario() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    try {
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            locale: 'pt-br',
            events: '/paciente/api/consultas/agendadas',
            eventClick: function(info) {
                mostrarDetalhesConsulta(info.event.id);
            },
            dateClick: function(info) {
                abrirModalAgendamento(info.dateStr);
            }
        });
        calendar.render();
    } catch (error) {
        console.error('Erro ao inicializar calendário:', error);
    }
}

function inicializarGraficoConsultas(ctx) {
    if (!ctx) return;
    
    fetch('/paciente/api/estatisticas/consultas')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels || ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
                    datasets: [{
                        label: 'Consultas por Mês',
                        data: data.values || [12, 19, 3, 5, 2, 3],
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Histórico de Consultas'
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Erro ao carregar estatísticas:', error);
        });
}

function inicializarGraficoDiagnosticos(ctx) {
    if (!ctx) return;
    
    fetch('/paciente/api/estatisticas/diagnosticos')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels || ['Finalizados', 'Pendentes', 'Em Análise'],
                    datasets: [{
                        label: 'Status dos Diagnósticos',
                        data: data.values || [10, 2, 1],
                        backgroundColor: [
                            'rgba(75, 192, 192, 0.2)',
                            'rgba(255, 205, 86, 0.2)',
                            'rgba(255, 99, 132, 0.2)'
                        ],
                        borderColor: [
                            'rgba(75, 192, 192, 1)',
                            'rgba(255, 205, 86, 1)',
                            'rgba(255, 99, 132, 1)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Status dos Exames'
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Erro ao carregar estatísticas:', error);
        });
}

// ========== FUNÇÕES DE PERFIL ==========

function editarPerfil() {
    // Habilitar edição dos campos do perfil
    const campos = ['telefone', 'endereco', 'data_nascimento', 'genero'];
    const form = document.getElementById('formPerfil');
    
    campos.forEach(campo => {
        const input = form.querySelector(`[name="${campo}"]`);
        if (input) {
            input.removeAttribute('readonly');
            input.classList.remove('form-control-plaintext');
            input.classList.add('form-control');
        }
    });
    
    // Mostrar botões de ação
    document.getElementById('btnSalvarPerfil')?.classList.remove('d-none');
    document.getElementById('btnCancelarEdicao')?.classList.remove('d-none');
    document.getElementById('btnEditarPerfil')?.classList.add('d-none');
}

function salvarPerfil(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const botaoSalvar = document.getElementById('btnSalvarPerfil');
    
    if (!botaoSalvar) return;
    
    const originalText = botaoSalvar.innerHTML;
    botaoSalvar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
    botaoSalvar.disabled = true;
    
    fetch('/paciente/perfil', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            window.location.reload();
        } else {
            throw new Error('Erro ao salvar perfil');
        }
    })
    .catch(error => {
        mostrarErro('Erro ao salvar perfil: ' + error.message);
        botaoSalvar.innerHTML = originalText;
        botaoSalvar.disabled = false;
    });
}

// ========== FUNÇÕES DE CONSULTAS ==========

function agendarConsulta() {
    window.location.href = '/paciente/agendar';
}

function verConsultas() {
    window.location.href = '/paciente/consultas';
}

function verDiagnosticos() {
    window.location.href = '/paciente/diagnosticos';
}

function mostrarDetalhesConsulta(consultaId) {
    window.location.href = `/paciente/consultas/${consultaId}`;
}

function imprimirConsulta(consultaId) {
    consultaId = consultaId || document.querySelector('[data-consulta-id]')?.dataset.consultaId;
    
    if (!consultaId) {
        mostrarErro('ID da consulta não encontrado');
        return;
    }
    
    const janela = window.open(`/paciente/consultas/${consultaId}/print`, '_blank');
    setTimeout(() => {
        if (janela) {
            janela.print();
        }
    }, 500);
}

// ========== FUNÇÕES DE DIAGNÓSTICOS ==========

function baixarLaudo(diagnosticoId) {
    diagnosticoId = diagnosticoId || document.querySelector('[data-diagnostico-id]')?.dataset.diagnosticoId;
    
    if (!diagnosticoId) {
        mostrarErro('ID do diagnóstico não encontrado');
        return;
    }
    
    const botao = event?.target || document.querySelector('#btnBaixarLaudo');
    if (botao) {
        const originalText = botao.innerHTML;
        botao.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando PDF...';
        botao.disabled = true;
        
        fetch(`/paciente/api/diagnostico/pdf/${diagnosticoId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erro ao gerar PDF');
                }
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `laudo_medico_${new Date().toISOString().split('T')[0]}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            })
            .catch(error => {
                mostrarErro('Erro ao baixar laudo: ' + error.message);
            })
            .finally(() => {
                botao.innerHTML = originalText;
                botao.disabled = false;
            });
    }
}

function exportarParaPDF() {
    // Lógica para exportar dados do paciente em PDF
    alert('Funcionalidade de exportação em desenvolvimento.');
}

// ========== FUNÇÕES DE AGENDAMENTO ==========

function submitAgendarConsulta(event) {
    event.preventDefault();
    
    const form = event.target;
    const botaoAgendar = form.querySelector('button[type="submit"]');
    
    if (!botaoAgendar) return;
    
    const originalText = botaoAgendar.innerHTML;
    botaoAgendar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Agendando...';
    botaoAgendar.disabled = true;
    
    const formData = new FormData(form);
    
    fetch('/paciente/agendar', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '/paciente/consultas';
        } else {
            throw new Error('Erro ao agendar consulta');
        }
    })
    .catch(error => {
        mostrarErro('Erro ao agendar consulta: ' + error.message);
        botaoAgendar.innerHTML = originalText;
        botaoAgendar.disabled = false;
    });
}

function verificarDisponibilidade() {
    const medicoId = document.getElementById('medico_id')?.value;
    const dataHora = document.getElementById('dataConsulta')?.value;
    
    if (!medicoId || !dataHora) return;
    
    fetch(`/paciente/api/disponibilidade?medico_id=${medicoId}&data_hora=${dataHora}`)
        .then(response => response.json())
        .then(data => {
            const mensagemDiv = document.getElementById('disponibilidadeMsg');
            if (mensagemDiv) {
                if (data.disponivel) {
                    mensagemDiv.innerHTML = '<span class="text-success"><i class="fas fa-check-circle"></i> Horário disponível!</span>';
                    mensagemDiv.classList.remove('d-none');
                } else {
                    mensagemDiv.innerHTML = '<span class="text-danger"><i class="fas fa-times-circle"></i> Horário indisponível. Tente outro horário.</span>';
                    mensagemDiv.classList.remove('d-none');
                }
            }
        })
        .catch(error => {
            console.error('Erro ao verificar disponibilidade:', error);
        });
}

function abrirModalAgendamento(dataStr) {
    const modal = new bootstrap.Modal(document.getElementById('modalAgendamentoRapido'));
    if (modal) {
        const dataInput = document.getElementById('dataAgendamentoRapido');
        if (dataInput) {
            dataInput.value = dataStr;
        }
        modal.show();
    }
}

// ========== FUNÇÕES AUXILIARES ==========

function mostrarErro(mensagem) {
    // Criar toast de erro
    const toast = document.createElement('div');
    toast.className = 'position-fixed top-0 end-0 p-3';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="toast show" role="alert">
            <div class="toast-header bg-danger text-white">
                <strong class="me-auto">Erro</strong>
                <button type="button" class="btn-close btn-close-white" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
            <div class="toast-body">
                <i class="fas fa-exclamation-circle me-2"></i> ${mensagem}
            </div>
        </div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

function mostrarSucesso(mensagem) {
    // Criar toast de sucesso
    const toast = document.createElement('div');
    toast.className = 'position-fixed top-0 end-0 p-3';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="toast show" role="alert">
            <div class="toast-header bg-success text-white">
                <strong class="me-auto">Sucesso</strong>
                <button type="button" class="btn-close btn-close-white" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
            <div class="toast-body">
                <i class="fas fa-check-circle me-2"></i> ${mensagem}
            </div>
        </div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 3000);
}

// ========== EXPORTAÇÃO ==========

window.PacienteDashboard = {
    editarPerfil,
    baixarLaudo,
    agendarConsulta,
    verConsultas,
    verDiagnosticos,
    imprimirConsulta,
    mostrarDetalhesConsulta
};