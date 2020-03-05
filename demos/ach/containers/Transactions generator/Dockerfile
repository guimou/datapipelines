FROM python:3.7

WORKDIR /usr/src/app

COPY requirements.txt transaction_generator.py  ach ./

RUN pip install -r requirements.txt

CMD ["python", "-u", "transaction_generator.py"]
