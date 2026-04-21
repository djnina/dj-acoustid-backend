FROM python:3.11-slim

# install system deps (THIS is where fpcalc comes from)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    chromaprint \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["python", "app.py"]
