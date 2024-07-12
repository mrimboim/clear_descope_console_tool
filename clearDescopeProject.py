import os
import sys
import requests
import time
import json
from dotenv import load_dotenv

from descope import (
    AuthException,
    DescopeClient,
    AssociatedTenant,
    RoleMapping,
    AttributeMapping,
    UserPassword,
    UserPasswordBcrypt,
    UserObj
)

load_dotenv()
DESCOPE_PROJECT_ID = os.getenv("DESCOPE_PROJECT_ID")
DESCOPE_MANAGEMENT_KEY = os.getenv("DESCOPE_MANAGMENT_KEY")

try:
    descope_client = DescopeClient(
        project_id=DESCOPE_PROJECT_ID, management_key=DESCOPE_MANAGEMENT_KEY
    )
except AuthException as error:
    print(f"Failed to initialize Descope Client: {error}")
    sys.exit()

def api_request_with_retry(action, url, headers, data=None, max_retries=4, timeout=10):
    """
    Handles API requests with additional retry on timeout and rate limit.

    Args:
    - action (string): 'get' or 'post'
    - url (string): The URL of the path for the api request
    - headers (dict): Headers to be sent with the request
    - data (json): Optional and used only for post, but the payload to post
    - max_retries (int): The max number of retries
    - timeout (int): The timeout for the request in seconds
    Returns:
    - API Response
    - Or None
    """
    retries = 0
    while retries < max_retries:
        try:
            if action == "get":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(
                    url, headers=headers, data=data, timeout=timeout
                )

            if (
                response.status_code != 429
            ):  # Not a rate limit error, proceed with response
                return response

            # If rate limit error, prepare for retry
            retries += 1
            wait_time = 5**retries
            print(f"Rate limit reached. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

        except requests.exceptions.ReadTimeout as e:
            # Handle read timeout exception
            print(f"Read timed out. (read timeout={timeout}): {e}")
            retries += 1
            wait_time = 5**retries
            print(f"Retrying attempt {retries}/{max_retries}...")
            time.sleep(
                wait_time
            )  # Wait for 5 seconds before retrying or use a backoff strategy

        except requests.exceptions.RequestException as e:
            # Handle other request exceptions
            print(f"A request exception occurred: {e}")
            break  # In case of other exceptions, you may want to break the loop

    print("Max retries reached. Giving up.")
    return None


def main():

    # Clearing Users
    users_resp = descope_client.mgmt.user.search_all()
    users = users_resp["users"]
    print(f"Deleting {len(users)} users:")
    count = 0
    for user in users:
        descope_client.mgmt.user.delete(user["loginIds"][0])
        count += 1
        if not (count % 10):
            print(f"\tDeleted {count} users")
    
    # Clearing User Custom attributes
    #   getting user custom attributes
    headers = {"Authorization": f"Bearer {DESCOPE_PROJECT_ID}:{DESCOPE_MANAGEMENT_KEY}"}
    response = api_request_with_retry(
        "get",
        f"https://api.descope.com/v1/mgmt/user/customattributes",
        headers=headers,
    )
    if response.status_code != 200:
        print(
            f"Error fetching Getting user custom attribute. Status code: {response.status_code}"
        )
    attrs = response.json()

    print(f"Deleting {len(attrs['data'])} custom user attributes:")

    count = 0
    attr_name_list = []
    for attr in attrs['data']:
        attr_name_list.append(attr['name'])

    #   deleting user custom attributes
    response = api_request_with_retry(
        "post",
        f"https://api.descope.com/v1/mgmt/user/customattribute/delete",
        headers={
            "Authorization": f"Bearer {DESCOPE_PROJECT_ID}:{DESCOPE_MANAGEMENT_KEY}",
            "Content-Type": "application/json"
        },
        data=json.dumps({"names": attr_name_list})
    )
    
    # Clearing Tenants
    tenants_resp = descope_client.mgmt.tenant.load_all()
    tenants = tenants_resp["tenants"]
    print(f"Deleting {len(tenants)} tenants")
    for tenant in tenants:
        descope_client.mgmt.tenant.delete(id=tenant["id"])

    # Clear permissions

    permissions_resp = descope_client.mgmt.permission.load_all()
    permissions = permissions_resp["permissions"]
    print(f"Deleting {len(permissions)} roles")
    roles_name_list = []
    for permission in permissions:
        descope_client.mgmt.permission.delete(permission["name"])

    # Clear roles
    roles_resp = descope_client.mgmt.role.load_all()
    roles = roles_resp["roles"]
    print(f"Deleting {len(roles)} roles")
    for role in roles:
        descope_client.mgmt.role.delete(role["name"])
    

  







if __name__ == "__main__":
    main()