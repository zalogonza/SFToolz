import sys
import os
import subprocess
from simple_salesforce import Salesforce
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime, timedelta
from collections import defaultdict
import argparse

# Define multiplier variables
mult_commit = 0.8
mult_bestcase = 0.2
mult_else = 0

# Function to print to STDERR for debugging
def print_err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Function to parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description='Process Salesforce data and filter by area.')
    parser.add_argument('--area', type=str, required=True, help='Filter opportunities where Area contains the specified string.')
    args = parser.parse_args()
    return args.area

# Load environment variables from the .env file in $HOME/.sfdc
def load_env_vars():
    SFD_ENV_DIR = os.path.join(os.path.expanduser("~"), ".sfdc")
    SFD_ENV_FILE = os.path.join(SFD_ENV_DIR, ".env")
    
    if os.path.exists(SFD_ENV_FILE):
        print_err("Loading environment variables from .env file in $HOME/.sfdc...")
        with open(SFD_ENV_FILE) as env_file:
            for line in env_file:
                if line.strip():
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    else:
        print_err(".env file not found, invoking sfdc_login.py to perform login...")
        perform_login()

# Function to invoke sfdc_login.py if credentials are missing or expired
def perform_login():
    subprocess.run(["python3", os.path.join(os.path.expanduser("~"), "sfdc_login.py")])
    load_env_vars()

# Function to authenticate and connect to Salesforce
def connect_to_salesforce():
    try:
        access_token = os.getenv('SF_ACCESS_TOKEN')
        instance_url = os.getenv('SF_INSTANCE_URL')

        if not access_token or not instance_url:
            print_err("Salesforce credentials missing, invoking login...")
            perform_login()
            access_token = os.getenv('SF_ACCESS_TOKEN')
            instance_url = os.getenv('SF_INSTANCE_URL')

        sf = Salesforce(instance_url=instance_url, session_id=access_token)
        print_err("Connected to Salesforce successfully!")
        return sf
    except Exception as e:
        print_err(f"Error connecting to Salesforce: {e}")
        return None

# Function to calculate the current quarter's start and end dates
def get_current_quarter_dates():
    today = datetime.today()
    year = today.year
    start_of_week = today - timedelta(days=today.weekday())  # Monday of the current week

    if today.month in [1, 2, 3]:
        quarter = 'Q1'
        end_date = f'{year}-03-31'
    elif today.month in [4, 5, 6]:
        quarter = 'Q2'
        end_date = f'{year}-06-30'
    elif today.month in [7, 8, 9]:
        quarter = 'Q3'
        end_date = f'{year}-09-30'
    else:
        quarter = 'Q4'
        end_date = f'{year}-12-31'

    last_day_of_q = datetime.strptime(end_date, '%Y-%m-%d')
    return start_of_week, last_day_of_q, quarter

# Function to handle pagination and fetch all opportunities
def get_all_opportunities(sf, query):
    all_opportunities = []
    response = sf.query(query)

    # Append initial batch of records
    all_opportunities.extend(response['records'])

    # While there are more records to fetch, keep querying the next set of records
    while not response['done']:
        next_records_url = response['nextRecordsUrl']
        print_err(f"Fetching next batch of records from: {next_records_url}")
        response = sf.query_more(next_records_url, True)
        all_opportunities.extend(response['records'])

    print_err(f"Total records retrieved: {len(all_opportunities)}")
    return all_opportunities

# Function to retrieve opportunities closing this quarter
def get_opportunities_from_sfdc(sf):
    start_date, end_date, quarter = get_current_quarter_dates()
    
    # Print start and end dates to STDERR for debugging
    print_err(f"Start Date: {start_date.strftime('%Y-%m-%d')}")
    print_err(f"End Date: {end_date.strftime('%Y-%m-%d')}")
    print_err(f"Current Quarter: {quarter}")

    
    # Now you can use the 'area' variable in your SOQL query
    query = f"""
    SELECT Name, Amount, CloseDate, ForecastCategoryName, Owner_Area__c, Distributor__c, StageName, IsClosed
    FROM Opportunity
    WHERE CloseDate >= {start_date.strftime('%Y-%m-%d')} 
    AND CloseDate <= {end_date.strftime('%Y-%m-%d')}
    AND IsClosed = False
    AND Owner_Area__c LIKE '%{area}%'
    ORDER BY CloseDate ASC
    """

    # Print the query to STDERR for debugging
    print_err(f"SOQL Query: {query}")

    # Retrieve all opportunities using pagination
    opportunities = get_all_opportunities(sf, query)

    # Debug: Print each opportunity to track if 2024-09-30 is included
    for opp in opportunities:
        print_err(f"Opportunity: {opp['Name']}, CloseDate: {opp['CloseDate']}, Area: {opp['Owner_Area__c']}, Amount: {opp['Amount']}")
    
    return opportunities

