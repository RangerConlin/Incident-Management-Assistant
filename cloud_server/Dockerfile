FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8765

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8765"]
