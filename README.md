# Sending AWS cost notifications via Email or LINE (o^∇^o)

## Prerequisites
- You are using AWS multi-account (Organizations) environment
- You have set up Linked Account using filters in Budgets  
  [AWS Budgets Document](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-create-filters.html#:~:text=.-,Linked%20Account,-Choose%20an%20AWS)
- If you are using `CostNotificationEmail.py`, please preconfigure SNS settings.

## Instructions

### 1. AWS Lambda Configuration
   1. #### Code Configuration
      Don't forget to set the filename and handler configurations.
      - `LoggingClass.py`
      - `CostNotificationEmail.py` ※ When using AWS SNS to notify cost via Email
      - `CostNotificationLINE.py` ※ When notifying cost via LINE

   2. #### Environment Variables Configuration
      Set the following environment variables.
      - `ACCOUNT_ID` : Organizations Master Account
      - `BUDGET_NAME` : The name of the budget created in Budgets
      - `LOG_LEVEL` : `INFO` or `DEBUG`
      - `SNS_TOPIC_ARN` : The ARN of the SNS topic ※ Required when using `CostNotificationEmail.py`
      - `LINE_NOTIFY_TOKEN` : The token issued on LINE (PC) ※ Required when using `CostNotificationLINE.py`

   3. #### IAM Role Configuration
      Access permissions to the following AWS resources are required.
      - `CloudWatch Logs`
      - `Organizations`
      - `Cost Explorer`
      - `Budgets`
      - `SNS`

### 2. AWS EventBridge Rule Configuration
   Configure the Cron setting in the rule of AWS EventBridge. If you want to notify at the end of every month, configure as follows.
   ```bash
   0 0 L * ? *