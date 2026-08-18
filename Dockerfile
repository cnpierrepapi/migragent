FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY migragent/ ./migragent/
COPY web/brand/ ./web/brand/

# Cloud Run sets PORT. The service listens on it rather than on a fixed number.
ENV PORT=8080
EXPOSE 8080

# The ambient identity is stated rather than detected. Asking the credential who
# it is reports "default" until it has been refreshed over the network, so a self
# check silently fails and the service tries to impersonate itself, which hangs
# instead of erroring. That cost a deploy cycle on the previous build.
ENV MIGRAGENT_AMBIENT_PRINCIPAL=migragent-web

CMD exec gunicorn --bind :$PORT --workers 2 --threads 8 --timeout 120 migragent.app:app
