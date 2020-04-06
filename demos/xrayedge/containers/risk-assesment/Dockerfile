FROM python:3.6

RUN pip install --upgrade pip

WORKDIR /usr/src/app

COPY requirements.txt risk-assesment.py FreeMono.ttf ./

RUN pip install -r requirements.txt

CMD ["python", "-u", "risk-assesment.py"]
