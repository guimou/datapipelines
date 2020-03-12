FROM python:3.6

WORKDIR /usr/src/app

COPY requirements.txt xray.py pneumonia_model.h5 FreeMono.ttf ./

RUN pip install -r requirements.txt

CMD ["python", "-u", "xray.py"]
