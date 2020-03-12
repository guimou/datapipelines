import http.server
import io
import json
import logging
import os
import random
import socketserver
import sys
from hashlib import blake2b
from io import BytesIO

import boto3
import numpy as np
import tensorflow as tf
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from cloudevents.sdk import marshaller
from cloudevents.sdk.event import v02

access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

s3client = boto3.client('s3','us-east-1', endpoint_url=service_point,
                       aws_access_key_id = access_key,
                       aws_secret_access_key = secret_key,
                        use_ssl = True if 'https' in service_point else False)

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
    bucket_eventName=msg['eventName']
    bucket_name=msg['s3']['bucket']['name']
    bucket_object=msg['s3']['object']['key']
    data = {'bucket_eventName':bucket_eventName, 'bucket_name':bucket_name, 'bucket_object':bucket_object}
    return data

def load_image(bucket_name, img_path):
    logging.info('load_image')
    obj = s3client.get_object(Bucket=bucket_name, Key=img_path)
    img = tf.keras.preprocessing.image.load_img(BytesIO(obj['Body'].read()), target_size=(150, 150))
    img_tensor = tf.keras.preprocessing.image.img_to_array(img)                    # (height, width, channels)
    img_tensor = np.expand_dims(img_tensor, axis=0)         # (1, height, width, channels), add a dimension because the model expects this shape: (batch_size, height, width, channels)
    img_tensor /= 255.                                      # imshow expects values in the range [0, 1]

    return img_tensor

def prediction(new_image):
    logging.info('prediction')
    try:
        model = tf.keras.models.load_model('./pneumonia_model.h5')
        logging.info('model loaded')
        pred = model.predict(new_image)
        logging.info('prediction made')
    
        if pred[0][0] > 0.80:
            label='Pneumonia, risk=' + str(round(pred[0][0]*100,2)) + '%'
        elif pred[0][0] < 0.60:
            label='Normal, risk=' + str(round(pred[0][0]*100,2)) + '%'
        else:
            label='Unsure, risk=' + str(round(pred[0][0]*100,2)) + '%'
    except Exception as e:
        logging.error(f"Prediction error: {e}")
        raise   
    logging.info('label')
    prediction = {'label':label,'pred':pred[0][0]}
    return prediction

def anonymize(img,img_name):
    # Use GaussianBlur to blur the PII 5 times.
    logging.info('blurring')
    box = (0, img.size[1]-100, 300, img.size[1])
    crop_img = img.crop(box)
    blur_img = crop_img.filter(ImageFilter.GaussianBlur(radius=5))
    img.paste(blur_img, box)

    # Anonymize filename  
    logging.info('anonymizing filename') 
    prefix = img_name.split('_')[0]
    patient_id = img_name.split('_')[2]
    suffix = img_name.split('_')[-1]
    new_img_name = prefix + '_' + 'XXXXXXXX_' + get_study_id(patient_id) + '_XXXX-XX-XX_' + suffix

    anon_data = {'img_anon': img, 'anon_img_name': new_img_name}

    return anon_data


def get_study_id(patient_id):
    # Given a patient id, returns a study id.
    # In a real implementation this should be replaced by some database lookup.
    # Here we generate a hash based on patient id
    h = blake2b(digest_size=4)
    h.update((int(patient_id)).to_bytes(2, byteorder='big'))
    return h.hexdigest()

def get_safe_ext(key):
    ext = os.path.splitext(key)[-1].strip('.').upper()
    if ext in ['JPG', 'JPEG']:
        return 'JPEG' 
    elif ext in ['PNG']:
        return 'PNG' 
    else:
        logging.error('Extension is invalid')   

def run_event(event):
    logging.info(event.Data())
    try:
        extracted_data = extract_data(event.Data())
        bucket_eventName = extracted_data['bucket_eventName']
        bucket_name = extracted_data['bucket_name']
        img_key = extracted_data['bucket_object']
        logging.info(bucket_eventName + ' ' + bucket_name + ' ' + img_key)

        if bucket_eventName == 's3:ObjectCreated:Put':
            # Load image and make prediction
            new_image = load_image(bucket_name,img_key)
            result = prediction(new_image)
            logging.info('result=' + result['label'])

            # Get original image and print prediction on it
            image_object = s3client.get_object(Bucket=bucket_name,Key=img_key)
            img = Image.open(BytesIO(image_object['Body'].read()))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype('FreeMono.ttf', 50)
            draw.text((0, 0), result['label'], (255), font=font)

            # Save image with "-processed" appended to name
            computed_image_key = os.path.splitext(img_key)[0] + '-processed.' + os.path.splitext(img_key)[-1].strip('.')
            buffer = BytesIO()
            img.save(buffer, get_safe_ext(computed_image_key))
            buffer.seek(0)
            sent_data = s3client.put_object(Bucket=bucket_name+'-processed', Key=computed_image_key, Body=buffer)
            if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise logging.error('Failed to upload image {} to bucket {}'.format(computed_image_key, bucket_name + '-processed'))

            logging.info('Image processed')

            if result['pred'] > 0.80:
                img_name = img_key.split('/')[-1]
                anonymized_data = anonymize(img,img_name)
                split_key = img_key.rsplit('/', 1)
                if len(split_key) == 1:
                    anonymized_image_key = anonymized_data['anon_img_name']
                else:
                    anonymized_image_key = split_key[0] + '/' + anonymized_data['anon_img_name']
                anonymized_img = anonymized_data['img_anon']
                buffer = BytesIO()
                anonymized_img.save(buffer, get_safe_ext(anonymized_image_key))
                buffer.seek(0)
                sent_data = s3client.put_object(Bucket=bucket_name+'-anonymized', Key=anonymized_image_key, Body=buffer)
                if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
                    raise logging.error('Failed to upload image {} to bucket {}'.format(anonymized_image_key, bucket_name + '-anonymized'))

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


client = CloudeventsServer()
client.start_receiver(run_event)
