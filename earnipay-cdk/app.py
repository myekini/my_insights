import aws_cdk as cdk
from earnipay_cdk.earnipay_cdk_stack import EarnipayCdkStack

app = cdk.App()

# Instantiate the MultiContainerEcsStack with hardcoded account and region
EarnipayCdkStack(app, "EarnipayCdkStack", env=cdk.Environment(account="816069156617", region="us-east-1"))

app.synth()
