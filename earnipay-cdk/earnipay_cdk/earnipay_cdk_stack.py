from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_efs as efs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct


class EarnipayCdkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Image tags for Frappe
        frappe_tag = "frappe-staging-latest"

        # Import the default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        # ECS Cluster
        cluster = ecs.Cluster(self, "EarnipayCluster", vpc=vpc, cluster_name="earnipay-cluster")

        # EFS File System and Security Group (pre-created)
        efs_file_system_id = "fs-0e9028aef21a04f20"
        efs_security_group_id = "sg-05ef1001c9b846a54"
        efs_security_group = ec2.SecurityGroup.from_security_group_id(self, "EFSSecurityGroup", efs_security_group_id)

        # Reference existing EFS file system
        file_system = efs.FileSystem.from_file_system_attributes(
            self,
            "ExistingEFS",
            file_system_id=efs_file_system_id,
            security_group=efs_security_group
        )

        # ECS Task Role with EFS permissions
        ecs_task_role = iam.Role(self, "ECSTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            inline_policies={
                "EFSAccessPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"],
                            resources=[f"arn:aws:elasticfilesystem:{self.region}:{self.account}:file-system/{efs_file_system_id}"],
                            effect=iam.Effect.ALLOW
                        )
                    ]
                )
            }
        )

        # Create ECS Task Security Group for NFS Traffic
        ecs_security_group = ec2.SecurityGroup(self, "ECSTaskSecurityGroup", vpc=vpc)
        ecs_security_group.add_egress_rule(
            ec2.Peer.security_group_id(efs_security_group.security_group_id),
            ec2.Port.tcp(2049),
            "Allow NFS traffic to EFS"
        )

        # Define Fargate Task Definition
        task_definition = ecs.FargateTaskDefinition(self, "EarnipayTask",
            memory_limit_mib=2048,
            cpu=1024,
            execution_role=ecs_task_role
        )

        # MariaDB Container (directly from Docker Hub)
        mariadb_container = task_definition.add_container(
            "MariaDbContainer",
            image=ecs.ContainerImage.from_registry("mariadb:10.8"),  # Pulling from Docker Hub
            environment={
                "MYSQL_ROOT_PASSWORD": "123"
            },
            command=[
                "--character-set-server=utf8mb4",
                "--collation-server=utf8mb4_unicode_ci",
                "--skip-character-set-client-handshake",
                "--skip-innodb-read-only-compressed"
            ],
            logging=ecs.LogDriver.aws_logs(stream_prefix="MariaDB", log_retention=logs.RetentionDays.ONE_WEEK),
            essential=True,
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "mysqladmin ping -h localhost"],
                retries=2,
            )
        )
        mariadb_container.add_mount_points(ecs.MountPoint(
            container_path="/var/lib/mysql",
            source_volume="mariadb-data",
            read_only=False
        ))

        # Redis Container (directly from Docker Hub)
        redis_container = task_definition.add_container(
            "RedisContainer",
            image=ecs.ContainerImage.from_registry("redis:alpine"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="Redis", log_retention=logs.RetentionDays.ONE_WEEK),
            essential=True,
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "redis-cli ping"],
                retries=3,
            )
        )

        # Frappe Container (from ECR repository)
        frappe_container = task_definition.add_container(
            "FrappeContainer",
            image=ecs.ContainerImage.from_ecr_repository(ecr.Repository.from_repository_name(self, "FrappeRepo", "earnipay/dashboard"), tag=frappe_tag),
            logging=ecs.LogDriver.aws_logs(stream_prefix="Frappe", log_retention=logs.RetentionDays.ONE_WEEK),
            command=["bash", "/workspace/init.sh"],
            environment={"SHELL": "/bin/bash"},
            working_directory="/home/frappe",
            essential=True
        )
        frappe_container.add_port_mappings(ecs.PortMapping(container_port=8000))

        # Set Frappe dependencies (MariaDB and Redis must be healthy)
        frappe_container.add_container_dependencies(
            ecs.ContainerDependency(container=mariadb_container, condition=ecs.ContainerDependencyCondition.HEALTHY),
            ecs.ContainerDependency(container=redis_container, condition=ecs.ContainerDependencyCondition.HEALTHY)
        )

        # EFS Volume for MariaDB
        task_definition.add_volume(name="mariadb-data", efs_volume_configuration=ecs.EfsVolumeConfiguration(
            file_system_id=file_system.file_system_id,
            root_directory="/"
        ))

        # Fargate Service
        service = ecs.FargateService(self, "EarnipayService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            assign_public_ip=True,
            security_groups=[ecs_security_group],
            service_name="earnipay-service"
        )

        # Enable Auto-scaling
        scalable_target = service.auto_scale_task_count(min_capacity=1, max_capacity=5)
        scalable_target.scale_on_cpu_utilization("CpuScaling", target_utilization_percent=50)
