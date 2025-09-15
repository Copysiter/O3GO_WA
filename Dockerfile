FROM python:3.11

WORKDIR /app
EXPOSE 8000

COPY ./packages/ /app/
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt --no-cache-dir

COPY ./app/ /app/
ENV PYTHONPATH=/

ENTRYPOINT ["python", "-m", "main"]