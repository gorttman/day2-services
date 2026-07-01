FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 pamtester libpam-modules \
    && rm -rf /var/lib/apt/lists/*

COPY auth_server.py /app/auth_server.py

EXPOSE 8081

CMD ["python3", "/app/auth_server.py"]
