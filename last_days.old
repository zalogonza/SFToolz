import os
import subprocess
from simple_salesforce import Salesforce
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime, timedelta
from collections import defaultdict

# Define the path to the .env file in the $HOME/.sfdc directory
HOME = os.path.expanduser("~")
SFD_ENV_DIR = os.path.join(HOME, ".sfdc")
SFD_ENV_FILE = os.path.join(SFD_ENV_DIR, ".env")

# Function to load environment variables from the .env file in $HOME/.sfdc
def load_env_vars():
    if os.path.exists(SFD_ENV_FILE):
        print("Loading environment variables from .env file in $HOME/.sfdc...")
        with open(SFD_ENV_FILE) as env_file:
            for line in env_file:
                if line.strip():
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    else:
        print(".env file not found, invoking sfdc_login.py to perform login...")
        perform_login()

# Function to invoke sfdc_login.py if credentials are missing or expired
def perform_login():
    subprocess.run(["python3", os.path.join(HOME, "sfdc_login.py")])
    load_env_vars()

# Function to authenticate and connect to Salesforce using OAuth token
def connect_to_salesforce():
    try:
        access_token = os.getenv('SF_ACCESS_TOKEN')
        instance_url = os.getenv('SF_INSTANCE_URL')

        # Check if the token or instance URL is missing
        if not access_token or not instance_url:
            print("Salesforce credentials missing, invoking login...")
            perform_login()
            access_token = os.getenv('SF_ACCESS_TOKEN')
            instance_url = os.getenv('SF_INSTANCE_URL')

        # Connect to Salesforce
        sf = Salesforce(instance_url=instance_url, session_id=access_token)
        print("Connected to Salesforce successfully!")
        return sf
    except Exception as e:
        print(f"Error connecting to Salesforce: {e}")
        return None

# Function to retrieve opportunities closing this quarter
def get_opportunities_from_sfdc(sf):
    # Calculate the start and end dates for the current quarter
    quarter, year = get_current_quarter()
    if quarter == 'Q1':
        start_date = f'{year}-01-01'
        end_date = f'{year}-03-31'
    elif quarter == 'Q2':
        start_date = f'{year}-04-01'
        end_date = f'{year}-06-30'
    elif quarter == 'Q3':
        start_date = f'{year}-07-01'
        end_date = f'{year}-09-30'
    else:
        start_date = f'{year}-10-01'
        end_date = f'{year}-12-31'

    # SOQL query to get opportunities closing in the current quarter
    query = f"""
    SELECT Name, Amount, CloseDate, ForecastCategoryName, Owner_Area__c, Distributor__c
    FROM Opportunity
    WHERE CloseDate >= {start_date} AND CloseDate <= {end_date}
    ORDER BY CloseDate ASC
    """

    try:
        # Execute the SOQL query
        opportunities = sf.query(query)['records']
        print(f"Retrieved {len(opportunities)} opportunities from Salesforce.")
        return opportunities
    except Exception as e:
        print(f"Error retrieving opportunities: {e}")
        return []

# Function to determine the current quarter
def get_current_quarter():
    today = datetime.today()
    year = today.year

    if today.month in [1, 2, 3]:
        return 'Q1', year
    elif today.month in [4, 5, 6]:
        return 'Q2', year
    elif today.month in [7, 8, 9]:
        return 'Q3', year
    else:
        return 'Q4', year

# Function to distribute opportunity amounts evenly across the week
def distribute_amount(amount, confidence_factor):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    daily_amount = (amount * confidence_factor) / len(days)
    return {day: daily_amount for day in days}

# Function to process opportunities and generate the required output
def process_opportunities(opportunities):
    weekly_data = defaultdict(lambda: defaultdict(float))
    distributor_data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    # Iterate through opportunities and distribute amounts by day
    for opp in opportunities:
        area = opp['Owner_Area__c']
        distributor = opp.get('Distributor__c', 'Unknown Distributor')  # Use 'Unknown Distributor' if missing
        name = opp['Name']
        forecast = opp['ForecastCategoryName']
        amount = opp['Amount'] if opp['Amount'] is not None else 0  # Handle None values for Amount
        close_date = datetime.strptime(opp['CloseDate'], "%Y-%m-%d")
        week_number = close_date.isocalendar()[1]  # ISO week number

        # Confidence factor: 0.7 for Commit, 0.3 for Best Case
        if forecast == 'Commit':
            confidence_factor = 0.7
        elif forecast == 'Best Case':
            confidence_factor = 0.3
        else:
            confidence_factor = 0

        # If opportunity is under $100,000, group it into "All Other"
        if amount < 100000:
            if forecast == 'Commit':
                name = 'All the Rest Commit'
            else:
                name = 'All the Rest Best Case'

        daily_distribution = distribute_amount(amount, confidence_factor)

        # Sum daily amounts and store them per week and day
        for day, daily_amount in daily_distribution.items():
            weekly_data[week_number][day] += daily_amount
            distributor_data[week_number][distributor][day] += daily_amount

        # Store the weekly totals
        weekly_data[week_number]['Total'] += amount
        distributor_data[week_number][distributor]['Total'] += amount

    return weekly_data, distributor_data

# Function to generate or update the Excel file
def generate_excel(weekly_data, distributor_data):
    # Determine the filename based on the quarter
    quarter, year = get_current_quarter()
    filename = f'Sales_Closing_Q{quarter}_{year}.xlsx'

    try:
        # Try to load the workbook if it exists
        if os.path.exists(filename):
            workbook = load_workbook(filename)
            writer = pd.ExcelWriter(filename, engine='openpyxl')
            writer.book = workbook
            writer.sheets = dict((ws.title, ws) for ws in workbook.worksheets)
        else:
            # Create a new writer if the file doesn't exist
            writer = pd.ExcelWriter(filename, engine='openpyxl')

    except Exception as e:
        print(f"Error loading workbook: {e}")
        print("Creating a new workbook.")
        writer = pd.ExcelWriter(filename, engine='openpyxl')

    # Add a new worksheet with the current date
    today_str = datetime.today().strftime('%Y-%m-%d')
    if today_str in writer.sheets:
        sheet_name = f"{today_str}_Update"
    else:
        sheet_name = today_str

    # Prepare DataFrame to write to Excel
    data = []
    for week, days in weekly_data.items():
        row = [f"Week {week}"]
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Total']:
            row.append(days[day])
        data.append(row)

    df = pd.DataFrame(data, columns=['Week', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Total'])

    # Write data to the new sheet
    df.to_excel(writer, sheet_name=sheet_name, index=False)

    # Write distributor data per week
    for week, dist_data in distributor_data.items():
        dist_sheet_name = f"Week_{week}_Distributors"
        dist_data_list = []
        for distributor, dist_days in dist_data.items():
            row = [distributor]
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Total']:
                row.append(dist_days[day])
            dist_data_list.append(row)

        df_dist = pd.DataFrame(dist_data_list, columns=['Distributor', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Total'])
        df_dist.to_excel(writer, sheet_name=dist_sheet_name, index=False)

    # Save the workbook
    writer._save()
    print(f"Data written to {sheet_name} and distributor sheets in {filename}")

# Main flow
if __name__ == "__main__":
    # Load environment variables and connect to Salesforce
    load_env_vars()
    sf = connect_to_salesforce()

    # Retrieve opportunities and proceed with data processing
    if sf:
        opportunities = get_opportunities_from_sfdc(sf)
        weekly_data, distributor_data = process_opportunities(opportunities)
        generate_excel(weekly_data, distributor_data)

