import aws_cdk as cdk
from ecs_cdk.ecs_cdk_stack import MultiContainerEcsStack

app = cdk.App()

# Instantiate the MultiContainerEcsStack with hardcoded account and region
MultiContainerEcsStack(app, "MultiContainerEcsStack",
    env=cdk.Environment(
        account="816069156617",
        region="us-east-1"
    )
)

app.synth()