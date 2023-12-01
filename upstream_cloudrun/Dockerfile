FROM tiangolo/uwsgi-nginx-flask:python3.8

RUN apt update
RUN yes | apt install vim

WORKDIR /app
COPY . ./


ENV STATIC_URL /app/static
ENV STATIC_PATH /var/www/app/static

RUN pip install -r /app/requirements.txt