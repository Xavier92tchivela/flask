// static/js/medico_analise.js

// Variáveis globais
let CONSULTA_ID = null;
let receitaAtual = null;
let pacienteNome = '';
let modais = {};
let API_PREFIX = '/medico'; // Adicionar prefixo das rotas do médico

// Inicialização quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    // Verificar se estamos na página correta
    if (!document.getElementById('analiseForm')) {
        return;
    }
    
    // Inicializar variáveis
    CONSULTA_ID = document.getElementById('consultaId')?.value || 
                  document.querySelector('[data-consulta-id]')?.dataset.consultaId;
    
    if (!CONSULTA_ID) {
        console.error('ID da consulta não encontrado');
        mostrarErro('ID da consulta não encontrado. Recarregue a página.');
        return;
    }
    
    pacienteNome = document.getElementById('pacienteNome')?.value || 
                   document.querySelector('[data-paciente-nome]')?.dataset.pacienteNome;
    
    // Inicializar modais do Bootstrap
    inicializarModais();
    
    // Configurar event listeners
    configurarEventListeners();
    
    // Configurar para dispositivos móveis
    ajustarParaMobile();
    
    console.log('Script médico_analise.js carregado para consulta:', CONSULTA_ID);
});

// ========== FUNÇÕES DE INICIALIZAÇÃO ==========

function inicializarModais() {
    // Inicializar todos os modais
    const modalElements = [
        'concordanciaModal',
        'discordanciaModal',
        'chatModal',
        'receitaModal',
        'editarReceitaModal'
    ];
    
    modalElements.forEach(modalId => {
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            modais[modalId] = new bootstrap.Modal(modalElement);
        }
    });
}

function configurarEventListeners() {
    // Formulário de análise
    const analiseForm = document.getElementById('analiseForm');
    if (analiseForm) {
        analiseForm.addEventListener('submit', handleAnaliseSubmit);
    }
    
    // Botões com onclick inline
    document.querySelectorAll('[onclick]').forEach(btn => {
        const onclick = btn.getAttribute('onclick');
        
        if (onclick.includes('usarAnaliseLocal')) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', usarAnaliseLocal);
        }
        if (onclick.includes('gerarReceitaMedica')) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', gerarReceitaMedica);
        }
        if (onclick.includes('editarReceita')) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', editarReceita);
        }
    });
    
    // Botões de ação na área de resultados
    configurarBotoesAcao();
    
    // Chat input
    const mensagemChat = document.getElementById('mensagemChat');
    if (mensagemChat) {
        mensagemChat.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                enviarMensagem();
            }
        });
    }
}

function configurarBotoesAcao() {
    // Mapear botões por ID
    const botoesMap = {
        // Botões principais
        'btnImprimir': () => window.print(),
        'btnCopiar': copiarReceita,
        'btnReceita': gerarReceitaMedica,
        'btnChat': abrirChatDiagnostico,
        'btnPDF': gerarPDF,
        'btnSalvar': salvarDiagnosticoRevisado,
        
        // Botões no modal de receita
        'btnConcordarModal': concordarReceitaDireta,
        'btnDiscordarModal': mostrarModalDiscordancia,
        'btnImprimirModal': () => window.print(),
        'btnEditarModal': editarReceita,
        'btnPDFModal': gerarPDF,
        'btnNovaReceitaModal': gerarReceitaMedica,
        'btnChatModal': abrirChatDiagnostico,
        'btnCopiarModal': copiarReceita,
        'btnSalvarModal': salvarDiagnosticoRevisado,
        
        // Botões de chat
        'btnSugestoes': sugerirPerguntas,
        'btnEnviarChat': enviarMensagem,
        'btnFinalizarChat': finalizarDiscussao,
        
        // Botões de modais
        'btnConfirmarConcordancia': confirmarConcordancia,
        'btnConfirmarDiscordancia': confirmarDiscordancia,
        'btnSalvarEditada': salvarReceitaEditada
    };
    
    // Aplicar event listeners
    Object.entries(botoesMap).forEach(([id, handler]) => {
        const btn = document.getElementById(id);
        if (btn) {
            // Remover onclick inline se existir
            if (btn.getAttribute('onclick')) {
                btn.removeAttribute('onclick');
            }
            btn.addEventListener('click', handler);
        }
    });
}

