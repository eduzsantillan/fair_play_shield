data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${var.project_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

  tags = local.common_tags
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ssm" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_trigger.zip"

  source {
    content  = <<-EOF
import boto3
import json
import os

def lambda_handler(event, context):
    ssm = boto3.client('ssm')
    instance_id = os.environ['EC2_INSTANCE_ID']
    
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [
                'cd /home/ec2-user/fair_play_shield',
                'docker-compose exec -T app python main.py --step all --seasons 1',
                'echo "Pipeline completed at $(date)"'
            ]
        },
        TimeoutSeconds=3600
    )
    
    command_id = response['Command']['CommandId']
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Pipeline triggered successfully',
            'command_id': command_id,
            'instance_id': instance_id
        })
    }
EOF
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "trigger" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-pipeline-trigger"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60

  environment {
    variables = {
      EC2_INSTANCE_ID = aws_instance.app.id
    }
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_event_rule" "weekly_trigger" {
  name                = "${var.project_name}-weekly-pipeline"
  description         = "Trigger pipeline every Monday at 6 AM UTC"
  schedule_expression = "cron(0 6 ? * MON *)"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.weekly_trigger.name
  target_id = "TriggerLambda"
  arn       = aws_lambda_function.trigger.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_trigger.arn
}

output "lambda_function_name" {
  description = "Lambda function name for manual invocation"
  value       = aws_lambda_function.trigger.function_name
}
