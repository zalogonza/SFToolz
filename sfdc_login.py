import os
import subprocess
import json

# Define the path to the .env file in the $HOME/.sfdc directory
HOME = os.path.expanduser("~")
SFD_ENV_DIR = os.path.join(HOME, ".sfdc")
SFD_ENV_FILE = os.path.join(SFD_ENV_DIR, ".env")

# Ensure that the $HOME/.sfdc directory exists
os.makedirs(SFD_ENV_DIR, exist_ok=True)

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

# Main execution
if __name__ == "__main__":
    sso_login()

