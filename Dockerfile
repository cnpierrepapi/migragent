FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY migragent/ ./migragent/
COPY web/brand/ ./web/brand/
COPY docs/DATA_PROTECTION.md ./docs/DATA_PROTECTION.md

# Cloud Run sets PORT. The service listens on it rather than on a fixed number.
ENV PORT=8080
EXPOSE 8080

# The ambient identity is stated rather than detected. Asking the credential who
# it is reports "default" until it has been refreshed over the network, so a self
# check silently fails and the service tries to impersonate itself, which hangs
# instead of erroring. That cost a deploy cycle on the previous build.
ENV MIGRAGENT_AMBIENT_PRINCIPAL=migragent-web

# The worker timeout matches Cloud Run's request timeout of 300 seconds rather
# than sitting under it. At 120 a request that was still working got its worker
# killed and the caller got nothing to read, which looks like a crash and is a
# deadline. The real cap on a slow route is the model budget in
# migragent/model.py, which is a number with a reason attached.
CMD exec gunicorn --bind :$PORT --workers 2 --threads 8 --timeout 300 migragent.app:app
