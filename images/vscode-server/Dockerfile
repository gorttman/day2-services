FROM codercom/code-server:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget python3 python3-pip python3-venv \
    ansible jq unzip openssh-client iputils-ping dnsutils \
  && rm -rf /var/lib/apt/lists/*

RUN usermod -l gorttman coder \
    && usermod -d /home/gorttman -m gorttman \
    && groupmod -n gorttman coder

USER gorttman