# Function to distribute opportunity amounts by day of the week
def distribute_amount_by_day(amount, close_date, forecast):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily_amounts = {day: 0 for day in days}

    # Use the multipliers based on forecast type
    if forecast == 'Commit':
        multiplier = mult_commit
    elif forecast == 'Best Case':
        multiplier = mult_bestcase
    else:
        multiplier = mult_else

    adjusted_amount = amount * multiplier

    # Assign the amount to the respective day if forecast is Commit
    if forecast == 'Commit':
        weekday = close_date.weekday()  # Monday is 0, Sunday is 6
        daily_amounts[days[weekday]] = adjusted_amount
    elif forecast == 'Best Case':
        daily_amounts['Upside'] = adjusted_amount  # For non-commit opportunities, add to "Upside"

    return daily_amounts

# Process opportunities by week and area, sorted by amount (from highest to lowest)
def process_opportunities(opportunities):
    weekly_data = defaultdict(lambda: defaultdict(list))

    # Sort opportunities by amount, from highest to lowest
    opportunities = sorted(opportunities, key=lambda x: x['Amount'] if x['Amount'] is not None else 0, reverse=True)

    for opp in opportunities:
        week_number = datetime.strptime(opp['CloseDate'], "%Y-%m-%d").isocalendar()[1]
        area = opp['Owner_Area__c']
        name = opp['Name']
        amount = opp['Amount'] if opp['Amount'] is not None else 0
        forecast = opp['ForecastCategoryName']
        close_date = datetime.strptime(opp['CloseDate'], "%Y-%m-%d")

        daily_amounts = distribute_amount_by_day(amount, close_date, forecast)

        weekly_data[week_number][area].append({
            'Opportunity Name': name,
            'Amount': amount,
            'CloseDate': close_date.strftime('%Y-%m-%d'),
            'Monday': daily_amounts['Monday'],
            'Tuesday': daily_amounts['Tuesday'],
            'Wednesday': daily_amounts['Wednesday'],
            'Thursday': daily_amounts['Thursday'],
            'Friday': daily_amounts['Friday'],
            'Saturday': daily_amounts['Saturday'],
            'Sunday': daily_amounts['Sunday'],
            'Upside': daily_amounts.get('Upside', 0)
        })

    return weekly_data


# Function to generate or update the Excel file
def generate_excel(weekly_data):
    start_of_week, last_day_of_q, quarter = get_current_quarter_dates()
    year = datetime.today().year
    filename = os.path.join(os.path.expanduser("~"), "Documents", f'Sales_Closing_Q{quarter}_{year}.xlsx')

    try:
        writer = pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') if os.path.exists(filename) else pd.ExcelWriter(filename, engine='openpyxl')
    except Exception as e:
        writer = pd.ExcelWriter(filename, engine='openpyxl')
    
    for week_number, areas in weekly_data.items():
        sheet_name = f"{datetime.today().strftime('%Y-%m-%d-%H')}"
        data = []

        for area, opportunities in areas.items():
            for opp in opportunities:
                row = [
                    week_number,
                    area,
                    opp['Opportunity Name'],
                    opp['Amount'],
                    opp['CloseDate'],
                    opp['Monday'],
                    opp['Tuesday'],
                    opp['Wednesday'],
                    opp['Thursday'],
                    opp['Friday'],
                    opp['Saturday'],
                    opp['Sunday'],
                    opp['Upside']
                ] 
                data.append(row)

        df = pd.DataFrame(data, columns=[
            'Week Number', 'Area', 'Opportunity Name', 'Amount', 'CloseDate', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'Upside'
        ])
        df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=writer.sheets[sheet_name].max_row if sheet_name in writer.sheets else 0, header=not writer.sheets)

    writer.close()  # Use close() instead of save()


# Main execution
if __name__ == "__main__":
    load_env_vars()
    sf = connect_to_salesforce()
    area = parse_arguments()
    if sf:
        opportunities = get_opportunities_from_sfdc(sf)
        weekly_data = process_opportunities(opportunities)
        generate_excel(weekly_data)


