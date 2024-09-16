import os
import json
from simple_salesforce import Salesforce
from dotenv import load_dotenv

# Load environment variables from .env file (handled by sfdc_login.py)
load_dotenv(os.path.expanduser("~/.sfdc/.env"))

# Assuming sfdc_login.py will retrieve the necessary environment variables for login
username = os.getenv("SFDC_USERNAME")
password = os.getenv("SFDC_PASSWORD")
security_token = os.getenv("SFDC_SECURITY_TOKEN")

# Authenticate to Salesforce using simple_salesforce
sf = Salesforce(username=username, password=password, security_token=security_token)

# Query to retrieve pending FTQ approval requests
ftq_query = """
SELECT Id, Name, QuoteId, Status, OwnerId, CreatedDate
FROM FTQ__c
WHERE Status = 'Pending Approval'
"""

# Execute the query
ftq_approvals = sf.query_all(ftq_query)

# If there are any pending approvals, retrieve detailed quote information
if ftq_approvals['totalSize'] > 0:
    print(f"Found {ftq_approvals['totalSize']} pending FTQ approvals.\n")
    
    for ftq in ftq_approvals['records']:
        print(f"FTQ Name: {ftq['Name']}")
        print(f"Quote ID: {ftq['QuoteId']}")
        print(f"Status: {ftq['Status']}")
        print(f"Owner ID: {ftq['OwnerId']}")
        print(f"Created Date: {ftq['CreatedDate']}")
        
        # Retrieve detailed information about the quote related to this FTQ
        quote_query = f"SELECT Id, Name, Amount, CloseDate, AccountId FROM Quote WHERE Id = '{ftq['QuoteId']}'"
        quote_details = sf.query(quote_query)
        
        if quote_details['totalSize'] > 0:
            quote = quote_details['records'][0]
            print("Quote Details:")
            print(f"  Name: {quote['Name']}")
            print(f"  Amount: {quote['Amount']}")
            print(f"  Close Date: {quote['CloseDate']}")
            print(f"  Account ID: {quote['AccountId']}\n")
        else:
            print("No quote details found for this FTQ.\n")
else:
    print("No pending FTQ approvals found.")

