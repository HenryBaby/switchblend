FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y gcc python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get remove -y gcc python3-dev && \
    apt-get autoremove -y && \
    apt-get clean

COPY ./app /app

EXPOSE 5000

CMD ["python", "app.py"]
