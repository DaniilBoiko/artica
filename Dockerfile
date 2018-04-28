FROM python:3.6-alpine

RUN adduser -D artica

WORKDIR /home/artica

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn

COPY app app
COPY artica artica
COPY artica.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP artica.py

RUN chown -R artica:artica ./
USER artica

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
