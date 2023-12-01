## 目的

示範 cloud run service to service (同步)
參考官方文章 [1]

三種可以使用的連線方式:
- Private Google Access (PGA) 
- Internal Load Balancer
- Private Service Connect (PSC)

Cloud Run Traffic 打通到 VPC 的方式有兩種
- Serverless VPC Access
- Direct VPC egress

需注意來源方 Cloud Run 若採用  Serverless VPC Access 進行連接時，因為 Serverless VPC Access 會自動建立一個有開啟 PGA 功能但使用者看不到的 Subnet，所以不需要額外設定開啟 PGA

[1] https://cloud.google.com/run/docs/securing/private-networking#from-other-services

## Prerequisites

Ensure you have [Python 3](https://www.python.org/downloads/) and [the Pulumi CLI](https://www.pulumi.com/docs/get-started/install/).

We will be deploying to Google Cloud Platform (GCP), so you will need an account. If you don't have an account,
[sign up for free here](https://cloud.google.com/free/). In either case,
[follow the instructions here](https://www.pulumi.com/docs/intro/cloud-providers/gcp/setup/) to connect Pulumi to your GCP account.

This example assumes that you have GCP's `gcloud` CLI on your path. This is installed as part of the
[GCP SDK](https://cloud.google.com/sdk/).

Wordpress image base on bitnami [wordpress-nginx](https://hub.docker.com/r/bitnami/wordpress-nginx/)

## Running the Example

After cloning this repo, `cd` into it and run these commands. 

1. Create a new stack, which is an isolated deployment target for this example:

    ```bash
    $ pulumi stack init dev
    ```

2. Set the required configuration variables for this program:

    ```bash
    $ pulumi config set gcp:project <your-gcp-project>
    $ pulumi config set gcp:region <gcp-region>
    ```

    Option: Setup instructions

    ```bash
    gcloud auth configure-docker <gcp-region>-docker.pkg.dev
    ```

3. Deploy everything with the `pulumi up` command.

    ```bash
    $ pulumi up
    ```


Note: you must disable deletion protection before removing the resource (e.g., via pulumi destroy), or the instance cannot be deleted and the provider run will not complete successfully.
