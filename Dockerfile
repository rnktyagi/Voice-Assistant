FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 7860

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]