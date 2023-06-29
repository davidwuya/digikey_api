import requests
import webbrowser
import time
import re
import os
from dotenv import load_dotenv

load_dotenv()

# env variables
VERCEL_URL = "https://oauth-callback.vercel.app/api/"
DK_AUTHORIZE = "https://api.digikey.com/v1/oauth2/authorize"
API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
OAUTH_STATE = os.getenv("OAUTH_STATE")

class DigiKeyAPI:
    def __init__(
        self,
        api_key,
        client_id,
        oauth_state,
        vercel_url="https://oauth-callback.vercel.app/api/",
        dk_authorize="https://api.digikey.com/v1/oauth2/authorize",
    ):
        self.vercel_url = vercel_url
        self.dk_authorize = dk_authorize
        self.api_key = api_key
        self.client_id = client_id
        self.oauth_state = oauth_state
        try:
            assert self.api_key and self.client_id and self.oauth_state
        except AssertionError:
            print(self.api_key, self.client_id, self.oauth_state)
            print("Missing API Key, Client ID, or OAuth State")
            exit(1)

    def oauth_authorize(self, debug=False):
        redirect_uri = self.vercel_url + "callback"
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": self.oauth_state,
        }
        url = requests.Request("GET", self.dk_authorize, params=params).prepare().url
        if debug:
            print(url)
        if url:
            webbrowser.open(url)
            return True
        else:
            return None

    def verify_token(self, debug=False):
        response = requests.get(
            self.vercel_url + "verify", headers={"x-api-key": self.api_key}
        )
        if debug:
            print(response.json())
        return response.status_code

    def get_token(self, verify=False, debug=False):
        if verify:
            assert self.verify_token() == 200
        response = requests.get(
            self.vercel_url + "token", headers={"x-api-key": self.api_key}
        )
        return response.json()["access_token"] if not debug else response.json()

    @staticmethod
    def decode_barcode(barcode: str, type="DK"):
        dk_part_number = re.search(r"\$P(.*?)\$1P", barcode)
        if dk_part_number:
            dk_part_number = dk_part_number.group(1)

        mfr_part_number = re.search(r"\$1P(.*?)\$KGW", barcode)
        if mfr_part_number:
            mfr_part_number = mfr_part_number.group(1)

        if mfr_part_number and mfr_part_number.startswith("1P"):
            mfr_part_number = mfr_part_number[2:]

        if type == "DK":
            return dk_part_number
        elif type == "MFR":
            return mfr_part_number
        else:
            return None

    def product_details(self, oauth_token, dk_part_number):
        url = f"https://api.digikey.com/Search/v3/Products/{dk_part_number}"
        authorization = "Bearer " + oauth_token
        params = {
            "includes": "DigiKeyPartNumber,Manufacturer,ManufacturerPartNumber,ProductDescription"
        }
        headers = {
            "Authorization": authorization,
            "X-DIGIKEY-Client-Id": self.client_id,
            "X-DIGIKEY-Locale-Site": "US",
            "X-DIGIKEY-Locale-Language": "en",
            "X-DIGIKEY-Locale-Currency": "USD",
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            return f"Error: {response.status_code} - {response.text}"

    def get_product_details(self, barcode, debug=False):
        oauth_token = self.get_token(debug=debug)
        dk_part_number = self.decode_barcode(barcode)
        if debug:
            print(dk_part_number)
        return self.product_details(oauth_token, dk_part_number)
    
# api = DigiKeyAPI(API_KEY, CLIENT_ID, OAUTH_STATE)
# print(api.get_product_details(input("Barcode: ")))

class DigiKeyPart:
    def __init__(self, api_value):
        self.name = None
        self.supplier = "Digi-Key"
        self.dk_part_num = None
        self.mfg_part_num = None
        self.manufacturer = None
        self.description = None
        self.link = None
        self.price_breaks = []
        self.raw_value = api_value
        self.parameters = []
        self.picture = None
        self.thumbnail = None
    
    def __str__(self):
        return self.name