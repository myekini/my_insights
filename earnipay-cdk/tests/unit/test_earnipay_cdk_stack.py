import aws_cdk as core
import aws_cdk.assertions as assertions

from earnipay_cdk.earnipay_cdk_stack import EarnipayCdkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in earnipay_cdk/earnipay_cdk_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = EarnipayCdkStack(app, "earnipay-cdk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
