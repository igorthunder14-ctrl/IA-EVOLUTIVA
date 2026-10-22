import json
import os
import traceback
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, render_template, request, session
from pypdf import PdfReader
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "troque-esta-chave-local")

BASE_DIR = Path(__file__).resolve().parent
PASTA_DADOS = BASE_DIR / "dados"
PASTA_HISTORICOS = BASE_DIR / "historicos"
EXTENSOES_PERMITIDAS = {"txt", "pdf"}

# Ollama roda localmente no computador. Nenhuma chave de API é necessária.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODELO_LOCAL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

PASTA_DADOS.mkdir(parents=True, exist_ok=True)
PASTA_HISTORICOS.mkdir(parents=True, exist_ok=True)

SYSTEM_INSTRUCTION = """
Você é o NEXUS, um assistente de inteligência artificial especializado
em biomedicina e ciências da saúde.
- Responda em português brasileiro, com clareza e precisão.
- Seja objetivo, mas desenvolva o assunto quando necessário.
- Use tópicos quando isso facilitar a compreensão.
- Responda a perguntas gerais mesmo sem documentos locais.
- Use TXT e PDF fornecidos como material complementar.
- Não afirme ter lido documentos que não foram fornecidos.
- Considere o histórico em perguntas de acompanhamento.
- Diferencie fatos científicos de hipóteses e incertezas.
- Em temas de saúde, ofereça informações educativas e recomende um profissional
  quando a situação exigir avaliação individual. Não invente referências.
"""

INTERACOES = {
    "saudacao": {
        "palavras": {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "e aí", "hey"},
        "resposta": "Olá! Sou o NEXUS // AI CORE. Como posso ajudar você hoje?",
    },
    "agradecimento": {
        "palavras": {"obrigado", "obrigada", "valeu", "vlw", "obrigadão", "grato", "thanks"},
        "resposta": "De nada! Estou à disposição para ajudar.",
    },
    "despedida": {
        "palavras": {"tchau", "até mais", "ate mais", "falou", "adeus"},
        "resposta": "Até logo! Obrigado por conversar com o NEXUS.",
    },
}


def obter_caminho_historico():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    return PASTA_HISTORICOS / f"historico_{session['user_id']}.json"


def carregar_historico():
    caminho = obter_caminho_historico()
    if caminho.exists():
        try:
            with caminho.open("r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            if isinstance(dados, list):
                return dados
        except (OSError, json.JSONDecodeError) as erro:
            print("Erro ao carregar histórico:", repr(erro))
    return []


def salvar_no_historico(pergunta, resposta):
    historico = carregar_historico()
    historico.append({"pergunta": pergunta, "resposta": resposta})
    caminho = obter_caminho_historico()
    try:
        with caminho.open("w", encoding="utf-8") as arquivo:
            json.dump(historico[-15:], arquivo, ensure_ascii=False, indent=2)
    except OSError as erro:
        print("Erro ao salvar histórico:", repr(erro))


def permitido_arquivo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


def carregar_todos_os_documentos():
    conteudos = []
    for caminho in PASTA_DADOS.iterdir():
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() == ".txt":
            try:
                texto = caminho.read_text(encoding="utf-8", errors="replace").strip()
                if texto:
                    conteudos.append(f"DOCUMENTO TXT: {caminho.name}\n{texto}")
            except OSError as erro:
                print(f"Erro ao ler TXT {caminho.name}:", repr(erro))
        elif caminho.suffix.lower() == ".pdf":
            try:
                leitor = PdfReader(str(caminho))
                paginas = [pagina.extract_text() or "" for pagina in leitor.pages]
                texto_pdf = "\n".join(paginas).strip()
                if texto_pdf:
                    conteudos.append(f"DOCUMENTO PDF: {caminho.name}\n{texto_pdf}")
            except Exception as erro:
                print(f"Erro ao ler PDF {caminho.name}:", repr(erro))
    return "\n\n".join(conteudos)[:40000]


def consultar_ollama(mensagens):
    payload = json.dumps({
        "model": MODELO_LOCAL,
        "messages": mensagens,
        "stream": False,
        "options": {"temperature": 0.4},
    }).encode("utf-8")

    req = Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=300) as resposta_http:
            dados = json.loads(resposta_http.read().decode("utf-8"))
    except HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace")
        print("Erro HTTP do Ollama:", erro.code, detalhe)
        if erro.code == 404:
            raise RuntimeError(
                f"Ollama não encontrou o modelo '{MODELO_LOCAL}'. "
                f"Execute: ollama pull {MODELO_LOCAL}"
            ) from erro
        raise RuntimeError(f"Ollama respondeu com HTTP {erro.code}: {detalhe}") from erro
    except URLError as erro:
        raise RuntimeError(
            "Não foi possível conectar ao Ollama. Abra o Ollama e confirme "
            "que ele está rodando em http://localhost:11434."
        ) from erro

    texto = (dados.get("message") or {}).get("content", "").strip()
    if not texto:
        raise RuntimeError("O Ollama respondeu, mas não retornou texto.")
    return texto


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status_ia", methods=["GET"])
def status_ia():
    """Endpoint simples para verificar se o servidor Ollama está acessível."""
    try:
        req = Request(OLLAMA_URL.rsplit("/api/", 1)[0] + "/api/tags")
        with urlopen(req, timeout=5) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        modelos = [m.get("name", "") for m in dados.get("models", [])]
        instalado = any(nome == MODELO_LOCAL or nome.startswith(MODELO_LOCAL + "-") for nome in modelos)
        return jsonify({
            "ollama_conectado": True,
            "modelo_configurado": MODELO_LOCAL,
            "modelo_instalado": instalado,
            "modelos_instalados": modelos,
        })
    except Exception as erro:
        return jsonify({
            "ollama_conectado": False,
            "modelo_configurado": MODELO_LOCAL,
            "erro": str(erro),
        }), 503


