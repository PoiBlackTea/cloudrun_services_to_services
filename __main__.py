"""A Google Cloud Python Pulumi program"""

import pulumi
import pulumi_docker as docker
import pulumi_gcp as gcp

# Case 1 PGA 單獨vpc，實際測試時手動關閉PGA示範可以通 (可以考慮建立一個 GCE call cloud run)
# Case 2 共用 cloud run  internal Load Balancer
# Case 3 PSC 共用 cloud run 新 vpc 連線


config = pulumi.Config()
gcp_config = pulumi.Config("gcp")
gcp_region = gcp_config.require("region")
gcp_project = gcp_config.require("project")

repository_id = "external"
cloudrun_name = "external_cloudrun"
image_name = f"{gcp_region}-docker.pkg.dev/{gcp_project}/{repository_id}/{cloudrun_name}:demo"


repo = gcp.artifactregistry.Repository(
    "my-repo",
    description="example Docker repository",
    docker_config=gcp.artifactregistry.RepositoryDockerConfigArgs(
        immutable_tags=True,
    ),
    format="DOCKER",
    location=gcp_region,
    repository_id=repository_id
)

cloudrun_image = docker.Image("cloudrun-image",
    image_name=image_name,
    build=docker.DockerBuildArgs(
        args={
            "platform": "linux/amd64",
        },
        context="upstream_cloudrun/",
        dockerfile="upstream_cloudrun/Dockerfile",
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[repo]
    )
)

# create cloud function service account
service_account = gcp.serviceaccount.Account("serviceAccount",
    account_id="cloudrun-sa",
    display_name="cloud run sa"
)


# create custom vpc with pga
internal_network= gcp.compute.Network("internal-vpc",
    auto_create_subnetworks=False,
    description="internal vpc with pga",
    mtu=1500
)


# create custom vpc subnet with pga
subnetwork = gcp.compute.Subnetwork("demo-subnet",
    ip_cidr_range="10.0.1.0/24",
    region=gcp_region,
    network=internal_network.id,
    private_ip_google_access=True
)


# create vpc access connector in  internal connector
vpc_connector = gcp.vpcaccess.Connector("vpc-connector",
    ip_cidr_range="10.1.0.0/28",
    network=internal_network.id,
    opts=pulumi.ResourceOptions(
        depends_on=[internal_network]
    )
)

# create downstream cloud run service
downstream_cloudrun = gcp.cloudrunv2.Service(
    "downstream-cloudrun",
    location=gcp_region,
    ingress="INGRESS_TRAFFIC_INTERNAL_ONLY",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        containers=[
            gcp.cloudrunv2.ServiceTemplateContainerArgs(
                image="us-docker.pkg.dev/cloudrun/container/hello"
            )
        ],
        scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(
                max_instance_count=1,
                min_instance_count=0
        ),
        service_account=service_account.email,
        execution_environment="EXECUTION_ENVIRONMENT_GEN2",
        timeout="3600s",
        session_affinity=True,
    ),
    traffics=[
        gcp.cloudrunv2.ServiceTrafficArgs(
            type="TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
            percent=100,
        )
    ],
    opts=pulumi.ResourceOptions(depends_on=[])
)


# create cloud run service with pga
service_use_pga = gcp.cloudrunv2.Service(
    "cloudrun-with-pga",
    location=gcp_region,
    ingress="INGRESS_TRAFFIC_ALL",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        containers=[gcp.cloudrunv2.ServiceTemplateContainerArgs(
            image=image_name,
            envs=[
                gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                    name="endpoint",
                    value=downstream_cloudrun.uri,
                )
            ],
            ports=[gcp.cloudrunv2.ServiceTemplateContainerPortArgs(
                container_port=80
            )]
        )],
        vpc_access=gcp.cloudrunv2.ServiceTemplateVpcAccessArgs(
            connector=vpc_connector.id,
            egress="ALL_TRAFFIC",
        ),
        scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(
                max_instance_count=1,
                min_instance_count=0
        ),
        service_account=service_account.email,
        execution_environment="EXECUTION_ENVIRONMENT_GEN2",
        timeout="3600s",
        session_affinity=True,
    ),
    traffics=[gcp.cloudrunv2.ServiceTrafficArgs(
        type="TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
        percent=100,
    )],
    opts=pulumi.ResourceOptions(depends_on=[])
)



