# Közös image a webhez és a workerhez.
FROM python:3.12-slim

# Ne írjon .pyc-t, ne pufferelje a kimenetet (így látszik a log azonnal)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Rendszerszintű csomagok: psycopg fordításához, képek kezeléséhez (Pillow), healthcheckhez
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev libjpeg-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Először csak a függőséglista másolódik, hogy a Docker cache-e ne vesszen el minden kódmódosításnál
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

# A kódot fejlesztésben a compose csatolja be (volume), élesben ez a másolat számít
COPY . .

EXPOSE 8000

# Fejlesztői alapértelmezés; élesben a compose.prod.yml felülírja gunicornra

CMD ["sh", "-c", "cd /app/web && python manage.py collectstatic --noinput && Python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000}"]
