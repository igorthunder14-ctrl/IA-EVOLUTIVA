// Função principal para enviar a mensagem
async function enviarMensagem() {
    const input = document.getElementById("perguntaInput");
    const chatBox = document.getElementById("chat-box");
    const texto = input.value.trim();

    if (!texto) return;

    // 1. Mostra a mensagem do utilizador no chat
    chatBox.innerHTML += `
        <div class="message user-message">
            <div class="avatar">EU</div>
            <div class="bubble">${escapeHtml(texto)}</div>
        </div>
    `;
    input.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    // 2. Mostra indicador visual "A Pensar..."
    const idPensando = "pensando-" + Date.now();
    chatBox.innerHTML += `
        <div class="message ai-message" id="${idPensando}">
            <div class="avatar">AI</div>
            <div class="bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch("/perguntar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pergunta: texto })
        });
        
        const dados = await response.json();

        // Remove o indicador de "A Pensar..."
        const elementoPensando = document.getElementById(idPensando);
        if (elementoPensando) elementoPensando.remove();

        // 3. Cria a caixa para a resposta da IA e aplica o efeito de digitação
        const idMsg = "msg-ia-" + Date.now();
        chatBox.innerHTML += `
            <div class="message ai-message">
                <div class="avatar">AI</div>
                <div class="bubble" id="${idMsg}"></div>
            </div>
        `;
        chatBox.scrollTop = chatBox.scrollHeight;

        await digitarTexto(idMsg, dados.resposta);

    } catch (error) {
        const elementoPensando = document.getElementById(idPensando);
        if (elementoPensando) elementoPensando.remove();
        console.error("Erro de comunicação:", error);
    }
}

// Efeito de Máquina de Escrever (Digitação Letra por Letra)
async function digitarTexto(elementoId, texto) {
    const elemento = document.getElementById(elementoId);
    let i = 0;
    
    return new Promise(resolve => {
        function adicionarLetra() {
            if (i < texto.length) {
                elemento.innerHTML += texto.charAt(i);
                i++;
                const chatBox = document.getElementById("chat-box");
                chatBox.scrollTop = chatBox.scrollHeight;
                setTimeout(adicionarLetra, 12);
            } else {
                elemento.innerHTML += `
                    <button class="btn-voz" onclick="lerVoz(this, \`\${escapeHtml(texto)}\`)">🔊 Ouvir</button>
                `;
                resolve();
            }
        }
        adicionarLetra();
    });
}

// Síntese de Voz
function lerVoz(botao, texto) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(texto);
        utterance.lang = 'pt-BR';
        utterance.rate = 1.0;
        window.speechSynthesis.speak(utterance);
    } else {
        alert("O seu browser não suporta síntese de voz.");
    }
}

// Upload automático de ficheiros
async function enviarArquivo() {
    const fileInput = document.getElementById("fileInput");
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("arquivo", file);

    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML += `
        <div class="message ai-message">
            <div class="avatar">AI</div>
            <div class="bubble">A carregar e indexar o ficheiro '${file.name}'... Aguarde.</div>
        </div>
    `;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });
        const resultado = await response.json();

        chatBox.innerHTML += `
            <div class="message ai-message">
                <div class="avatar">AI</div>
                <div class="bubble">${resultado.mensagem || resultado.erro}</div>
            </div>
        `;
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (e) {
        console.error("Erro no upload:", e);
    }
}

function verificarEnter(event) {
    if (event.key === "Enter") {
        enviarMensagem();
    }
}

async function resetarConversa() {
    await fetch("/resetar_historico", { method: "POST" });
    document.getElementById("chat-box").innerHTML = `
        <div class="message ai-message">
            <div class="avatar">AI</div>
            <div class="bubble">
                <span>Fluxo neural limpo. Como posso ajudar agora?</span>
                <button class="btn-voz" onclick="lerVoz(this, 'Fluxo neural limpo. Como posso ajudar agora?')">🔊 Ouvir</button>
            </div>
        </div>
    `;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}