FROM alpine:3.20.3
ADD requirements.txt /
RUN apk add --no-cache python3 py3-pip && \
    python3 -m venv /app && \
    /app/bin/pip install -r requirements.txt
ADD truenascsp/*.py /app/
WORKDIR /app
ENTRYPOINT [ "/app/bin/gunicorn", "--workers", "3", "--bind", "0.0.0.0:8080", "--timeout", "180", "--preload", "csp:SERVE" ]
