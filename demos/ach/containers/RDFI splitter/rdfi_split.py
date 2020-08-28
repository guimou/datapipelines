import http.server
import io
import json
import logging
import os
import random
import socketserver
import sys
import uuid
from io import BytesIO

import boto3

import mysql.connector
from ach.builder import AchFile
from cloudevents.sdk import marshaller
from cloudevents.sdk.event import v02

access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']

db_user = os.environ['database-user']
db_password = os.environ['database-password']
db_host = os.environ['database-host']
db_db = os.environ['database-db']

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

s3client = boto3.client('s3', 'us-east-1', endpoint_url=service_point,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        use_ssl=True if 'https' in service_point else False)

m = marshaller.NewDefaultHTTPMarshaller()

# banks format = (routing without check_digit, name)
banks = [
    ('06200001', 'BANK OF NEW-YORK'),
    ('06200002', 'BANK OF CHICAGO'),
    ('06200003', 'BANK OF BOSTON'),
    ('06200004', 'BANK OF LOS ANGELES'),
    ('06200005', 'BANK OF ORLANDO'),
    ('06200006', 'BANK OF DENVER'),
    ('06200007', 'BANK OF SEATTLE')
]


class ForkedHTTPServer(socketserver.ForkingMixIn, http.server.HTTPServer):
    """Handle requests with fork."""


class CloudeventsServer(object):
    """Listen for incoming HTTP cloudevents requests.
    cloudevents request is simply a HTTP Post request following a well-defined
    of how to pass the event data.
    """

    def __init__(self, port=8080):
        self.port = port

    def start_receiver(self, func):
        """Start listening to HTTP requests
        :param func: the callback to call upon a cloudevents request
        :type func: cloudevent -> none
        """
        class BaseHttp(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                logging.info('POST received')
                content_type = self.headers.get('Content-Type')
                content_len = int(self.headers.get('Content-Length'))
                headers = dict(self.headers)
                data = self.rfile.read(content_len)
                data = data.decode('utf-8')
                logging.info(content_type)
                logging.info(data)

                #if content_type != 'application/json':
                #    logging.info('Not JSON')
                #    data = io.StringIO(data)

                #try:
                #    event = v02.Event()
                #    event = m.FromRequest(event, headers, data, json.loads)
                #except Exception as e:
                #    logging.error(f"Event error: {e}")
                #    raise
                event = eval(data)['Records'][0]
                logging.info(event)
                func(event)
                self.send_response(204)
                self.end_headers()
                return

        socketserver.TCPServer.allow_reuse_address = True
        with ForkedHTTPServer(("", self.port), BaseHttp) as httpd:
            try:
                logging.info("serving at port {}".format(self.port))
                httpd.serve_forever()
            except:
                httpd.server_close()
                raise


def extract_data(msg):
    logging.info('extract_data')
    bucket_eventName = msg['eventName']
    bucket_name = msg['s3']['bucket']['name']
    object_key = msg['s3']['object']['key']
    data = {'bucket_eventName': bucket_eventName,
            'bucket_name': bucket_name, 'object_key': object_key}
    return data


def load_file(bucket_name, file_key):
    # logging.info('load_file')
    obj = s3client.get_object(Bucket=bucket_name, Key=file_key)
    content = obj['Body'].read().decode('utf-8')
    return content


def save_file(bucket_name, file_name, content):
    sent_data = s3client.put_object(
        Bucket=bucket_name, Key=file_name, Body=content)
    if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise logging.error(
            'Failed to upload file {} to bucket {}'.format(file_name, bucket_name))

def delete_file(bucket_name, object_key):
    logging.info('delete_file')
    s3client.delete_object(Bucket=bucket_name,Key=object_key)


def create_setting_entry(lines):
    immediate_dest = lines[0][4:12]  # ODFI Bank routing number
    immediate_org = lines[0][13:23]  # Company's ACH id
    immediate_dest_name = lines[0][40:63]  # Bank's name
    immediate_org_name = lines[0][63:86]  # Company's name
    # Company's ACH id (again, comes from original generator)
    company_id = lines[0][13:23]

    settings = {
        'immediate_dest': immediate_dest,
        'immediate_org': immediate_org,
        'immediate_dest_name': immediate_dest_name,
        'immediate_org_name': immediate_org_name,
        'company_id': company_id,  # tax number
    }

    return settings

def create_ach_files(content):
    lines = content.splitlines()
    for i in range(0, len(banks)): # For each bank
        ach_file = AchFile('A', create_setting_entry(lines)) # Initiate ACH file
        entries=[]
        for j in range (2,len(lines)): # Read lines
            if lines[j][3:11] == banks[i][0]: # If match for destination (RDFI)
                # Add an entry
                routing_number = lines[j][3:11] # RDFI bank (customer's bank)
                account_number = lines[j][12:29] # Customer account number
                amount = str(float(lines[j][29:39])/100) # Amount
                name = lines[j][54:76] # Customer name
                entries.append({
                    'type'           : '27',  #  We're creatign debits only
                    'routing_number' : routing_number,
                    'account_number' : account_number,
                    'amount'         : amount,
                    'name'           : name
                })
        if len(entries) != 0: #We have transactions
            ach_file.add_batch('POS', entries, credits=True, debits=True)
            # Save generated file to merchant-upload bucket
            bucket_name = 'ach-rdfi-' + banks[i][0] # Based on RDFI rounting number
            file_name = str(uuid.uuid4()) + '.ach' # Generate unique name
            ach_content = ach_file.render_to_string()
            save_file(bucket_name, file_name, ach_content)

def update_rdfi_split():
    try:
        cnx = mysql.connector.connect(user=db_user, password=db_password,
                                      host=db_host,
                                      database=db_db)
        cursor = cnx.cursor()
        query = 'INSERT INTO rdfi_split(time,entry) SELECT CURRENT_TIMESTAMP(), 1;'
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

def run_event(event):
    try:
        extracted_data = extract_data(event.Data())
        bucket_eventName = extracted_data['bucket_eventName']
        bucket_name = extracted_data['bucket_name']
        object_key = extracted_data['object_key']
        logging.info(bucket_eventName + ' ' + bucket_name + ' ' + object_key)

        if bucket_eventName == 's3:ObjectCreated:Put':
            # Load file and treat it
            content = load_file(bucket_name, object_key)
            create_ach_files(content)
            update_rdfi_split()
            delete_file(bucket_name, object_key)
            
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


client = CloudeventsServer()
client.start_receiver(run_event)
