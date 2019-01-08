FROM python:3.6-alpine

RUN apk --no-cache add tzdata git curl

COPY . /app
WORKDIR /app

RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python

RUN pip install -U git+https://github.com/Rapptz/discord.py@rewrite
RUN $HOME/.poetry/bin/poetry build
RUN pip install --no-cache-dir --find-links=/app/dist wartracker

ENV PYTHONPATH /app
CMD ["wartracker"]
