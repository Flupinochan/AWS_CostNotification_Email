"""
▼Title
    Notify cost
▼Author
    Flupinochan
▼Version
    1.0
▼Execution Environment
    Python 3.10 / For Lambda
▼Overview
    Python for aggregating the cost of the current month for the accounts set in the AWS Budgets filter, and sending it via email
▼Remarks
    Need to set linked accounts in the filter for Budgets
"""

import datetime
import os
import sys
import boto3

from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config
from LoggingClass import LoggingClass

# ----------------------------------------------------------------------
# Constant Definitions
# ----------------------------------------------------------------------

# Time zones JST, UTC
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# Log Level (default is INFO)
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Retry count when using client or resource API
RETRY_COUNT = int(os.environ.get('RETRY_COUNT', 3))

# Master AccountID (String Type)
ACCOUNT_ID = os.environ['ACCOUNT_ID']

# Budget Name
BUDGET_NAME = os.environ['BUDGET_NAME']

# SNS ARN
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

# ----------------------------------------------------------------
# Global Variable Definitions
# ----------------------------------------------------------------

# Set arguments like retry counts and region when using client or resource API
config = Config(
    region_name='ap-northeast-1',
    retries={
        'max_attempts': RETRY_COUNT,
        'mode': 'standard'
    }
)

# Both are global services, so region setting is ignored
# Budgets API settings
client_budgets = boto3.client('budgets', config=config)
# Cost Explorer API settings
client_cost_explorer = boto3.client('ce', config=config)
# SNS API settings
resource_sns = boto3.resource('sns', config=config)
sns_topic = resource_sns.Topic(SNS_TOPIC_ARN)
# Organizations API settings
client_organizations = boto3.client('organizations')

# ----------------------------------------------------------------------
# Logger Configuration
# ----------------------------------------------------------------------

# Get Logger object. Use this for log output
logger = LoggingClass(LOG_LEVEL)
log = logger.get_logger()

# Usage example
# log.info("Test")

# ----------------------------------------------------------------------
# Main Processing
# ----------------------------------------------------------------------
def main():

    # sys._getframe().f_code.co_name) will give the function name
    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    # Get the accounts for cost aggregation
    account_list = get_account_list()

    # Get the beginning of the month required to fetch this month's cost
    start_utc_str, end_utc_str = time_processing()

    # Get account name
    account_name_dict = get_account_name(account_list)

    # Get cost ranking
    service_cost_ranking_message = get_service_cost_ranking(account_list, start_utc_str, end_utc_str)
    total_cost, account_cost_ranking_message = get_account_cost_ranking(account_name_dict, start_utc_str, end_utc_str)

    # Send cost ranking
    sns_publish(start_utc_str, service_cost_ranking_message, total_cost, account_cost_ranking_message)

    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))

# ----------------------------------------------------------------------
# Get Account Information
# ----------------------------------------------------------------------
def get_account_list() -> List[str]:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    # Account list
    account_list = []

    response = client_budgets.describe_budget(
        AccountId=ACCOUNT_ID,
        BudgetName=BUDGET_NAME
    )

    # Get AccountID set in Budget's filter
    for values in response['Budget']['CostFilters'].values():
        for value in values:
                account_list.append(value)

    log.debug("Cost aggregation accounts : {}".format(', '.join(account_list)))

    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))

    return account_list

# ----------------------------------------------------------------------
# Time Processing
# ----------------------------------------------------------------------
def time_processing() -> Tuple[str, str]:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    # Beginning of the month, today's date in UTC   ########### Last month for test
    now = datetime.datetime.now(UTC)
    start_utc = datetime.datetime(now.year, now.month-1, 1)
    start_utc_str = start_utc.strftime('%Y-%m-%d')
    end_utc_str = now.strftime('%Y-%m-%d')

    log.debug("UTC start of the month (str) : {}".format(start_utc_str))
    log.debug("UTC today (str) : {}".format(end_utc_str))

    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))

    return start_utc_str, end_utc_str

# ----------------------------------------------------------------------
# Get Service Cost Ranking
# ----------------------------------------------------------------------
def get_service_cost_ranking(arg_account_list: List[str], arg_start_utc_str: str, end_utc_str: str) -> List[str]:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    response = client_cost_explorer.get_cost_and_usage(
        TimePeriod={
            'Start': arg_start_utc_str,
            'End': end_utc_str
        },
        Granularity='MONTHLY',
        Metrics=[
            'UnblendedCost',
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            },
        ],
        Filter={
            'Dimensions': {
                'Key': 'LINKED_ACCOUNT',
                'Values': arg_account_list
            }
        }
    )

    # Array for storing data
    service_cost_ranking_message = []

    # Top 5 High Cost Services
    for index, service in enumerate(sorted(
            [group for group in response['ResultsByTime'][0]['Groups'] if group['Keys'][0] != 'Tax'],
            key=lambda x: float(x['Metrics']['UnblendedCost']['Amount']),
            reverse=True)[:5]):
        
        rank = "TOP" + str(index + 1)
        service_cost_str_float = service['Metrics']['UnblendedCost']['Amount']
        service_cost = service_cost_str_float.split('.')[0]
        unit = service['Metrics']['UnblendedCost']['Unit']
        service_name = service['Keys'][0]


        message = "{} {}{} : {}".format(rank, service_cost, unit, service_name)
        service_cost_ranking_message.append(message)

        log.debug(message)

    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))

    return service_cost_ranking_message


