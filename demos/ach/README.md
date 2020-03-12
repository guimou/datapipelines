# ACH process

This demo shows how to implement an ACH payment process, leveraging Ceph notifications, Kafka and KNative.

What you will find here:

* [Slides](Automate%20and%20scale%20your%20data%20pipelines%20the%20Cloud%20Native%20Way.pdf) from a presentation of this demo. The full video of the presentation is available [here](http://youtu.be/) (link to come)
* topics.yaml: definition of the Kafka topics needed in the demo
* secret.yaml: used to provide your Ceph Access and Secret Keys to the other containers
* service-....yaml: definition of the services that are used to process the data at the different steps
* kafkasource-....yaml: definition of the KafkaSource objects for KNative eventing
* transaction-job.yaml: definition of the job that will generate the transactions (initiation of the pipeline)

In the **containers** folder you will find the code to generate different container images:

* Transactions generator: creates random transactions, put them in an ACH file, and send it to the ach-merchant-upload bucket.
* ODFI splitter: upon notification, retrieves ACH file from the ach-merchant-upload bucket, extracts the origin bank number, and puts the files in the associated buckets (ach-odfi-060000x)
* RDI splitter: upon notification, retrieves ACH file from the ach-odfi-060000x bucket, extracts transactions by RDFI number, generates new ACH files and puts them in the associated buckets (ach-rdfi-060000x)
* RDI processor: upon notification, retrieves ACH file from the ach-rdfi-060000x bucket, extracts transactions and add the amounts to the total (saved in small external database)

In the **tools** folder you will also find:

* ach file generator.ipynb: base notebook to see how ach files are generated
* ach_dashboard.yaml: definition of the grafana dasboard used in this demo
* ach-bd.txt: various SQL commands to create and (re)initialize tables used in the auxiliary database (used to store the number of processed files)
* amq-streams-ocs4.yaml: definition od the KafkaCluster created with the AMQStreams operator, using OCS4 storage for persistency
* grafana-prometheus-datasource.yaml: datasource for the Grafana Operator to connect to OpenShift Prometheus. You will have to replace the secret (basicAuth) by the one used by the built-in OpenShift Grafana.
* kafdrop.yaml: installation of Kafdrop to monitor your Kafka/AMQStreams cluster
