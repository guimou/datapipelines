import io
import logging
import os
import sys
from io import BytesIO
import pandas as pd
import gzip

import boto3
import numpy as np
from cloudevents.http import from_http
from flask import Flask, request

from flask_cors import CORS

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

##############
## Vars init #
##############
# Object storage
access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']
s3client = boto3.client('s3','us-east-1', endpoint_url=service_point,
                       aws_access_key_id = access_key,
                       aws_secret_access_key = secret_key,
                        use_ssl = True if 'https' in service_point else False)

########
# Code #
########
# Main Flask app
app = Flask(__name__)
CORS(app)

@app.route("/", methods=["POST"])
def home():
    # Retrieve the CloudEvent
    event = from_http(request.headers, request.get_data())
    
    # Process the event
    process_event(event.data)

    return "", 204

def process_event(data):
    """Main function to process data received by the container image."""

    logging.info(data)
    try:
        # Retrieve event info
        extracted_data = extract_data(data)
        bucket_eventName = extracted_data['bucket_eventName']
        bucket_name = extracted_data['bucket_name']
        object_key = extracted_data['bucket_object']
        object_name = object_key.split('/')[-1]
        logging.info(bucket_eventName + ' ' + bucket_name + ' ' + object_key)

        if 's3:ObjectCreated' in bucket_eventName:
            # Load object and analyze
            analyze_object(bucket_name,object_key)

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

def extract_data(data):
    logging.info('extract_data')
    record=data['Records'][0]
    bucket_eventName=record['eventName']
    bucket_name=record['s3']['bucket']['name']
    bucket_object=record['s3']['object']['key']
    data_out = {'bucket_eventName':bucket_eventName, 'bucket_name':bucket_name, 'bucket_object':bucket_object}
    return data_out

def s3_to_pandas(client, bucket, key, header=None):

    # get key using boto3 client
    obj = client.get_object(Bucket=bucket, Key=key)
    gz = gzip.GzipFile(fileobj=obj['Body'])
    
    # load stream directly to DF
    return pd.read_csv(gz, header=header, dtype=str)
    
def ADDmetadata(bucketname,objectname,metadata_name,metadata_value):
    s3_object = s3client.get_object(Bucket=bucketname, Key=objectname)
    k = s3client.head_object(Bucket = bucketname, Key = objectname)
    m = k['Metadata']
    m[metadata_name] = metadata_value
    s3client.copy_object(Bucket = bucketname, Key = objectname,CopySource = {'Bucket': bucketname , 'Key': objectname}, Metadata = m, MetadataDirective='REPLACE')

def analyze_object(bucket_name,object_key):
    df = s3_to_pandas(s3client, bucket_name,object_key)
    df_describe = df.describe().to_json()
    ADDmetadata(bucket_name,object_key,'dfdescribe',df_describe)


# Launch Flask server
if __name__ == '__main__':
    app.run(host='0.0.0.0')
