FROM python:3.12-slim

# torch / sentence-transformers / scikit-learn need a C build toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now the app code
COPY . .

EXPOSE 8000

# main.py's __main__ block is an interactive CLI (input()), which will hang
# in a container. Run the actual FastAPI app with uvicorn instead.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