downstream_iam = gcp.cloudrunv2.ServiceIamMember(
    "downstream-iam",
    name=downstream_cloudrun.id,
    role="roles/run.invoker",
    member="allUsers"
)

service_use_pga_iam = gcp.cloudrunv2.ServiceIamMember(
    "service-pga-iam",
    name=service_use_pga.id,
    role="roles/run.invoker",
    member="allUsers"
)



# Case 2
serverless_neg = gcp.compute.RegionNetworkEndpointGroup(
    "internalneg",
    network_endpoint_type="SERVERLESS",
    region=gcp_region,
    cloud_run=gcp.compute.RegionNetworkEndpointGroupCloudRunArgs(
        service=downstream_cloudrun.name,
    )
)

loadbalancer_backend = gcp.compute.RegionBackendService(
    "serverlessneg",
    load_balancing_scheme="INTERNAL_MANAGED",
    protocol="HTTP2",
    region=gcp_region,
    backends=[gcp.compute.RegionBackendServiceBackendArgs(
        group=serverless_neg.self_link,
        balancing_mode="UTILIZATION"
    )]
)

# create custom vpc subnet with proxy
proxy_subnetwork = gcp.compute.Subnetwork(
    "proxy-subnet",
    ip_cidr_range="10.0.201.0/24",
    region=gcp_region,
    purpose="REGIONAL_MANAGED_PROXY",
    role="ACTIVE",
    network=internal_network.id
)

# Create a URL map
url_map = gcp.compute.RegionUrlMap(
    'internallb-url-map',
    default_service=loadbalancer_backend.self_link
)

# Create a Target HTTP Proxy
target_http_proxy = gcp.compute.RegionTargetHttpProxy(
    'example-http-proxy',
    url_map=url_map.self_link,
    region=gcp_region
)

# create internal load balancer ip
addr = gcp.compute.Address(
    "addr", 
    region=gcp_region,
    subnetwork=subnetwork.id,
    address_type="INTERNAL"
)

# Lastly, create a global Forwarding Rule
forwarding_rule = gcp.compute.ForwardingRule(
    'internal-forwardingrule',
    target=target_http_proxy.self_link,
    port_range='80',
    load_balancing_scheme="INTERNAL_MANAGED",
    ip_address=addr.self_link,
    network=internal_network,
    subnetwork=subnetwork
)


# create cloud run service with pga
external_cloudrun_internallb = gcp.cloudrunv2.Service("cloudrun-with-ilb",
    location=gcp_region,
    ingress="INGRESS_TRAFFIC_ALL",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        containers=[gcp.cloudrunv2.ServiceTemplateContainerArgs(
            image=image_name,
            envs=[
                gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                    name="endpoint",
                    value=addr.address.apply(lambda address: "http://" + address),
                )
            ],
            ports=[gcp.cloudrunv2.ServiceTemplateContainerPortArgs(
                container_port=80
            )]
        )],
        vpc_access=gcp.cloudrunv2.ServiceTemplateVpcAccessArgs(
            connector=vpc_connector.id,
            egress="PRIVATE_RANGES_ONLY",
        ),
        scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(
                max_instance_count=1,
                min_instance_count=0
        ),
        service_account=service_account.email,
        execution_environment="EXECUTION_ENVIRONMENT_GEN2",
        timeout="3600s",
        session_affinity=True,
    ),
    traffics=[gcp.cloudrunv2.ServiceTrafficArgs(
        type="TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
        percent=100,
    )],
    opts=pulumi.ResourceOptions(depends_on=[])
)

service_iam_member_3 = gcp.cloudrunv2.ServiceIamMember("service-iam-member_3",
    name=external_cloudrun_internallb.id,
    role="roles/run.invoker",
    member="allUsers"
)



# create custom vpc with cloud dns
# cloudrun_network_with_clouddns = gcp.compute.Network("cloudrun-vpc3",
#     auto_create_subnetworks=False,
#     description="cloudrun vpc with dns",
#     mtu=1500)

# # create custom vpc subnet with cloud dns
# cloudrun_subnetwork_with_clouddns = gcp.compute.Subnetwork("cloudrun-demo-subnet3",
#     ip_cidr_range="10.0.3.0/24",
#     region=gcp_region,
#     network=cloudrun_network_with_clouddns.id,
#     private_ip_google_access=False)

pulumi.export("Ennable PGA", pulumi.Output.format(service_use_pga.uri))
pulumi.export("Use Internal Load Balancer", pulumi.Output.format(external_cloudrun_internallb.uri))