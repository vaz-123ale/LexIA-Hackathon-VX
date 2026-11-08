# LexIA — imagem para AWS App Runner, ECS/Fargate ou qualquer contêiner.
# Credenciais: use o papel IAM do serviço (nunca copie chaves para a imagem). Variáveis: veja .env.example e infra/aws/README.md.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir anthropic boto3
COPY app ./app
COPY web ./web
COPY data ./data
COPY scripts ./scripts
ENV TORRE_DB=/app/var/torre.db PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "-m", "app.server", "--host", "0.0.0.0", "--port", "8765"]
