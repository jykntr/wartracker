FROM python:3.6-alpine

RUN apk --no-cache add tzdata

COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt

CMD ["python", "wartracker.py"]