@app.route("/upload", methods=["POST"])
def upload_arquivo():
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo foi enviado."}), 400
    arquivo = request.files["arquivo"]
    if not arquivo.filename:
        return jsonify({"erro": "Nome de arquivo inválido."}), 400
    if not permitido_arquivo(arquivo.filename):
        return jsonify({"erro": "Formato não permitido. Envie um TXT ou PDF."}), 400
    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro:
        return jsonify({"erro": "Não foi possível utilizar esse nome de arquivo."}), 400
    try:
        arquivo.save(str(PASTA_DADOS / nome_seguro))
        return jsonify({
            "mensagem": f"Arquivo '{nome_seguro}' recebido com sucesso. Seu conteúdo estará disponível para as próximas perguntas."
        })
    except OSError as erro:
        print("Erro no upload:", repr(erro))
        return jsonify({"erro": "Não foi possível salvar o arquivo."}), 500


@app.route("/perguntar", methods=["POST"])
def perguntar():
    dados = request.get_json(silent=True) or {}
    pergunta_usuario = str(dados.get("pergunta", "")).strip()
    pergunta_lower = pergunta_usuario.lower().strip("!?.,")

    if not pergunta_usuario:
        return jsonify({"resposta": "Por favor, digite uma pergunta."}), 400

    comandos_reset = {
        "reiniciar conversa", "nova conversa", "resetar chat",
        "limpar historico", "limpar histórico"
    }
    if pergunta_lower in comandos_reset:
        caminho = obter_caminho_historico()
        try:
            if caminho.exists():
                caminho.unlink()
        except OSError as erro:
            print("Erro ao limpar histórico:", repr(erro))
            return jsonify({"resposta": "Não foi possível limpar o histórico."}), 500
        return jsonify({"resposta": "Conversa reiniciada! Como posso ajudar você agora?"})

    for info in INTERACOES.values():
        if pergunta_lower in info["palavras"]:
            resposta = info["resposta"]
            salvar_no_historico(pergunta_usuario, resposta)
            return jsonify({"resposta": resposta})

    try:
        base_conhecimento = carregar_todos_os_documentos()
        historico_salvo = carregar_historico()
        mensagens = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

        contexto = f"""
BASE DE CONHECIMENTO LOCAL:
{base_conhecimento if base_conhecimento else "Nenhum documento local foi carregado."}

Instruções sobre documentos: use o conteúdo acima como material complementar.
Se não houver informação relevante nos documentos, responda normalmente com seus conhecimentos.
Não diga que consultou um documento se não houver conteúdo disponível.
"""
        mensagens.append({"role": "system", "content": contexto})

        # Mantém os últimos turnos como contexto para perguntas de acompanhamento.
        for turno in historico_salvo[-8:]:
            pergunta_anterior = str(turno.get("pergunta", "")).strip()
            resposta_anterior = str(turno.get("resposta", "")).strip()
            if pergunta_anterior and resposta_anterior:
                mensagens.append({"role": "user", "content": pergunta_anterior})
                mensagens.append({"role": "assistant", "content": resposta_anterior})

        mensagens.append({"role": "user", "content": pergunta_usuario})
        resposta_ia = consultar_ollama(mensagens)
        salvar_no_historico(pergunta_usuario, resposta_ia)
        return jsonify({"resposta": resposta_ia})

    except Exception as erro:
        traceback.print_exc()
        mensagem_erro = str(erro)
        if "Não foi possível conectar ao Ollama" in mensagem_erro:
            resposta_erro = (
                "Não consegui conectar à IA local. Abra o aplicativo Ollama e tente novamente. "
                "Se ele já estiver aberto, confira se está rodando em http://localhost:11434."
            )
        elif "não encontrou o modelo" in mensagem_erro:
            resposta_erro = mensagem_erro
        else:
            resposta_erro = (
                "Não foi possível gerar uma resposta pela IA local. "
                f"Detalhe: {mensagem_erro}"
            )
        return jsonify({"resposta": resposta_erro}), 500


@app.route("/resetar_historico", methods=["POST"])
def resetar():
    caminho = obter_caminho_historico()
    try:
        if caminho.exists():
            caminho.unlink()
    except OSError as erro:
        print("Erro ao resetar histórico:", repr(erro))
        return jsonify({"status": "Não foi possível limpar o histórico."}), 500
    return jsonify({"status": "Histórico limpo com sucesso."})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
