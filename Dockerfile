FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Instala dependências antes de copiar todo o código para aproveitar cache
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Agora copia o restante do repositório (handlers, config, scripts etc.)
COPY . .

# Garante que a pasta de dados exista para montagem via volume
RUN mkdir -p data && \
    chmod +x docker-entrypoint.sh && \
    addgroup --system app && \
    adduser --system --ingroup app app && \
    chown -R app:app /app

USER app

EXPOSE 8081
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["ghl-webhooks"]
