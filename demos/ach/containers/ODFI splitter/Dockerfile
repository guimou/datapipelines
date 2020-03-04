FROM python:3.7

WORKDIR /usr/src/app

COPY requirements.txt odfi_split.py ./

RUN pip install -r requirements.txt

CMD ["python", "-u", "odfi_split.py"]
