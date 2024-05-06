FROM almalinux

# Install stuff
RUN dnf install -y curl jq && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Manipulate stuff
ENV HERE=/cut/csi-e2e
ENV PATH=${PATH}:${HERE}
RUN mkdir -p ${HERE}
ADD cache ${HERE}
ADD runner.sh ${HERE}
WORKDIR ${HERE}
