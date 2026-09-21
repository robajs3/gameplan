FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p static/uploads

EXPOSE 5005

CMD ["gunicorn", "-b", "0.0.0.0:5005", "-w", "2", "--timeout", "60", "app:app"]
