import logging
import os
import sys
from string import Template

from flask import Flask

import mysql.connector
from flask_cors import CORS

db_user = os.environ['database-user']
db_password = os.environ['database-password']
db_host = os.environ['database-host']
db_db = os.environ['database-db']
service_point = service_point = os.environ['service_point']

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def get_last_image(bucket_name):
    bucket_table = {'xrayedge-in':'images_uploaded','xrayedge-in-processed':'images_processed','xrayedge-research-in':'images_anonymized',}
    try:
        cnx = mysql.connector.connect(user=db_user, password=db_password,
                                      host=db_host,
                                      database=db_db)
        cursor = cnx.cursor()
        query = 'SELECT name FROM ' + bucket_table[bucket_name] + ' ORDER BY time DESC LIMIT 1;'
        cursor.execute(query)
        data = cursor.fetchone()
        if data is not None:
            result = data[0]
        else:
            result = ""
        cursor.close()
        cnx.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

    return result


LOCATION_TEMPLATE_SMALL = Template("""
    <img src="${service_point}/${bucket_name}/${image_name}" style="width:260px;"></img>""")

LOCATION_TEMPLATE_BIG = Template("""
    <img src="${service_point}/${bucket_name}/${image_name}" style="width:575px;"></img>""")

app = Flask(__name__)
CORS(app)

@app.route('/')
def homepage():
    return "Hello world"

@app.route('/last_image_small/<bucket_name>')
def last_image_small(bucket_name):
    image_name = get_last_image(bucket_name)
    if image_name != "":   
        html = LOCATION_TEMPLATE_SMALL.substitute(service_point=service_point, bucket_name=bucket_name, image_name=image_name)
    else:
        html = '<h2 style="font-family: Roboto,Helvetica Neue,Arial,sans-serif;text-align: center; color: white;font-size: 15px;font-weight: 400;">No image to show</h2>'
    return html

@app.route('/last_image_big/<bucket_name>')
def last_image_big(bucket_name):
    image_name = get_last_image(bucket_name)   
    if image_name != "":   
        html = LOCATION_TEMPLATE_BIG.substitute(service_point=service_point, bucket_name=bucket_name, image_name=image_name)
    else:
        html = '<h2 style="font-family: Roboto,Helvetica Neue,Arial,sans-serif;text-align: center; color: white;font-size: 15px;font-weight: 400;">No image to show</h2>'
    return html



if __name__ == '__main__':
    app.run(host='0.0.0.0')

