from google import genai

client = genai.Client(api_key="AQ.Ab8RN6IrvUyKEcC_UrQf-7QzKSbPGooa784XlQPywA_4bsHHfw")

# Vamos listar os modelos disponíveis para a sua chave
for m in client.models.list():
    if "flash" in m.name:
        print(m.name)