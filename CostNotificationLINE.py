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
    Python for aggregating the cost of the current month for the accounts set in the AWS Budgets filter, and sending it via LINE
▼Remarks
    Need to set linked accounts in the filter for Budgets
"""

import datetime
import os
import sys
import boto3
import urllib.request
import urllib.parse

from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config
from LoggingClass import LoggingClass



# ----------------------------------------------------------------------
# Constant Definitions
# ----------------------------------------------------------------------

try:

    # Time zones UTC
    UTC = ZoneInfo("UTC")

    # Log Level (default is INFO)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # Retry count when using client or resource API
    RETRY_COUNT = int(os.environ.get('RETRY_COUNT', 3))

    # Master AccountID (String Type)
    ACCOUNT_ID = os.environ['ACCOUNT_ID']

    # Budget Name
    BUDGET_NAME = os.environ['BUDGET_NAME']

    # LINE Notify Token
    LINE_NOTIFY_TOKEN = os.environ['LINE_NOTIFY_TOKEN']

except KeyError as e:
    raise Exception("Required environment variable not set : {}".format(e))



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

# Budgets API settings
client_budgets = boto3.client('budgets', config=config)
# Cost Explorer API settings
client_cost_explorer = boto3.client('ce', config=config)
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

    # Get the accountIDs for cost aggregation
    account_list = get_account_list()

    # Get today and the beginning of the month required to fetch this month's cost
    # The cost is the sum of expenses from the beginning of the month until today
    start_utc_str, end_utc_str = time_processing()

    # Get account names
    account_name_dict = get_account_name(account_list)

    # Get cost ranking
    service_cost_ranking_message = get_service_cost_ranking(account_list, start_utc_str, end_utc_str)
    total_cost, account_cost_ranking_message = get_account_cost_ranking(account_name_dict, start_utc_str, end_utc_str)

    # Send cost ranking
    send_line(start_utc_str, service_cost_ranking_message, total_cost, account_cost_ranking_message)

    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))



# ----------------------------------------------------------------------
# Get AccountIDs
# ----------------------------------------------------------------------
def get_account_list() -> List[str]:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    account_list = []

    response = client_budgets.describe_budget(
        AccountId=ACCOUNT_ID,
        BudgetName=BUDGET_NAME
    )

    # Get AccountIDs set in Budget's filter
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

    # Beginning of the month, today's date in UTC
    now = datetime.datetime.now(UTC)
    start_utc = datetime.datetime(now.year, now.month, 1)
    start_utc_str = start_utc.strftime('%Y-%m-%d')
    end_utc_str = now.strftime('%Y-%m-%d')

    log.debug("UTC Beginning of the month (str) : {}".format(start_utc_str))
    log.debug("UTC Today (str) : {}".format(end_utc_str))
    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))

    return start_utc_str, end_utc_str



# ----------------------------------------------------------------------
# Get Account Names
# ----------------------------------------------------------------------
def get_account_name(arg_account_list: List[str]) -> Dict[str, str]:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    account_name_dict = {}

    # Get the Account Names corresponding to the AccountID obtained from Budgets using AWS Organizations
    paginator = client_organizations.get_paginator('list_accounts')
    for page in paginator.paginate():
        for account in page['Accounts']:
            for accountId in arg_account_list:
                if account['Id'] == accountId:
                    account_name_dict[account['Id']] = account['Name']

    log.debug("Account Names : {}".format(','.join(account_name_dict.values())))
    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))

    return account_name_dict



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

    service_cost_ranking_message = []

    """
    ・sorted(iterable, key=None, reverse=False)[:5]
    Taking five from the sorted list by the slice

    ・[Processing Result for Element in Iterable if Condition]
    Using list comprehension, a new list is created.
    Create a List excluding taxes
    1. Iterating through the elements of an iterable (such as a list, dictionary, tuple, or any other iterable object) using a for loop,
    2. Checking the elements against a conditional expression using an if statement,
    3. Including only the elements that satisfy the condition in the new list.

    ・key=lambda x: float(x['Metrics']['UnblendedCost']['Amount'])
    By combining the sorted function with lambda, you can sort the elements in a list based on any key
    """

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
# Get Account Cost Ranking & Total Cost
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


    # Top 3 High Cost Accounts
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

        log.debug(message)


    # Get the total cost of accounts taken from Budgets
    total_cost_float = 0.0

    for group in response['ResultsByTime'][0]['Groups']:
        total_cost_float += float(group['Metrics']['UnblendedCost']['Amount'])

    total_cost = str(total_cost_float).split('.')[0] + unit

    log.debug("Total Cost : {}".format(total_cost))
    log.debug("{}() End processing".format(sys._getframe().f_code.co_name))


    return total_cost, account_cost_ranking_message



# ----------------------------------------------------------------------
# Send LINE
# ----------------------------------------------------------------------
def send_line(arg_start_utc_str, arg_service_cost_ranking_message, arg_total_cost, arg_account_cost_ranking_message) -> None:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    # Create message
    service_cost_message = '\n'.join(arg_service_cost_ranking_message)
    account_cost_message = '\n'.join(arg_account_cost_ranking_message)

    line_message = """{}
【Total Cost】
{}

【Account Cost Ranking】
{}

【Service Cost Ranking】
{}""".format(arg_start_utc_str[:-3], arg_total_cost, account_cost_message, service_cost_message)

    # LINE Notify API URL
    url = "https://notify-api.line.me/api/notify"

    # Send LINE
    headers = {
        'Authorization': 'Bearer ' + LINE_NOTIFY_TOKEN,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'message': line_message}
    encoded_data = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as res:
            response_body = res.read().decode('utf-8')
            log.info("LINE Notify Response: {}".format(response_body))

    except urllib.error.HTTPError as err:
        log.error("HTTP error occurred: {}".format(err.code))
    except Exception as err:
        log.error("An error occurred: {}".format(err))

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
        log.debug("{}() End processing".format(sys._getframe().f_code.co_name))
        log.info('Processing completed successfully')