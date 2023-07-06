from dk_api import DigiKeyAPI, DKPart
from inventree_manager import InvenTreeManager
from inventree.api import InvenTreeAPI
from dk_api import DigiKeyAPI, DKPart
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

# Create API objects
load_dotenv()
VERCEL_URL = "https://oauth-callback.vercel.app/api/"
DK_AUTHORIZE = "https://api.digikey.com/v1/oauth2/authorize"
API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
OAUTH_STATE = os.getenv("OAUTH_STATE")
INVENTREE_ADDRESS = os.getenv("INVENTREE_ADDRESS")
INVENTREE_USERNAME = os.getenv("INVENTREE_USERNAME")
INVENTREE_PASSWORD = os.getenv("INVENTREE_PASSWORD")
invapi = InvenTreeAPI(
    INVENTREE_ADDRESS, username=INVENTREE_USERNAME, password=INVENTREE_PASSWORD
)
dkapi = DigiKeyAPI(API_KEY, CLIENT_ID, OAUTH_STATE)
manager = InvenTreeManager(invapi, dkapi)

# options
# 1. By Barcode
# 2. By Part Number
def pangu():
    barcode = input("Scan Barcode or enter Part Number: ")
    response = dkapi.get_product_details_from_barcode(barcode)
    this_part = DKPart(response)
    manager.check_part(this_part)
    this_part.write_labels()


if __name__ == "__main__":
    while True:
        pangu()

