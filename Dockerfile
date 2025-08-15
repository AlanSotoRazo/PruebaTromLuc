FROM python:3.9-slim

# Instalar dependencias del sistema necesarias para dlib, face-recognition, opencv, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk2.0-dev \
    libboost-all-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    zlib1g-dev \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear un entorno virtual y activarlo
RUN python -m venv /opt/venv

# Activar el entorno virtual e instalar dependencias
COPY requirements.txt /app/
RUN /opt/venv/bin/pip install --upgrade pip setuptools && /opt/venv/bin/pip install -r /app/requirements.txt

# Copiar el código fuente
COPY . /app/
WORKDIR /app

# Usar el entorno virtual como PATH principal
ENV PATH="/opt/venv/bin:$PATH"

# Comando para iniciar la aplicación
CMD ["python", "app.py"]
