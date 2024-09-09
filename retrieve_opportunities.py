import os
import subprocess
from simple_salesforce import Salesforce
from datetime import datetime, timedelta
import json

# Define the path to the .env file in the $HOME/.sfdc directory
HOME = os.path.expanduser("~")
SFD_ENV_DIR = os.path.join(HOME, ".sfdc")
SFD_ENV_FILE = os.path.join(SFD_ENV_DIR, ".env")

# Ensure that the $HOME/.sfdc directory exists
os.makedirs(SFD_ENV_DIR, exist_ok=True)

# Function to load environment variables from the .env file in $HOME/.sfdc
def load_env_vars():
    if os.path.exists(SFD_ENV_FILE):
        print("Loading environment variables from .env file in $HOME/.sfdc...")
        with open(SFD_ENV_FILE) as env_file:
            for line in env_file:
                if line.strip():
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

# Function to save environment variables to the .env file in $HOME/.sfdc
def save_env_vars():
    print("Saving environment variables to .env file in $HOME/.sfdc...")
    with open(SFD_ENV_FILE, "w") as env_file:
        env_file.write(f"SF_USERNAME={os.getenv('SF_USERNAME')}\n")
        env_file.write(f"SF_LOGIN_URL={os.getenv('SF_LOGIN_URL')}\n")
        env_file.write(f"SF_ACCESS_TOKEN={os.getenv('SF_ACCESS_TOKEN')}\n")
        env_file.write(f"SF_INSTANCE_URL={os.getenv('SF_INSTANCE_URL')}\n")

# Function to delete the .env file in $HOME/.sfdc
def delete_env_file():
    if os.path.exists(SFD_ENV_FILE):
        print("Deleting .env file in $HOME/.sfdc due to expired credentials...")
        os.remove(SFD_ENV_FILE)

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
        
        os.environ['SF_ACCESS_TOKEN'] = result_json['result']['accessToken']
        os.environ['SF_INSTANCE_URL'] = result_json['result']['instanceUrl']
        
        # Save the environment variables to the .env file in $HOME/.sfdc
        save_env_vars()

        return os.environ['SF_ACCESS_TOKEN'], os.environ['SF_INSTANCE_URL']
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
    # Step 1: Load environment variables from .env file in $HOME/.sfdc if it exists
    load_env_vars()

    # Step 2: Set environment variables if they are not set
    set_env_vars()

    # Step 3: Check if access token and instance URL are already set
    access_token = os.getenv('SF_ACCESS_TOKEN')
    instance_url = os.getenv('SF_INSTANCE_URL')

    # If they are not set, perform SSO login
    if not access_token or not instance_url:
        access_token, instance_url = sso_login()

    # Step 4: Connect to Salesforce using access token
    sf = connect_to_salesforce(access_token, instance_url)

    # Step 5: If login fails, credentials are expired, delete the .env file and retry SSO login
    if not sf:
        print("Salesforce login failed. Credentials might be expired.")
        delete_env_file()

        # Retry SSO login and connect to Salesforce again
        access_token, instance_url = sso_login()
        sf = connect_to_salesforce(access_token, instance_url)

    # Step 6: Retrieve opportunities closing this week and next week
    if sf:
        get_opportunities_closing_soon(sf)

