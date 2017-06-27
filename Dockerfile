FROM python:2.7
ENV PYTHONUNBUFFERED 1

COPY . /app
RUN pip install -r /app/requirements.txt
ENTRYPOINT ["python","/app/main.py"]