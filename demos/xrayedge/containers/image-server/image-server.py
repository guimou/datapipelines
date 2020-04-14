import logging
import sys
import os
from flask import Flask, redirect
from string import Template

import mysql.connector

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
        query = 'SELECT name FROM ' + bucket_table[bucket_name] + ' ORDER BY TIME LIMIT 1;'
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        cnx.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

    return result[0]


LOCATION_TEMPLATE = Template("${service_point}/${bucket_name}/${image_name}")

app = Flask(__name__)
@app.route('/')
def homepage():
    return "Hello world"

@app.route('/last_image/<bucket_name>')
def last_image(bucket_name):
    image_name = get_last_image(bucket_name)   
    location = LOCATION_TEMPLATE.substitute(bucket_name=bucket_name,image_name=image_name)

    return redirect(location, code=302)



if __name__ == '__main__':
    app.run(host='0.0.0.0')



