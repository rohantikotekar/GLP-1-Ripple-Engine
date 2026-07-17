FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY loop ./loop
COPY data ./data
COPY backend ./backend
COPY contracts ./contracts
COPY frontend ./frontend

EXPOSE 8000
CMD ["uvicorn", "loop.server:app", "--host", "0.0.0.0", "--port", "8000"]