function ajustarParaMobile() {
    if (window.innerWidth < 768) {
        const chatContainer = document.getElementById('chatMessages');
        if (chatContainer) {
            chatContainer.style.height = '250px';
        }
        
        const receitaContainer = document.querySelector('.receita-medica');
        if (receitaContainer) {
            receitaContainer.style.maxHeight = '300px';
        }
    }
}

// ========== FUNÇÕES PARA ANÁLISE DE EXAMES ==========

async function handleAnaliseSubmit(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('imagem');
    const tipoExame = document.getElementById('tipo_exame');
    const observacoes = document.getElementById('observacoes_exame').value;
    
    if (!fileInput.value || !tipoExame.value) {
        mostrarErro('Por favor, preencha todos os campos obrigatórios.');
        return;
    }
    
    const submitButton = event.target.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analisando...';
    submitButton.disabled = true;
    
    document.getElementById('errorAlert')?.classList.add('d-none');
    
    const formData = new FormData();
    formData.append('imagem', fileInput.files[0]);
    formData.append('tipo_exame', tipoExame.value);
    formData.append('observacoes_exame', observacoes);
    
    try {
        // Usar a rota correta com prefixo /medico
        const response = await fetch(`${API_PREFIX}/api/diagnostico/analisar/${CONSULTA_ID}`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            mostrarErro('Erro na análise: ' + data.error + '. Tente usar a análise local.');
        } else {
            window.location.reload();
        }
    } catch (error) {
        console.error('Erro na análise:', error);
        let errorMessage = 'Erro ao conectar com o serviço de análise. ';
        
        if (error.message.includes('404')) {
            errorMessage += 'Endpoint não encontrado. ';
            if (confirm('Deseja usar a análise local?')) {
                await usarAnaliseLocal();
                return;
            }
        } else if (error.message.includes('SSL') || error.message.includes('EOF')) {
            errorMessage += 'Problema de conexão SSL. ';
        } else if (error.message.includes('fetch') || error.message.includes('Network')) {
            errorMessage += 'Problema de rede. Verifique sua conexão.';
        } else {
            errorMessage += error.message;
        }
        
        mostrarErro(errorMessage);
    } finally {
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
    }
}

async function usarAnaliseLocal() {
    const tipoExame = document.getElementById('tipo_exame').value;
    const observacoes = document.getElementById('observacoes_exame').value;
    
    if (!tipoExame) {
        mostrarErro('Selecione o tipo de exame primeiro.');
        return;
    }

    const submitButton = document.querySelector('#analiseForm button[type="submit"]');
    const originalText = submitButton.innerHTML;
    
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando análise local...';
    submitButton.disabled = true;

    try {
        const response = await fetch(`${API_PREFIX}/api/analise-local`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tipo_exame: tipoExame,
                observacoes: observacoes,
                consulta_id: CONSULTA_ID,
                paciente_nome: pacienteNome || 'Paciente'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            window.location.reload();
        } else {
            mostrarErro(data.error || 'Erro ao gerar análise local');
        }
    } catch (error) {
        mostrarErro('Erro de conexão: ' + error.message);
    } finally {
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
    }
}

// ========== FUNÇÕES PARA GERAÇÃO DE PDF ==========

