import requests
import webbrowser
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
        api_key: str,
        client_id: str,
        oauth_state: str,
        vercel_url="https://oauth-callback.vercel.app/api/",
        dk_authorize="https://api.digikey.com/v1/oauth2/authorize",
    ):
        self.vercel_url = vercel_url
        self.dk_authorize = dk_authorize
        self.api_key = api_key
        self.client_id = client_id
        self.oauth_state = oauth_state
        self.token = None
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
        self.token = response.json()["access_token"]
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

    def product_details(self, token, dk_part_number):
        url = f"https://api.digikey.com/Search/v3/Products/{dk_part_number}"
        authorization = "Bearer " + token
        params = {
            "includes": "DigiKeyPartNumber,Manufacturer,ManufacturerPartNumber,ProductDescription,LimitedTaxonomy,PrimaryPhoto,ProductUrl,DetailedDescription"
        }
        headers = {
            "Authorization": authorization,
            "X-DIGIKEY-Client-Id": self.client_id,
            "X-DIGIKEY-Locale-Site": "US",
            "X-DIGIKEY-Locale-Language": "en",
            "X-DIGIKEY-Locale-Currency": "USD",
        }
        print("Querying Digi-Key API...")
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            return f"Error: {response.status_code} - {response.text}"

    def get_product_details_from_barcode(self, barcode, debug=False):
        oauth_token = self.get_token(debug=debug)
        try:
            dk_part_number = self.decode_barcode(barcode)
            if debug:
                print(dk_part_number)
        except:
            print("Error decoding barcode. Try with part number instead.")
            return self.product_details(oauth_token, input("DK Part Number: "))

        return self.product_details(oauth_token, dk_part_number)

    def get_product_details_from_part_number(self, part_number, debug=False):
        oauth_token = self.get_token(debug=debug)
        return self.product_details(oauth_token, part_number)


class DKPart:
    """
    A class representing a Digi-Key part.

    Attributes:
    -----------
    LimitedTaxonomy : list
        A list of categories that the part belongs to. 
    ProductUrl : str
        The URL of the product page for the part.
    PrimaryPhoto : str
        The URL of the primary photo for the part.
     : str
        A detailed description of the part.
    ManufacturerPartNumber : str
        The manufacturer part number for the part.
    DigiKeyPartNumber : str
        The Digi-Key part number for the part.
    ProductDescription : str
        A description of the part.
    Manufacturer : str
        The name of the manufacturer of the part.
    """

    def __init__(self, response: dict):
        self.LimitedTaxonomy = []
        self.ProductUrl = ""
        self.PrimaryPhoto = ""
        self.DetailedDescription = ""
        self.ManufacturerPartNumber = ""
        self.DigiKeyPartNumber = ""
        self.ProductDescription = ""
        self.Manufacturer = ""
        self.parse_response(response)

    def prettyprint(self):
        """
        Prints the part's attributes in a pretty format.

        Parameters:
        -----------
        None

        Returns:
        --------
        None
        """
        print("Digi-Key Part Number:", self.DigiKeyPartNumber)
        print("Manufacturer Part Number:", self.ManufacturerPartNumber)
        print("Manufacturer:", self.Manufacturer)
        print("Product Description:", self.ProductDescription)
        print("Limited Taxonomy:", self.LimitedTaxonomy)
        print("Detailed Description:", self.DetailedDescription)

    def split_taxonomy(self):
        # split the taxonomy into a list of categories
        # Parent category is first in list
        split_taxonomy = list(set(self.LimitedTaxonomy[0].split(' - ')))
        split_taxonomy.append(self.LimitedTaxonomy[1])
        self.LimitedTaxonomy = [split_taxonomy[-1]] + split_taxonomy[:-1][::-1]

    def extract_values(self, d: dict):
        """
        Recursively extracts relevant values from a dictionary and populates the DKPart object's attributes.

        Parameters:
        -----------
        d : dict
            The dictionary to extract values from.

        Returns:
        --------
        None
        """
        for key, value in d.items():
            if isinstance(value, dict):
                self.extract_values(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self.extract_values(item)
            elif key == "Value":
                if "Categories" in d["Parameter"]:
                    self.LimitedTaxonomy.append(value)
                elif "Manufacturer" in d["Parameter"]:
                    self.Manufacturer = value
            elif key in vars(self):
                setattr(self, key, value)
    


    def parse_response(self, response):
        """
        Parses the response from the Digi-Key API and extracts the relevant values to populate the DKPart object's attributes.

        Parameters:
        -----------
        response : dict
            The response from the Digi-Key API.

        Returns:
        --------
        None
        """
        self.extract_values(response)
        self.split_taxonomy()
