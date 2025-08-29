FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# Install Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    ln -s /usr/bin/pip3 /usr/bin/pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI
WORKDIR /app/ComfyUI

# Install PyTorch with CUDA support
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install ComfyUI requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install custom nodes

EXPOSE 8188

CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]