async function gerarPDF(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    const button = event?.currentTarget || this;
    const originalHTML = button.innerHTML;
    
    try {
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando PDF...';
        button.disabled = true;
        
        console.log('Iniciando geração de PDF para consulta:', CONSULTA_ID);
        
        // Tentar rota específica ou alternativa
        const response = await fetch(`${API_PREFIX}/api/receita/pdf/${CONSULTA_ID}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/pdf',
                'Cache-Control': 'no-cache'
            }
        });
        
        if (!response.ok) {
            // Tentar rota alternativa se a primeira falhar
            const altResponse = await fetch(`/api/receita/pdf/${CONSULTA_ID}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/pdf',
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (!altResponse.ok) {
                throw new Error('Erro ao gerar PDF: ' + altResponse.status);
            }
            
            const blob = await altResponse.blob();
            downloadPDF(blob);
        } else {
            const blob = await response.blob();
            downloadPDF(blob);
        }
        
        console.log('PDF gerado com sucesso');
    } catch (error) {
        console.error('Erro ao gerar PDF:', error);
        
        // Oferecer alternativa
        if (confirm('Não foi possível gerar PDF. Deseja imprimir a receita como alternativa?')) {
            imprimirReceitaDiretamente();
        } else {
            mostrarErro('Erro ao gerar PDF: ' + error.message);
        }
    } finally {
        button.innerHTML = originalHTML;
        button.disabled = false;
    }
}

function downloadPDF(blob) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `receita_${pacienteNome || 'paciente'}_${new Date().toISOString().split('T')[0]}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function imprimirReceitaDiretamente() {
    const conteudo = document.getElementById('conteudoReceita')?.innerHTML || 
                    document.querySelector('.receita-medica')?.innerHTML;
    
    if (!conteudo) {
        mostrarErro('Nenhuma receita encontrada para imprimir.');
        return;
    }
    
    const janelaImpressao = window.open('', '_blank');
    janelaImpressao.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Receita Médica - ${pacienteNome}</title>
            <style>
                @media print {
                    @page { margin: 2cm; }
                }
                body { 
                    font-family: Arial, sans-serif; 
                    margin: 2cm;
                    line-height: 1.6;
                    color: #000;
                }
                .header { 
                    text-align: center; 
                    margin-bottom: 2cm;
                    border-bottom: 3px solid #000;
                    padding-bottom: 0.5cm;
                }
                .paciente-info {
                    margin: 1cm 0;
                    padding: 0.5cm;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                .content {
                    margin: 1cm 0;
                    min-height: 10cm;
                }
                .assinatura {
                    margin-top: 3cm;
                    text-align: right;
                }
                .data {
                    text-align: left;
                    margin-top: 2cm;
                }
                .carimbo {
                    margin-top: 1cm;
                    padding-top: 0.5cm;
                    border-top: 1px dashed #666;
                    font-size: 0.9em;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1 style="margin-bottom: 0.5cm;">RECEITA MÉDICA</h1>
                <p style="margin: 0;">${new Date().toLocaleDateString('pt-BR')}</p>
            </div>
            
            <div class="paciente-info">
                <p style="margin: 0.2cm 0;"><strong>PACIENTE:</strong> ${pacienteNome}</p>
                <p style="margin: 0.2cm 0;"><strong>DATA:</strong> ${new Date().toLocaleDateString('pt-BR')}</p>
                <p style="margin: 0.2cm 0;"><strong>REGISTRO:</strong> ${CONSULTA_ID}</p>
            </div>
            
            <div class="content">
                ${conteudo}
            </div>
            
            <div class="assinatura">
                <p style="margin-bottom: 2cm;">_________________________</p>
                <p><strong>Dr(a). [Nome do Médico]</strong></p>
                <p>CRM: [Número do CRM]</p>
            </div>
        </body>
        </html>
    `);
    
    setTimeout(() => {
        janelaImpressao.print();
        setTimeout(() => {
            janelaImpressao.close();
        }, 1000);
    }, 1000);
}

// ========== FUNÇÕES PARA CONCORDÂNCIA/DISCORDÂNCIA ==========

function concordarReceitaDireta() {
    modais.concordanciaModal?.show();
}

function mostrarModalDiscordancia() {
    modais.discordanciaModal?.show();
}

