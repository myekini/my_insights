from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_efs as efs
from aws_cdk import aws_logs as logs
from constructs import Construct


class EarnipayCdkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Set static tags as they are the latest images
        frappe_tag = "frappe-staging-latest"
        mariadb_tag = "mariadb-staging-latest"
        redis_tag = "redis-staging-latest"

        # Import the default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        # Create an ECS Cluster within the default VPC
        cluster = ecs.Cluster(self, "EarnipayCluster", vpc=vpc, cluster_name="earnipay-cluster")

        # Define a single ECR repository for Frappe, MariaDB, and Redis
        repository = ecr.Repository.from_repository_name(self, "EarnipayRepo", "earnipay/dashboard")

        # Create an EFS file system for MariaDB persistence, within the default VPC
        file_system = efs.FileSystem(self, "MariaDbEfs", vpc=vpc)

        # Define a Fargate Task Definition
        task_definition = ecs.FargateTaskDefinition(self, "EarnipayTask",
            memory_limit_mib=2048,
            cpu=1024
        )

        # Add MariaDB Container
        mariadb_container = task_definition.add_container(
            "MariaDbContainer",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag=mariadb_tag),
            environment={"MYSQL_ROOT_PASSWORD": "123"},
            logging=ecs.LogDriver.aws_logs(stream_prefix="MariaDB", log_retention=logs.RetentionDays.ONE_WEEK)
        )
        # Attach EFS to MariaDB for persistence
        mariadb_container.add_mount_points(ecs.MountPoint(
            container_path="/var/lib/mysql",
            source_volume="mariadb-data",
            read_only=False
        ))

        # Add Redis Container
        task_definition.add_container(
            "RedisContainer",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag=redis_tag),
            logging=ecs.LogDriver.aws_logs(stream_prefix="Redis", log_retention=logs.RetentionDays.ONE_WEEK)
        )

        # Add Frappe Container
        frappe_container = task_definition.add_container(
            "FrappeContainer",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag=frappe_tag),
            logging=ecs.LogDriver.aws_logs(stream_prefix="Frappe", log_retention=logs.RetentionDays.ONE_WEEK),
            command=["bash", "/workspace/init.sh"],
            environment={"SHELL": "/bin/bash"},
            working_directory="/home/frappe"
        )
        frappe_container.add_port_mappings(ecs.PortMapping(container_port=8000))

        # Define EFS Volume for MariaDB persistence
        task_definition.add_volume(name="mariadb-data", efs_volume_configuration=ecs.EfsVolumeConfiguration(
            file_system_id=file_system.file_system_id
        ))

        # Create Fargate Service
        service = ecs.FargateService(self, "EarnipayService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=2,
            assign_public_ip=True,
            service_name="earnipay-service"
        )

        # Enable Auto-scaling for the Fargate Service
        scalable_target = service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=5
        )
        scalable_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=50
        )
