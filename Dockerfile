FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=container
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV TZ=America/Manaus

WORKDIR /app

# Install system dependencies required by Playwright and common libs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates gnupg libnss3 libatk1.0-0 libgtk-3-0 libx11-xcb1 libxcb-dri3-0 \
       libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libxcb1 \
       ffmpeg fonts-liberation libnss3-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright Chromium and OS dependencies for Chrome in container
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# Copy app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