async function confirmarConcordancia() {
    const observacoes = document.getElementById('observacoesMedico')?.value || '';
    const confirmButton = document.querySelector('#concordanciaModal .btn-success');
    
    if (!confirmButton) return;
    
    const originalText = confirmButton.innerHTML;
    
    try {
        confirmButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
        confirmButton.disabled = true;
        
        const response = await fetch(`${API_PREFIX}/api/receita/concordancia/${CONSULTA_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                concordancia: true, 
                observacoes: observacoes 
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            modais.concordanciaModal?.hide();
            modais.receitaModal?.hide();
            
            if (receitaAtual) {
                atualizarReceitaPrincipal(receitaAtual, 'Receita Aprovada e Salva!');
            }
            
            mostrarMensagemSucesso('Receita aprovada com sucesso!');
        } else {
            throw new Error(data.error || 'Erro ao salvar');
        }
    } catch (error) {
        mostrarErro('Erro ao confirmar concordância: ' + error.message);
    } finally {
        confirmButton.innerHTML = originalText;
        confirmButton.disabled = false;
    }
}

async function confirmarDiscordancia() {
    const observacoes = document.getElementById('observacoesDiscordancia')?.value || '';
    const confirmButton = document.querySelector('#discordanciaModal .btn-warning');
    
    if (!confirmButton) return;
    
    const originalText = confirmButton.innerHTML;
    
    try {
        confirmButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
        confirmButton.disabled = true;
        
        const response = await fetch(`${API_PREFIX}/api/receita/concordancia/${CONSULTA_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                concordancia: false, 
                observacoes: observacoes 
            })
        });
        
        const data = await response.json();
        
        modais.discordanciaModal?.hide();
        modais.receitaModal?.hide();
        
        if (data.success && data.iniciar_chat) {
            setTimeout(() => {
                abrirChatDiscordancia(observacoes);
            }, 300);
        } else {
            mostrarMensagemSucesso('Discordância registrada com sucesso!');
        }
        
    } catch (error) {
        mostrarErro('Erro ao confirmar discordância: ' + error.message);
    } finally {
        confirmButton.innerHTML = originalText;
        confirmButton.disabled = false;
    }
}

// ========== FUNÇÕES PARA EDIÇÃO DE RECEITA ==========

function editarReceita() {
    const conteudoReceita = document.getElementById('conteudoReceita');
    
    if (!conteudoReceita || !conteudoReceita.innerHTML.trim()) {
        mostrarErro('Nenhuma receita encontrada para editar. Gere uma receita primeiro.');
        return;
    }
    
    let conteudoCompleto = conteudoReceita.innerHTML;
    
    const timestampDiv = conteudoReceita.querySelector('.text-end, .text-muted');
    if (timestampDiv) {
        timestampDiv.remove();
    }
    
    modais.receitaModal?.hide();
    
    const editor = document.getElementById('editorReceita');
    if (editor) {
        editor.value = htmlParaTextoEditavel(conteudoCompleto);
    }
    
    modais.editarReceitaModal?.show();
}

function htmlParaTextoEditavel(html) {
    if (!html) return '';
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    let textoFormatado = tempDiv.textContent || tempDiv.innerText || '';
    
    textoFormatado = textoFormatado
        .replace(/\n\s*\n\s*\n/g, '\n\n')
        .replace(/ +/g, ' ')
        .trim();
    
    return textoFormatado;
}

