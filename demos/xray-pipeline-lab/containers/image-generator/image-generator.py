import logging
import os
import random
import sys
from time import sleep

import boto3
import mysql.connector

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

##############
## Vars init #
##############
# Object storage
access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']
s3client = boto3.client('s3', 'us-east-1', endpoint_url=service_point,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        use_ssl=True if 'https' in service_point else False)

# Buckets
bucket_source = os.environ['bucket-source']
bucket_destination = os.environ['bucket-base-name']

# Helper database
db_user = os.environ['database-user']
db_password = os.environ['database-password']
db_host = os.environ['database-host']
db_db = os.environ['database-db']

# Delay between images
seconds_wait = float(os.environ['seconds_wait'])

########
# Code #
########
def copy_file(source, image_key, destination, image_name):
    """Copies an object from a source bucket to a destination bucket.""" 

    copy_source = {
        'Bucket': source,
        'Key': image_key
    }
    s3client.copy(copy_source, destination, image_name)

def update_images_uploaded(image_name):
    """Inserts image name and timestamp into the helper database."""

    try:
        cnx = mysql.connector.connect(user=db_user, password=db_password,
                                      host=db_host,
                                      database=db_db)
        cursor = cnx.cursor()
        query = 'INSERT INTO images_uploaded(time,name) SELECT CURRENT_TIMESTAMP(),"' + image_name + '";'
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

# Populate source images lists
pneumonia_images=[]
for image in s3client.list_objects(Bucket=bucket_source,Prefix='demo_base/PNEUMONIA/')['Contents']:
    pneumonia_images.append(image['Key'])
normal_images=[]
for image in s3client.list_objects(Bucket=bucket_source,Prefix='demo_base/NORMAL/')['Contents']:
    normal_images.append(image['Key'])

# Main loop
while seconds_wait != 0: #This allows the container to keep running but not send any image if parameter is set to 0
    logging.info("copy image")
    rand_type = random.randint(1,10)
    if rand_type <= 8: # 80% of time, choose a normal image
        image_key = normal_images[random.randint(0,len(normal_images)-1)]
    else:
        image_key = pneumonia_images[random.randint(0,len(pneumonia_images)-1)]
    image_name = image_key.split('/')[-1]
    copy_file(bucket_source,image_key,bucket_destination,image_name)
    update_images_uploaded(image_name)
    sleep(seconds_wait)

# Dirty hack to keep container running even when no images are to be copied
os.system("tail -f /dev/null")
