FROM docker.io/python:3.12.13-alpine3.24
ADD requirements.txt /
RUN python -m venv /app && \
    /app/bin/pip install -r requirements.txt
ADD truenascsp/*.py /app/
WORKDIR /app
ENTRYPOINT [ "/app/bin/gunicorn", "--workers", "3", "--bind", "0.0.0.0:8080", "--timeout", "180", "--preload", "csp:SERVE" ]