async function salvarReceitaEditada() {
    const conteudoEditado = document.getElementById('editorReceita')?.value.trim();
    
    if (!conteudoEditado) {
        mostrarErro('A receita não pode estar vazia.');
        return;
    }
    
    const saveButton = document.querySelector('#editarReceitaModal .btn-success');
    if (!saveButton) return;
    
    const originalText = saveButton.innerHTML;
    saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
    saveButton.disabled = true;
    
    try {
        const conteudoFormatado = formatarTextoParaHTML(conteudoEditado);
        
        const response = await fetch(`${API_PREFIX}/api/receita/editar/${CONSULTA_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                receita: conteudoFormatado,
                receita_texto: conteudoEditado
            })
        });
        
        if (!response.ok) {
            throw new Error('Erro na resposta do servidor: ' + response.status);
        }
        
        const data = await response.json();
        
        if (data.success) {
            modais.editarReceitaModal?.hide();
            
            if (document.getElementById('conteudoReceita')) {
                document.getElementById('conteudoReceita').innerHTML = conteudoFormatado;
            }
            
            const receitaContent = document.getElementById('receitaContent');
            if (receitaContent) {
                receitaContent.innerHTML = conteudoFormatado;
            }
            
            receitaAtual = conteudoFormatado;
            
            mostrarMensagemSucesso('Receita editada com sucesso!');
        } else {
            throw new Error(data.error || 'Erro desconhecido ao salvar');
        }
    } catch (error) {
        console.error('Erro ao salvar receita:', error);
        mostrarErro('Erro ao salvar receita: ' + error.message);
    } finally {
        saveButton.innerHTML = originalText;
        saveButton.disabled = false;
    }
}

function formatarTextoParaHTML(texto) {
    if (!texto) return '';
    
    let html = `<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">`;
    
    const linhas = texto.split('\n');
    
    linhas.forEach((linha, index) => {
        const linhaTrim = linha.trim();
        
        if (!linhaTrim && index < linhas.length - 1) {
            html += '<br>';
            return;
        }
        
        if (!linhaTrim) return;
        
        if (linhaTrim === linhaTrim.toUpperCase() || linhaTrim.endsWith(':')) {
            html += `<div style="font-weight: bold; margin: 15px 0 8px 0; padding: 8px 12px; background: #f8f9fa; border-left: 4px solid #007bff;">
                        ${linhaTrim}
                     </div>`;
        }
        else if (linhaTrim.startsWith('•') || linhaTrim.startsWith('-')) {
            html += `<div style="margin: 5px 0 5px 20px; padding-left: 10px;">
                        ${linhaTrim}
                     </div>`;
        }
        else {
            html += `<div style="margin: 8px 0; line-height: 1.4;">
                        ${linhaTrim}
                     </div>`;
        }
    });
    
    html += `</div>`;
    return html;
}

// ========== FUNÇÃO PARA GERAR RECEITA MÉDICA ==========

async function gerarReceitaMedica() {
    modais.receitaModal?.show();
    
    const conteudoReceita = document.getElementById('conteudoReceita');
    if (!conteudoReceita) return;
    
    conteudoReceita.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <p class="mt-2 small">Gerando receita médica com IA...</p>
        </div>
    `;
    
    document.getElementById('secaoConcordancia')?.classList.add('d-none');
    
    try {
        const response = await fetch(`${API_PREFIX}/api/receita/gerar/${CONSULTA_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const data = await response.json();
        
        if (data.error) {
            conteudoReceita.innerHTML = `
                <div class="alert alert-danger py-2">
                    <h5 class="h6">Erro ao gerar receita</h5>
                    <p class="small">${data.error}</p>
                </div>
            `;
        } else {
            receitaAtual = data.receita;
            pacienteNome = data.paciente;
            
            const nomePacienteElement = document.getElementById('nomePacienteReceita');
            if (nomePacienteElement) {
                nomePacienteElement.textContent = data.paciente;
            }
            
            conteudoReceita.innerHTML = data.receita;
            document.getElementById('secaoConcordancia')?.classList.remove('d-none');
            
            const timestamp = document.createElement('div');
            timestamp.className = 'text-end text-muted mt-2';
            timestamp.innerHTML = `<small>Gerado em: ${data.timestamp}</small>`;
            conteudoReceita.appendChild(timestamp);

            atualizarReceitaPrincipal(data.receita, 'Receita Médica Gerada!');
        }
    } catch (error) {
        console.error('Erro ao gerar receita:', error);
        conteudoReceita.innerHTML = `
            <div class="alert alert-danger py-2">
                <h5 class="h6">Erro de conexão</h5>
                <p class="small">Não foi possível conectar com a IA para gerar a receita.</p>
                <button class="btn btn-warning btn-sm mt-2" onclick="usarAnaliseLocal()">
                    Usar Análise Básica
                </button>
            </div>
        `;
    }
}

// ========== FUNÇÃO PARA ATUALIZAR A RECEITA PRINCIPAL ==========

function atualizarReceitaPrincipal(conteudoReceita, mensagemSucesso) {
    const semResultado = document.getElementById('semResultado');
    if (semResultado) {
        semResultado.remove();
    }
    
    const receitaContent = document.getElementById('receitaContent');
    if (receitaContent) {
        receitaContent.innerHTML = conteudoReceita;
        
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success py-2 mb-3';
        alertDiv.innerHTML = `
            <h5 class="h6 mb-0">
                <i class="fas fa-check-circle"></i> ${mensagemSucesso}
            </h5>
            <small>Use os botões abaixo para editar, exportar ou salvar a receita.</small>
        `;
        receitaContent.prepend(alertDiv);
    }
}

// ========== FUNÇÕES PARA CHAT COM IA ==========

function abrirChatDiagnostico() {
    modais.chatModal?.show();
    
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="chat-message ai-message">
                <div class="message-header">
                    <strong>Assistente IA</strong>
                    <small class="text-muted">Agora</small>
                </div>
                <div class="message-content">
                    Olá, Dr(a). Estou aqui para discutir o diagnóstico e ajudar com qualquer dúvida ou ajuste.
                    Como posso ajudá-lo(a) hoje?
                </div>
            </div>
        `;
    }
}

function abrirChatDiscordancia(observacoes) {
    modais.chatModal?.show();
    
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    chatMessages.innerHTML = '';
    
    adicionarMensagem(
        `Olá, Dr(a). Entendo que você discorda da receita gerada. Vamos discutir e ajustar juntos. ` +
        `O que específicamente você gostaria de modificar?`,
        'ai'
    );
    
    if (observacoes) {
        setTimeout(() => {
            adicionarMensagem(
                `Minhas preocupações: ${observacoes}`,
                'doctor'
            );
        }, 1000);
    }
}

async function enviarMensagem() {
    const mensagemInput = document.getElementById('mensagemChat');
    const mensagem = mensagemInput?.value.trim();
    
    if (!mensagem) return;
    
    adicionarMensagem(mensagem, 'doctor');
    mensagemInput.value = '';
    
    const sugestoesContainer = document.querySelector('.sugestoes-container');
    if (sugestoesContainer) sugestoesContainer.remove();
    
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'chat-message ai-message';
    loadingMessage.innerHTML = `
        <div class="message-header">
            <strong>Assistente IA</strong>
            <small class="text-muted">Digitando...</small>
        </div>
        <div class="message-content">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            Processando sua pergunta...
        </div>
    `;
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    try {
        const response = await fetch(`${API_PREFIX}/api/diagnostico/chat/${CONSULTA_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ message: mensagem })
        });
        
        const data = await response.json();
        
        chatMessages.removeChild(loadingMessage);
        if (data.error) {
            adicionarMensagem('Erro ao conectar com a IA: ' + data.error, 'ai');
        } else {
            adicionarMensagem(data.response, 'ai', data.timestamp);
        }
    } catch (error) {
        chatMessages.removeChild(loadingMessage);
        adicionarMensagem('Erro de conexão com a IA. Tente novamente.', 'ai');
    }
}

