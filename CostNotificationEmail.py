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

from typing import List
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

# Development Master AccountID (String type is ok)
ACCOUNT_ID = os.environ['ACCOUNT_ID']

# Budget Name
BUDGET_NAME = os.environ['BUDGET_NAME']

# ----------------------------------------------------------------
# Global Variable Definitions
# ----------------------------------------------------------------

# Settings for retry count (fixed standard) and region (Tokyo) are specified in the arguments when using client or resource API
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
client_CostExplorer = boto3.client('ce', config=config)

# ----------------------------------------------------------------------
# Logger Configuration
# ----------------------------------------------------------------------

# Obtains Logger object from LoggingClass in SandboxLoggingClass.py. Used for log output.

logger = LoggingClass(LOG_LEVEL)
log = logger.get_logger()

# Usage example
# log.info("Test")

# ----------------------------------------------------------------------
# Main Processing
# ----------------------------------------------------------------------
def main():

    # sys._getframe().f_code.co_name) becomes the function name
    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    # Get the accounts for cost aggregation
    account_list = get_account_list()

    # Get the beginning of the month required to fetch this month's cost
    start_utc_str, end_utc_str = time_processing()

    # Get cost aggregation results
    cost_data = get_cost_aggregation(account_list, start_utc_str, end_utc_str)

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
def time_processing() -> str:

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    # Beginning of the month, today's date in UTC ########### Last month for test
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
def get_cost_aggregation(arg_account_list, arg_start_utc_str, end_utc_str):

    log.debug("{}() Start processing".format(sys._getframe().f_code.co_name))

    response = client_CostExplorer.get_cost_and_usage(
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

    # Top 5 High Cost Services
    for index, service in enumerate(sorted(
            [group for group in response['ResultsByTime'][0]['Groups'] if group['Keys'][0] != 'Tax'],
            key=lambda x: float(x['Metrics']['UnblendedCost']['Amount']),
            reverse=True)[:5], start=1):
        service_name = service['Keys'][0]
        service_cost_str_float = service['Metrics']['UnblendedCost']['Amount']
        service_cost = service_cost_str_float.split('.')[0]
        unit = service['Metrics']['UnblendedCost']['Unit']

        log.debug("TOP{} {} : {} {}".format(index, service_name, service_cost, unit))

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
        log.error("An error occurred in the AWS API. There may be an error in the CloudWatch LogGroup name, SNS Topic name, or you may not have access rights.")
        log.error(error_message, exc_info=True)

    except BotoCoreError as e:
        # Error handling for the boto3 SDK itself
        error_message = str(e)
        log.error("An error occurred in the boto3 library.")
        log.error(error_message, exc_info=True)

    except Exception as e:
        # Unexpected error handling
        error_message = str(e)
        log.error("An unexpected error occurred. There may be a syntax error in the code.")
        log.error(error_message, exc_info=True)

    finally:
        log.debug("{}() End processing".format(sys._getframe().f_code.co_name))
        log.info('The processing was completed successfully')