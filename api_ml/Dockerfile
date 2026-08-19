# Build context é a raiz do repositório (ver docker-compose.yml:
# build.context: "."), não api_ml/ — por isso os caminhos abaixo
# começam com "api_ml/", mesmo este Dockerfile estando dentro da pasta.
FROM python:3.11-slim

WORKDIR /app

COPY api_ml/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_ml/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
