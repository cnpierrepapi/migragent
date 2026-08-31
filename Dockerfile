FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY migragent/ ./migragent/
COPY web/brand/ ./web/brand/
COPY docs/DATA_PROTECTION.md ./docs/DATA_PROTECTION.md
COPY docs/ARCHITECTURE.md ./docs/ARCHITECTURE.md

# Cloud Run sets PORT. The service listens on it rather than on a fixed number.
ENV PORT=8080
EXPOSE 8080

# The ambient identity is stated rather than detected. Asking the credential who
# it is reports "default" until it has been refreshed over the network, so a self
# check silently fails and the service tries to impersonate itself, which hangs
# instead of erroring. That cost a deploy cycle on the previous build.
ENV MIGRAGENT_AMBIENT_PRINCIPAL=migragent-web

# The worker timeout matches Cloud Run's request timeout rather than sitting
# under it. At 120 a request that was still working got its worker killed and
# the caller got nothing to read, which looks like a crash and is a deadline.
# The real cap on a slow route is the model budget in migragent/model.py, which
# is a number with a reason attached.
#
# Both numbers went from 300 to 900 on 31 August 2026. A measured UK study run
# with three documents held the event stream open for 225 seconds, and one step
# in it, writing the form, was 88 seconds on its own. That is 75 seconds of
# headroom against a hard ceiling, and what happens past the ceiling is the
# stream being cut with no `done` event: the working screen sits there counting
# while the guide it is waiting for has already been built and saved. Deploy
# sets the matching number on the service, see .github/workflows/deploy.yml.
CMD exec gunicorn --bind :$PORT --workers 2 --threads 8 --timeout 900 migragent.app:app
