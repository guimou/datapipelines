import logging
import os
import random
import sys
from time import sleep

import boto3

import mysql.connector

access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']

db_user = os.environ['database-user']
db_password = os.environ['database-password']
db_host = os.environ['database-host']
db_db = os.environ['database-db']

seconds_wait = os.environ['seconds_wait']

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

s3client = boto3.client('s3', 'us-east-1', endpoint_url=service_point,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        use_ssl=True if 'https' in service_point else False)

def copy_file(source, image_key, destination, image_name):
    copy_source = {
        'Bucket': source,
        'Key': image_key
    }
    s3client.copy(copy_source, destination, image_name)

def update_images_uploaded(image_name):
    try:
        cnx = mysql.connector.connect(user='xrayedgeuser', password='xrayedgepassword',
                                      host='achdb.ach-db',
                                      database='achdb')
        cursor = cnx.cursor()
        query = 'INSERT INTO merchant_upload(time,name,entry) SELECT CURRENT_TIMESTAMP(),' + image_name + ', 1;'
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

# Inits
bucket_source = 'chest-xray'
bucket_destination = 'xrayedge-in'

# Read source images lists
pneumonia_images=[]
for image in s3client.list_objects(Bucket=bucket_source,Prefix='demo_base/PNEUMONIA/')['Contents']:
    pneumonia_images.append(image['Key'])
normal_images=[]
for image in s3client.list_objects(Bucket=bucket_source,Prefix='demo_base/NORMAL/')['Contents']:
    normal_images.append(image['Key'])

# Main loop
while seconds_wait != 0:
    rand_type = random.randint(1,10)
    if rand_type <= 8: # 80% of time, choose a normal image
        image_key = normal_images[random.randint(0,len(normal_images)-1)]
    else:
        image_key = pneumonia_images[random.randint(0,len(pneumonia_images)-1)]
    image_name = image_key.split('/')[-1]
    copy_file(bucket_source,image_key,bucket_destination,image_name)
    update_images_uploaded(image_name)
    sleep(seconds_wait)
