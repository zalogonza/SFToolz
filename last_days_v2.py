import sys
import os
import subprocess
from simple_salesforce import Salesforce
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime, timedelta
from collections import defaultdict

# Define multiplier variables
mult_commit = 0.7
mult_bestcase = 0.3
mult_else = 0

# Load environment variables from the .env file in $HOME/.sfdc
def load_env_vars():
    SFD_ENV_DIR = os.path.join(os.path.expanduser("~"), ".sfdc")
    SFD_ENV_FILE = os.path.join(SFD_ENV_DIR, ".env")
    
    if os.path.exists(SFD_ENV_FILE):
        with open(SFD_ENV_FILE) as env_file:
            for line in env_file:
                if line.strip():
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    else:
        perform_login()

# Perform login using sfdc_login.py
def perform_login():
    subprocess.run(["python3", os.path.join(os.path.expanduser("~"), "sfdc_login.py")])
    load_env_vars()

# Connect to Salesforce
def connect_to_salesforce():
    access_token = os.getenv('SF_ACCESS_TOKEN')
    instance_url = os.getenv('SF_INSTANCE_URL')

    if not access_token or not instance_url:
        perform_login()
        access_token = os.getenv('SF_ACCESS_TOKEN')
        instance_url = os.getenv('SF_INSTANCE_URL')

    sf = Salesforce(instance_url=instance_url, session_id=access_token)
    return sf

# Get the current quarter's start and end dates
def get_current_quarter_dates():
    today = datetime.today()
    year = today.year
    start_of_week = today - timedelta(days=today.weekday())  # Monday of the current week

    if today.month in [1, 2, 3]:
        end_date = f'{year}-03-31'
    elif today.month in [4, 5, 6]:
        end_date = f'{year}-06-30'
    elif today.month in [7, 8, 9]:
        end_date = f'{year}-09-30'
    else:
        end_date = f'{year}-12-31'

    last_day_of_q = datetime.strptime(end_date, '%Y-%m-%d')
    return start_of_week, last_day_of_q

# Retrieve all opportunities with pagination
def get_all_opportunities(sf, query):
    all_opportunities = []
    response = sf.query(query)
    all_opportunities.extend(response['records'])

    while not response['done']:
        next_records_url = response['nextRecordsUrl']
        response = sf.query_more(next_records_url, True)
        all_opportunities.extend(response['records'])

    return all_opportunities

# Retrieve opportunities closing this quarter
def get_opportunities_from_sfdc(sf):
    start_date, end_date = get_current_quarter_dates()

    query = f"""
    SELECT Name, Amount, CloseDate, ForecastCategoryName, Owner_Area__c, Distributor__c, StageName, IsClosed
    FROM Opportunity
    WHERE CloseDate >= {start_date.strftime('%Y-%m-%d')} AND CloseDate <= {end_date.strftime('%Y-%m-%d')}
    AND IsClosed = False
    ORDER BY CloseDate ASC
    """
    
    return get_all_opportunities(sf, query)

# Distribute opportunity amounts by day of the week
def distribute_amount_by_day(amount, close_date, forecast):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily_amounts = {day: 0 for day in days}

    multiplier = mult_commit if forecast == 'Commit' else mult_bestcase if forecast == 'Best Case' else mult_else
    adjusted_amount = amount * multiplier

    if forecast == 'Commit':
        weekday = close_date.weekday()  # Monday is 0, Sunday is 6
        daily_amounts[days[weekday]] = adjusted_amount
    elif forecast == 'Best Case':
        daily_amounts['Upside'] = adjusted_amount

    return daily_amounts

# Process opportunities by week and area
def process_opportunities(opportunities):
    weekly_data = defaultdict(lambda: defaultdict(list))

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

# Generate or update the Excel file
def generate_excel(weekly_data):
    quarter, year = get_current_quarter_dates()[2]  # Only get the quarter value
    filename = os.path.join(os.path.expanduser("~"), "Documents", f'Sales_Closing_Q{quarter}_{year}.xlsx')

    try:
        writer = pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') if os.path.exists(filename) else pd.ExcelWriter(filename, engine='openpyxl')
    except Exception as e:
        writer = pd.ExcelWriter(filename, engine='openpyxl')

    for week_number, areas in weekly_data.items():
        sheet_name = f"Week_{week_number}_{datetime.today().strftime('%Y-%m-%d')}"
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
        df.to_excel(writer, sheet_name=sheet_name, index=False)

    writer.save()

# Main execution
if __name__ == "__main__":
    load_env_vars()
    sf = connect_to_salesforce()

    if sf:
        opportunities = get_opportunities_from_sfdc(sf)
        weekly_data = process_opportunities(opportunities)
        generate_excel(weekly_data)

