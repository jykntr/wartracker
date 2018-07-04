FROM python:3.6-alpine

RUN apk --no-cache add tzdata git

COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt && pip install --editable .

CMD ["wartracker"]