function adicionarMensagem(texto, tipo, timestamp = null) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const timestampStr = timestamp || new Date().toLocaleTimeString('pt-BR', { 
        hour: '2-digit', minute: '2-digit' 
    });
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${tipo}-message`;
    messageDiv.innerHTML = `
        <div class="message-header">
            <strong>${tipo === 'ai' ? 'Assistente IA' : 'Você'}</strong>
            <small class="text-muted">${timestampStr}</small>
        </div>
        <div class="message-content">${texto}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function sugerirPerguntas() {
    const sugestoes = [
        "Explique melhor o diagnóstico",
        "Quais as evidências?",
        "Diagnósticos diferenciais?",
        "Ajustar medicação?",
        "Exames complementares?"
    ];
    
    const sugestoesContainer = document.createElement('div');
    sugestoesContainer.className = 'sugestoes-container';
    sugestoesContainer.innerHTML = '<small class="text-muted">Sugestões:</small><br>';
    
    sugestoes.forEach(sugestao => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-secondary sugestao-btn';
        btn.textContent = sugestao;
        btn.onclick = () => {
            const mensagemInput = document.getElementById('mensagemChat');
            if (mensagemInput) {
                mensagemInput.value = sugestao;
            }
            sugestoesContainer.remove();
        };
        sugestoesContainer.appendChild(btn);
    });
    
    const existingSugestoes = document.querySelector('.sugestoes-container');
    if (existingSugestoes) existingSugestoes.remove();
    
    const chatInput = document.querySelector('.chat-input');
    if (chatInput) {
        chatInput.parentNode.insertBefore(sugestoesContainer, chatInput);
    }
}

