FROM python:3.6

WORKDIR /usr/src/app

COPY requirements.txt risk-assesment.py pneumonia_model.h5 FreeMono.ttf ./

RUN pip install -r requirements.txt

CMD ["python", "-u", "risk-assesment.py"]
