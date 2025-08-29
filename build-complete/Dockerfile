FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# Install Python and create symlinks
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
WORKDIR /app/ComfyUI/custom_nodes

# Install easy_seed
RUN git clone https://github.com/yolain/ComfyUI-Easy-Use easy_seed
RUN if [ -f easy_seed/requirements.txt ]; then pip install --no-cache-dir -r easy_seed/requirements.txt; fi

# Install ShowText_pysssss
RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts ShowText_pysssss
RUN if [ -f ShowText_pysssss/requirements.txt ]; then pip install --no-cache-dir -r ShowText_pysssss/requirements.txt; fi

# Install MagCache
RUN git clone https://github.com/Zehong-Ma/ComfyUI-MagCache MagCache
RUN if [ -f MagCache/requirements.txt ]; then pip install --no-cache-dir -r MagCache/requirements.txt; fi

WORKDIR /app/ComfyUI

# Install custom nodes

EXPOSE 8188

CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]