function finalizarDiscussao() {
    modais.chatModal?.hide();
    mostrarMensagemSucesso('Discussão finalizada. Use "Salvar" para aplicar mudanças.');
}

// ========== FUNÇÕES AUXILIARES ==========

function copiarReceita() {
    const receitaElement = document.querySelector('.receita-medica');
    if (!receitaElement) {
        mostrarErro('Nenhuma receita encontrada para copiar.');
        return;
    }
    
    const tempElement = document.createElement('div');
    tempElement.innerHTML = receitaElement.innerHTML;
    const receitaText = tempElement.textContent || tempElement.innerText;
    
    navigator.clipboard.writeText(receitaText)
        .then(() => {
            alert('Texto copiado para a área de transferência!');
        })
        .catch(err => {
            console.error('Erro ao copiar:', err);
            mostrarErro('Erro ao copiar. Tente selecionar e copiar manualmente.');
        });
}

async function salvarDiagnosticoRevisado() {
    if (!confirm('Salvar alterações no diagnóstico?')) {
        return;
    }
    
    const receitaElement = document.querySelector('.receita-medica');
    if (!receitaElement) {
        mostrarErro('Nenhuma receita encontrada para salvar.');
        return;
    }
    
    try {
        const response = await fetch(`${API_PREFIX}/api/diagnostico/salvar/${CONSULTA_ID}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ diagnostico: receitaElement.innerHTML })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Diagnóstico salvo!');
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            throw new Error(data.error || 'Erro ao salvar');
        }
    } catch (error) {
        mostrarErro('Erro ao salvar: ' + error.message);
    }
}

function mostrarMensagemSucesso(mensagem) {
    // Criar toast de sucesso
    const toast = document.createElement('div');
    toast.className = 'position-fixed top-0 end-0 p-3';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="toast show" role="alert">
            <div class="toast-header bg-success text-white">
                <strong class="me-auto">Sucesso</strong>
                <button type="button" class="btn-close btn-close-white" onclick="this.parentElement.parentElement.parentElement.remove()"></button>
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

function mostrarErro(mensagem) {
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    
    if (errorAlert && errorMessage) {
        errorMessage.textContent = mensagem;
        errorAlert.classList.remove('d-none');
        errorAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
        // Fallback para alert
        alert(mensagem);
    }
}

// ========== EXPORTAÇÃO PARA ESCOPO GLOBAL ==========

window.MedicoAnalise = {
    CONSULTA_ID,
    API_PREFIX,
    receitaAtual,
    pacienteNome,
    modais,
    gerarPDF,
    editarReceita,
    gerarReceitaMedica,
    mostrarErro,
    usarAnaliseLocal,
    confirmarConcordancia,
    confirmarDiscordancia,
    salvarReceitaEditada,
    enviarMensagem,
    finalizarDiscussao,
    sugerirPerguntas
};

// Expor funções individuais também
Object.keys(window.MedicoAnalise).forEach(key => {
    if (typeof window.MedicoAnalise[key] === 'function' && key !== 'handleAnaliseSubmit') {
        window[key] = window.MedicoAnalise[key];
    }
});

console.log('Módulo MedicoAnalise carregado e pronto');