import logging
import math
import os
import random
import sys
import uuid

import boto3
import names

import mysql.connector
from ach.builder import AchFile

# banks format = (routing without check_digit, name)
banks = [
    ('06200001','BANK OF NEW-YORK'),
    ('06200002','BANK OF CHICAGO'),
    ('06200003','BANK OF BOSTON'),
    ('06200004','BANK OF LOS ANGELES'),
    ('06200005','BANK OF ORLANDO'),
    ('06200006','BANK OF DENVER'),
    ('06200007','BANK OF SEATTLE')
]

# companies format = (ACH id, name)
companies = [
    ('5094142940','Seamless Car Ltd'),
    ('0256851808','SunRay Candies Inc'),
    ('2966751269','Monocles Lighting Ltd'),
    ('1035542944','Collaborative Dogs Inc'),
    ('9155404762','Homegrown UFO Ltd'),
    ('9950412630','Guitars Valley Inc'),
    ('1050377871','Snow Avatar Ltd'),
    ('0041596227','Aero North Inc'),
    ('5345923695','Aqua Sausage Ltd'),
    ('8048237614','Vantage Comics Inc')
]

companies_banks = [1,2,3,4,5,6,0,1,2,3]

access_key = os.environ['AWS_ACCESS_KEY_ID']
secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
service_point = os.environ['service_point']

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

s3client = boto3.client('s3', 'us-east-1', endpoint_url=service_point,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        use_ssl=True if 'https' in service_point else False)

def save_file(bucket_name, file_name, content):
    sent_data = s3client.put_object(
        Bucket=bucket_name, Key=file_name, Body=content)
    if sent_data['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise logging.error(
            'Failed to upload file {} to bucket {}'.format(file_name, bucket_name))

def calc_check_digit(entry):
    multipliers = [3, 7, 1, 3, 7, 1, 3, 7]
    tmp_num = 0
    for num, mult in zip(list(entry), multipliers):
        tmp_num += int(num) * mult
    nearest_10 = math.ceil(tmp_num / 10.0)
    return str(int((nearest_10 * 10) - tmp_num))

# Create random settings entry for the ACH file
def create_setting_entry():
    selected_company = random.randint(0,9)  # Select a random company
    selected_bank = companies_banks[selected_company]  # Find the corresponding bank (ODFI)
    immediate_dest = banks[selected_bank][0]+calc_check_digit(banks[selected_bank][0])  # ODFI Bank routing number
    immediate_org = companies[selected_company][0]  #  Company's ACH id
    immediate_dest_name = banks[selected_bank][1]  # Bank's name
    immediate_org_name = companies[selected_company][1]  # Company's name
    company_id = companies[selected_company][0] #  Company's ACH id (again, comes from original generator)
    
    settings = {
        'immediate_dest' : immediate_dest,
        'immediate_org' : immediate_org,
        'immediate_dest_name' : immediate_dest_name,
        'immediate_org_name' : immediate_org_name,
        'company_id' : company_id, #tax number
    }

    return settings

# Create random transaction entries
def create_transactions_entries():
    max_entries = random.randint(300,500)  # Number of transactions per files
    entries=[]
    for x in range (1,max_entries):
        routing_number = banks[random.randint(0,6)][0][0:8] # Randomly select an RDFI bank (customer's bank)
        account_number = str(random.randint(111111111,999999999))   # Random customer account number
        amount = str(random.randint(100,200000)/100)  # Random amount between 1.00 and 2000.00
        name = names.get_full_name()  #  Generates random names
        entries.append({
            'type'           : '27',  #  We're creating debits only
            'routing_number' : routing_number,
            'account_number' : account_number,
            'amount'         : amount,
            'name'           : name

        })     
    
    return entries

def update_merchant_upload():
    try:
        cnx = mysql.connector.connect(user='achuser', password='achpassword',
                                      host='achdb.ach-db',
                                      database='achdb')
        cursor = cnx.cursor()
        query = 'INSERT INTO merchant_upload(time,entry) SELECT CURRENT_TIMESTAMP(), 1;'
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

# Initialize a new ACH file
ach_file = AchFile('A', create_setting_entry())

# Create entries
entries = create_transactions_entries()

# Populate ACH file with generated entries
ach_file.add_batch('POS', entries, credits=True, debits=True)

# Save generated file to merchant-upload bucket
bucket_name = 'ach-merchant-upload'
file_name = str(uuid.uuid4()) + '.ach'
content = ach_file.render_to_string()
save_file(bucket_name, file_name, content)
update_merchant_upload()
