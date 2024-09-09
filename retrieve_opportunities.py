import os
import subprocess
from simple_salesforce import Salesforce
from datetime import datetime, timedelta
import json

# Function to set environment variables if not set
def set_env_vars():
    if not os.getenv('SF_USERNAME'):
        print("Environment variable SF_USERNAME not set.")
        os.environ['SF_USERNAME'] = input("Enter Salesforce username (for SSO): ")

    if not os.getenv('SF_LOGIN_URL'):
        print("Environment variable SF_LOGIN_URL not set.")
        os.environ['SF_LOGIN_URL'] = input("Enter your Salesforce custom domain URL (e.g., https://yourdomain.my.salesforce.com): ")

# Function to perform SSO login using sfdx and retrieve the access token and instance URL
def sso_login():
    try:
        # Call sfdx for SSO login via web
        print("Initiating SSO login with Salesforce...")
        subprocess.run(["sfdx", "auth:web:login", "--setdefaultusername"], check=True)
        print("SSO login successful and default username set.")
        
        # Retrieve the OAuth access token and instance URL using sfdx
        result = subprocess.run(["sfdx", "force:org:display", "--json"], capture_output=True, check=True)
        result_json = json.loads(result.stdout)
        
        access_token = result_json['result']['accessToken']
        instance_url = result_json['result']['instanceUrl']
        return access_token, instance_url
    except subprocess.CalledProcessError as e:
        print(f"Error during SSO login or retrieving access token: {e}")
        return None, None

# Function to authenticate and connect to Salesforce using OAuth token
def connect_to_salesforce(access_token, instance_url):
    try:
        # Connect to Salesforce using the access token and instance URL
        sf = Salesforce(instance_url=instance_url, session_id=access_token)
        print("Connected to Salesforce successfully!")
        return sf
    except Exception as e:
        print(f"Error connecting to Salesforce: {e}")
        return None

# Function to retrieve opportunities closing this week and next week
def get_opportunities_closing_soon(sf):
    try:
        # Define date ranges for this week and next week
        today = datetime.today()
        start_of_this_week = today - timedelta(days=today.weekday())
        start_of_next_week = start_of_this_week + timedelta(days=7)
        end_of_next_week = start_of_next_week + timedelta(days=6)

        # Convert the dates to Salesforce Date format (YYYY-MM-DD)
        start_of_this_week_str = start_of_this_week.strftime('%Y-%m-%d')
        end_of_next_week_str = end_of_next_week.strftime('%Y-%m-%d')

        # SOQL query to retrieve opportunities closing this week and next week
        query = f"""
        SELECT Id, Name, StageName, CloseDate, Amount
        FROM Opportunity
        WHERE CloseDate >= {start_of_this_week_str} AND CloseDate <= {end_of_next_week_str}
        ORDER BY CloseDate ASC
        """

        # Execute the SOQL query
        opportunities = sf.query(query)

        if opportunities['totalSize'] > 0:
            print(f"Found {opportunities['totalSize']} opportunities closing this week and next week:")
            for opp in opportunities['records']:
                print(f"Opportunity Name: {opp['Name']}, Stage: {opp['StageName']}, Close Date: {opp['CloseDate']}, Amount: {opp['Amount']}")
        else:
            print("No opportunities found closing this week or next week.")

    except Exception as e:
        print(f"Error retrieving opportunities: {e}")

# Main function
if __name__ == "__main__":
    # Step 1: Set environment variables if they are not set
    set_env_vars()

    # Step 2: Perform SSO login and retrieve access token
    access_token, instance_url = sso_login()

    if not access_token or not instance_url:
        print("Failed to retrieve access token or instance URL. Exiting.")
        exit(1)

    # Step 3: Connect to Salesforce using access token
    sf = connect_to_salesforce(access_token, instance_url)

    # Step 4: Retrieve opportunities closing this week and next week
    if sf:
        get_opportunities_closing_soon(sf)

