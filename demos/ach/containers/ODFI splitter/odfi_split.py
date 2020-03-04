import http.server
import io
import json
import logging
import os
import random
import socketserver
import sys
from io import BytesIO

import boto3
from cloudevents.sdk import marshaller
from cloudevents.sdk.event import v02

access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

s3client = boto3.client('s3', 'us-east-1', endpoint_url=service_point,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        use_ssl=True if 'https' in service_point else False)

m = marshaller.NewDefaultHTTPMarshaller()


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

                if content_type != 'application/json':
                    logging.info('Not JSON')
                    data = io.StringIO(data)

                try:
                    event = v02.Event()
                    event = m.FromRequest(event, headers, data, json.loads)
                except Exception as e:
                    logging.error(f"Event error: {e}")
                    raise

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


def load_file(bucket_name, object_key):
    logging.info('load_file')
    obj = s3client.get_object(Bucket=bucket_name, Key=object_key)
    content = obj['Body'].read().decode('utf-8')
    return content

def save_file(bucket_name, file_name, content):
    sent_data = s3client.put_object(
        Bucket=bucket_name, Key=file_name, Body=content)
    if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise logging.error(
            'Failed to upload file {} to bucket {}'.format(file_name, bucket_name))


def get_odfi_routing(content):
    odfi_routing = content.splitlines()[0][4:12]
    return odfi_routing


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
            odfi_routing = get_odfi_routing(content)
            save_file('ach-odfi-' + odfi_routing,object_key,content)

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


client = CloudeventsServer()
client.start_receiver(run_event)
