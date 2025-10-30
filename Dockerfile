
# Minimal Dockerfile for this app
FROM python:3.11-slim

# System deps for Playwright browsers
RUN apt-get update && apt-get install -y wget gnupg ca-certificates libnss3 libatk-bridge2.0-0 libgtk-3-0 libasound2 \
    libgbm1 libxshmfence1 fonts-liberation libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxrender1 \
    libpango-1.0-0 libx11-6 libnss3 libxss1 libxtst6 libpci3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY app_streamlit.py ./

EXPOSE 8501
CMD ["streamlit", "run", "app_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
