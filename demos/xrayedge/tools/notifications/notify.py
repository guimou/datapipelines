#! /usr/bin/env python

'''
@Author Shon Paz
@Date   16/02/2020
'''

import boto3
import json
import botocore
import argparse

'''This class configures bucket notifications for both kafka and rabbitmq endpoints for real-time message queuing'''


class Notifier:

    def __init__(self):

        # creates all needed arguments for the program to run
        parser = argparse.ArgumentParser()
        parser.add_argument('-ac', '--action', help="action to execute, see doc for all options", required=True)
        parser.add_argument('-e', '--endpoint-url', help="endpoint url for s3 object storage", required=True)
        parser.add_argument('-a', '--access-key', help='access key for s3 object storage', required=True)
        parser.add_argument('-s', '--secret-key', help='secret key for s3 object storage', required=True)
        parser.add_argument('-b', '--bucket-name', help='s3 bucket name', required=False)
        parser.add_argument('-ke', '--kafka-endpoint', help='kafka endpoint in which rgw will send notifications to', required=False)
        parser.add_argument('-ae', '--amqp-endpoint', help='amqp endpoint in which rgw will send notifications to', required=False)
        parser.add_argument('-he', '--http-endpoint', help='http endpoint in which rgw will send notifications to', required=False)
        parser.add_argument('-al', '--ack-level', help='ack level for kafka and amqp, defaults to broker', required=False, default='broker')
        parser.add_argument('-t', '--topic', help='topic name in which rgw will send notifications to', required=False)
        parser.add_argument('-f', '--filter', help='filter such as prefix, suffix, metadata or tags', required=False)
        parser.add_argument('-o', '--opaque', help='opaque data that will be sent in the notifications', required=False)
        parser.add_argument('-x', '--exchange', help='amqp exchange name (mandatory for amqp endpoints)', required=False)
        parser.add_argument('-n', '--notification', help='notification name, allows for setting multiple notifications on the same bucket', required=False, default="configuration")

        # parsing all arguments
        args = parser.parse_args()

        # building instance vars
        self.action = args.action
        self.endpoint_url = args.endpoint_url
        self.access_key = args.access_key
        self.secret_key = args.secret_key
        self.bucket_name = args.bucket_name
        self.kafka_endpoint = args.kafka_endpoint
        self.http_endpoint = args.http_endpoint
        self.amqp_endpoint = args.amqp_endpoint
        self.ack_level = args.ack_level
        self.topic = args.topic
        self.filter = args.filter 
        self.opaque = args.opaque
        self.exchange = args.exchange
        self.notification = args.notification
        self.sns = boto3.client('sns', 
                               endpoint_url=self.endpoint_url, 
                               aws_access_key_id=self.access_key,
                               region_name='default', 
                               aws_secret_access_key=self.secret_key,
                               config=botocore.client.Config(signature_version = 's3'))

        self.s3 = boto3.client('s3',
                              endpoint_url = self.endpoint_url,
                              aws_access_key_id = self.access_key,
                              aws_secret_access_key = self.secret_key,
                              region_name = 'default',
                              config=botocore.client.Config(signature_version = 's3'))


    ''' This function lists all sns-like topic with configured endpoint'''
    def list_sns_topics(self):
     
        attributes = {}

        # lists the sns-like topics on RGW and gets the topics' ARN
        topics = self.sns.list_topics()

        if 'Topics' in topics:
            for topic in topics['Topics']:
                print(topic['TopicArn'])
        else:
            print('No topic configured')


    ''' This function creates an sns-like topic with configured push endpoint'''
    def create_sns_topic(self):
        attributes = {}

        if self.opaque:
            attributes['OpaqueData'] = self.opaque

        # in case wanted MQ endpoint is kafka 
        if(self.kafka_endpoint):
            attributes['push-endpoint'] = 'kafka://' + self.kafka_endpoint
            attributes['kafka-ack-level'] = self.ack_level
        
        # in case wanted MQ endpoint is rabbitmq
        elif(self.amqp_endpoint): 
            attributes['push-endpoint'] = 'amqp://' + self.amqp_endpoint
            attributes['amqp-exchange'] = self.exchange_name
            attributes['amqp-ack-level'] = self.ack_level
       
        # in case wanted MQ endpoint is http
        elif(self.http_endpoint):
            attributes['push-endpoint'] = 'http://' + self.http_endpoint

        # in case wanted MQ endpoint is not provided by the user 
        else:
            raise Exception("please configure a push endpoint!")

        # creates the wanted sns-like topic on RGW and gets the topic's ARN
        self.topic_arn = self.sns.create_topic(Name=self.topic, Attributes=attributes)['TopicArn']

    ''' This function deletes an sns-like topic'''
    def delete_sns_topic(self):

        # lists the sns-like topics on RGW and gets the topic's ARN that matchs request
        topics = self.sns.list_topics()

        if 'Topics' in topics:
            for topic in topics['Topics']:
                found = False
                arn = topic['TopicArn']
                topic_name = arn.split('::')[1]
                if topic_name == self.topic :
                    self.sns.delete_topic(TopicArn = arn)
                    found = True

            if not found:
                print('No topic with this name was found') 
        else:
            print('No topic configured')

    ''' This function lists all topics configured on a bucket'''
    def list_bucket_topics(self):

        configuration = self.s3.get_bucket_notification_configuration(Bucket=self.bucket_name)

        if 'TopicConfigurations' in configuration:
            for topic in configuration['TopicConfigurations']:
                print('TopicArn: ' + topic['TopicArn'] + ', Events: ' + ' '.join(topic['Events']))
        else:
            print('No notification configured')

    ''' This function configures bucket notification for object creation and removal '''
    def configure_bucket_notification(self): 
        
        # creates a bucket if it doesn't exists
        try: 
            self.s3.head_bucket(Bucket=self.bucket_name)
        except botocore.exceptions.ClientError:
            self.s3.create_bucket(Bucket = self.bucket_name)

        # initial dictionary 
        bucket_notifications_configuration = {
            "TopicConfigurations": [
                {
                    "Id": self.notification,
                    "TopicArn": self.topic_arn,
                    "Events": ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"]
                }
            ]
        }
        
        # in case the user has provided a filter to use 
        if(self.filter):
            bucket_notifications_configuration['TopicConfigurations'][0].update({'Filter': json.loads(self.filter)})

        # pushed the notification configuration to the bucket 
        self.s3.put_bucket_notification_configuration(Bucket = self.bucket_name,
                                                        NotificationConfiguration=bucket_notifications_configuration)

if __name__ == '__main__':

    # creates an notifier instance from class
    notifier = Notifier()

    if notifier.action == 'list-topics':
        notifier.list_sns_topics()

    if notifier.action == 'create-topic':
        notifier.create_sns_topic()

    if notifier.action == 'delete-topic':
        notifier.delete_sns_topic()
    
    if notifier.action == 'list-bucket-topics':
        notifier.list_bucket_topics()

    if notifier.action == 'configure-bucket-notification':
        notifier.configure_bucket_notification()

    if notifier.action == 'create-notification':
        # create sns-like topic sent to MQ endpoint 
        notifier.create_sns_topic()

        # configures object creation and removal based notification for the bucket
        notifier.configure_bucket_notification()


