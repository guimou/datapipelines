FROM python:3.6

WORKDIR /usr/src/app

COPY requirements.txt explore.py ./

RUN pip install -r requirements.txt

CMD ["python", "-u", "explore.py"]
