import json
import os
import uuid
from flask import Flask, jsonify, render_template, request, session
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = "chave_secreta_assistente_futurista_2026"

PASTA_DADOS = "dados"
PASTA_HISTORICOS = "historicos"
EXTENSOES_PERMITIDAS = {"txt", "pdf"}

os.makedirs(PASTA_DADOS, exist_ok=True)
os.makedirs(PASTA_HISTORICOS, exist_ok=True)

# Insira a sua chave real de API do Google AI Studio entre as aspas abaixo:
client = genai.Client(api_key="AQ.Ab8RN6JdqiFySAx75YR89XFMAkE3eJg4D_tjRZlKjHwk_IeK8A")

INTERACOES = {
    "saudacao": {
        "palavras": ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "hey"],
        "resposta": "Olá! Sistema online e conectado à base neural. Como posso ajudar com suas estratégias hoje?"
    },
    "agradecimento": {
        "palavras": ["obrigado", "obrigada", "valeu", "vlw", "obrigadão", "grato", "thanks"],
        "resposta": "De nada! Estou sempre à disposição."
    },
    "despedida": {
        "palavras": ["tchau", "até mais", "ate mais", "falou", "adeus"],
        "resposta": "Até logo! Fechando canal neural seguro."
    }
}

def permitido_arquivo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS

def obter_caminho_historico():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    return os.path.join(PASTA_HISTORICOS, f"historico_{session['user_id']}.json")

def carregar_historico():
    caminho = obter_caminho_historico()
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_no_historico(pergunta, resposta):
    historico = carregar_historico()
    historico.append({"pergunta": pergunta, "resposta": resposta})
    if len(historico) > 15:
        historico = historico[-15:]
    caminho = obter_caminho_historico()
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=4)

def carregar_todos_os_documentos():
    conteudo_unificado = []
    if not os.path.exists(PASTA_DADOS):
        return ""
        
    for nome_arquivo in os.listdir(PASTA_DADOS):
        caminho_completo = os.path.join(PASTA_DADOS, nome_arquivo)
        if nome_arquivo.endswith(".txt"):
            try:
                with open(caminho_completo, "r", encoding="utf-8") as f:
                    texto = f.read().strip()
                    if texto:
                        conteudo_unificado.append(f"--- DOCUMENTO (TXT): {nome_arquivo} ---\n{texto}")
            except Exception as e:
                print(f"Erro ao ler TXT {nome_arquivo}: {e}")
        elif nome_arquivo.endswith(".pdf"):
            try:
                leitor = PdfReader(caminho_completo)
                texto_pdf = ""
                for pagina in leitor.pages:
                    t = pagina.extract_text()
                    if t:
                        texto_pdf += t + "\n"
                if texto_pdf.strip():
                    conteudo_unificado.append(f"--- DOCUMENTO (PDF): {nome_arquivo} ---\n{texto_pdf}")
            except Exception as e:
                print(f"Erro ao ler PDF {nome_arquivo}: {e}")
    return "\n\n".join(conteudo_unificado)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_arquivo():
    if 'arquivo' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        return jsonify({"erro": "Nome de arquivo inválido"}), 400
    if arquivo and permitido_arquivo(arquivo.filename):
        nome_seguro = secure_filename(arquivo.filename)
        caminho = os.path.join(PASTA_DADOS, nome_seguro)
        arquivo.save(caminho)
        return jsonify({"mensagem": f"Arquivo '{nome_seguro}' carregado e indexado com sucesso!"})
    return jsonify({"erro": "Formato não permitido. Apenas TXT ou PDF."}), 400

@app.route("/perguntar", methods=["POST"])
def perguntar():
    dados = request.get_json()
    pergunta_usuario = dados.get("pergunta", "").strip()
    pergunta_lower = pergunta_usuario.lower().strip("!?.,")

    if not pergunta_usuario:
        return jsonify({"resposta": "Por favor, digite um comando ou pergunta válida."}), 400

    PALAVRAS_CHAVE_RESET = ["reiniciar conversa", "nova conversa", "resetar chat", "limpar historico"]
    if any(p in pergunta_lower for p in PALAVRAS_CHAVE_RESET):
        caminho = obter_caminho_historico()
        if os.path.exists(caminho):
            os.remove(caminho)
        return jsonify({"resposta": "Fluxo neural reiniciado. Histórico limpo. Como posso ajudar agora?"})

    for categoria, info in INTERACOES.items():
        if any(p == pergunta_lower or p in pergunta_lower for p in info["palavras"]):
            salvar_no_historico(pergunta_usuario, info["resposta"])
            return jsonify({"resposta": info["resposta"]})

    base_conhecimento = carregar_todos_os_documentos()
    historico_salvo = carregar_historico()

    system_instruction = "Você é um assistente especialista em biomedicina. Seja direto, conciso, objetivo e responda em tópicos curtos."

    contexto_conversacional = []
    for turno in historico_salvo:
        contexto_conversacional.append(f"Usuário: {turno['pergunta']}")
        contexto_conversacional.append(f"Assistente: {turno['resposta']}")

    historico_texto = "\n".join(contexto_conversacional) if contexto_conversacional else "Nenhum histórico anterior."

    prompt_final = f"""
    Base de Conhecimento Local:
    {base_conhecimento if base_conhecimento else "Nenhum documento carregado."}

    Histórico Recente:
    {historico_texto}

    Pergunta Atual: {pergunta_usuario}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",  # Atualizado conforme exigido pela mensagem de erro da API
            contents=prompt_final,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=1000
            )
        )
        resposta_ia = response.text
        salvar_no_historico(pergunta_usuario, resposta_ia)
        return jsonify({"resposta": resposta_ia})
    except Exception as e:
        erro_str = str(e)
        if "API key not valid" in erro_str or "API_KEY_INVALID" in erro_str:
            msg_amigavel = "❌ Chave de API inválida ou em falta. Certifique-se de colocar a sua chave correta do Google AI Studio no código."
        elif "503" in erro_str or "Unavailable" in erro_str:
            msg_amigavel = "⚠️ Servidores da Google temporariamente sobrecarregados. Aguarde alguns segundos e tente novamente."
        else:
            msg_amigavel = f"Erro interno no processamento neural: {erro_str}"
        return jsonify({"resposta": msg_amigavel}), 500

@app.route("/resetar_historico", methods=["POST"])
def resetar():
    caminho = obter_caminho_historico()
    if os.path.exists(caminho):
        os.remove(caminho)
    return jsonify({"status": "Histórico limpo com sucesso."})

if __name__ == "__main__":
    app.run(debug=True, port=5000)