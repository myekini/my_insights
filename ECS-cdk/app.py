#!/usr/bin/env python3
import aws_cdk as cdk
from ecs_cdk.ecs_cdk_stack import MultiContainerEcsStack

app = cdk.App()
MultiContainerEcsStack(app, "MultiContainerEcsStack",)

app.synth()