# ----------------------------------------------------------------------
# Get Account Cost Ranking
# ----------------------------------------------------------------------
def get_account_cost_ranking(arg_account_name_dict: Dict[str, str], arg_start_utc_str: str, end_utc_str: str) -> List[str]:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    response = client_cost_explorer.get_cost_and_usage(
        TimePeriod={
            'Start': arg_start_utc_str,
            'End': end_utc_str
        },
        Granularity='MONTHLY',
        Metrics=[
            'UnblendedCost',
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'LINKED_ACCOUNT'
            },
        ]
    )

    total_cost_int = 0
    account_cost_ranking_message = []
    unit = ""

    for index, group in enumerate(sorted(
        [group for group in response['ResultsByTime'][0]['Groups'] if group['Keys'][0] != 'Tax'],
        key=lambda x: float(x['Metrics']['UnblendedCost']['Amount']),
        reverse=True)[:3]):

        rank = "TOP" + str(index + 1)
        account_id = group['Keys'][0]
        account_cost_str_float = group['Metrics']['UnblendedCost']['Amount']
        account_cost = account_cost_str_float.split('.')[0]
        unit = group['Metrics']['UnblendedCost']['Unit'] 

        message = "{} {}{} : {}({})".format(rank, account_cost, unit, arg_account_name_dict[account_id], account_id)
        account_cost_ranking_message.append(message)
    
    for group in response['ResultsByTime'][0]['Groups']:
        total_cost_int += int(float(group['Metrics']['UnblendedCost']['Amount']))
    
    total_cost = str(total_cost_int) + unit

    return total_cost, account_cost_ranking_message




# ----------------------------------------------------------------------
# Get Account Name
# ----------------------------------------------------------------------
def get_account_name(arg_account_list) -> Dict[str, str]:

    account_name_dict = {}

    paginator = client_organizations.get_paginator('list_accounts')
    for page in paginator.paginate():
        for account in page['Accounts']:
            for accountId in arg_account_list:
                if account['Id'] == accountId:
                    account_name_dict[account['Id']] = account['Name']

    return account_name_dict


# ----------------------------------------------------------------------
# SNS(send email)
# ----------------------------------------------------------------------
def sns_publish(arg_start_utc_str, arg_service_cost_ranking_message, arg_total_cost, arg_account_cost_ranking_message) -> None:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))



    # 件名と本文を作成
    service_cost_message = '\n'.join(arg_service_cost_ranking_message)
    account_cost_message = '\n'.join(arg_account_cost_ranking_message)
    total_cost_message = "【Total Cost】\n{}".format(arg_total_cost)

    sns_subject = "【Cost Notification】{}".format(arg_start_utc_str)
    sns_message = total_cost_message + "\n"
    sns_message += "\n【Account Cost Ranking】"
    sns_message += "\n{}".format(account_cost_message)
    sns_message += "\n"
    sns_message += "\n【Service Cost Ranking】"
    sns_message += "\n{}".format(service_cost_message)

    # メール送信
    log.debug("SNS メール送信 本文 : {}.....".format(arg_service_cost_ranking_message[0]))
    log.info("SNS メール送信 件名 : {}".format(sns_subject))

    sns_topic.publish(
        Message = sns_message,
        Subject = sns_subject
    )

    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))



# ----------------------------------------------------------------------
# Entry Point (Program Start Point)
# ----------------------------------------------------------------------
def lambda_handler_entrypoint(event, context):

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    try:
        main()

    except ClientError as e:
        # Error handling for AWS API
        error_message = e.response['Error']['Message']
        log.error("An error occurred with the AWS API.")
        log.error(error_message, exc_info=True)

    except BotoCoreError as e:
        # Error handling for boto3 SDK
        error_message = str(e)
        log.error("An error occurred with the boto3 library.")
        log.error(error_message, exc_info=True)

    except Exception as e:
        # Error handling for other unexpected errors
        error_message = str(e)
        log.error("An unexpected error occurred. There may be a syntax error in the code.")
        log.error(error_message, exc_info=True)

    finally:
        log.debug("{}() Process end".format(sys._getframe().f_code.co_name))
        log.info('Processing completed successfully')