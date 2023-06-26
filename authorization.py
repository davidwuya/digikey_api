# https://developer.digikey.com/documentation/oauth
import requests
from dotenv import load_dotenv
import webbrowser
from flask import Flask, request
import os
from OpenSSL import SSL, crypto
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)
authorization_code = None
server_started = False

auth_endpoint = "https://api.digikey.com/v1/oauth2/authorize"
token_endpoint = "https://api.digikey.com/v1/oauth2/token"
redirect_uri = "https://localhost:5000/callback"
client_id = os.getenv("DK_CLIENT_ID")
client_secret = os.getenv("DK_CLIENT_SECRET")


def generate_certificate() -> bool:
    """
    Generates a self-signed SSL certificate and private key and saves them to files.

    Returns:
    bool: True if the certificate was generated successfully, False otherwise.
    """
    # Generate a private key
    private_key = crypto.PKey()
    private_key.generate_key(crypto.TYPE_RSA, 2048)

    # Create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(31536000)  # Valid for a year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(private_key)
    cert.sign(private_key, "sha256")

    # Write private key and certificate to files
    with open("key.pem", "wt") as f:
        f.write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, private_key).decode("utf-8")
        )

    with open("cert.pem", "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))

    print("Certificate generated.")
    return True


@app.route("/")
def index():
    # Build the authorization URL
    auth_url = f"{auth_endpoint}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"

    # Open the authorization url in the default web browser
    webbrowser.open(auth_url, new=2, autoraise=True)

    return "Open the authorization URL in your browser."


@app.route("/callback")
def callback():
    global authorization_code
    # Extract authorization code from the callback request
    authorization_code = request.args.get("code")

    if authorization_code:
        print(f"Authorization code: {authorization_code}")
        return f"Received authorization code: {authorization_code}"
    else:
        return "No code received. Try again."


def start_flask_app():
    """
    Starts the Flask server to handle the OAuth2 authorization flow and generates a certificate if one does not exist.
    """
    global server_started
    server_started = True
    # check for certificate, generate one if it doesn't exist
    if not os.path.isfile("cert.pem") or not os.path.isfile("key.pem"):
        generate_certificate()
    context = ("cert.pem", "key.pem")
    app.run(port=5000, ssl_context=context)


def get_authorization_code():
    """
    Starts a Flask server to handle the OAuth2 authorization flow and opens the authorization URL in the default web
    browser. Waits until the authorization code is received and returns it.

    :return: The authorization code.
    """
    global authorization_code, server_started
    # Start the server if it's not running
    if not server_started:
        start_flask_app()
        while not server_started:
            time.sleep(1)

    # Open the root URL
    webbrowser.open("https://localhost:5000", new=2, autoraise=True)

    # Wait until the authorization code is received
    while not authorization_code:
        time.sleep(1)

    return authorization_code


def get_access_token(
    authorization_code, client_id, client_secret, redirect_uri=redirect_uri
):
    """
    Requests an access token from the Digi-Key API using an authorization code.

    :param authorization_code: The authorization code received from the Digi-Key API.
    :param client_id: The client ID for the Digi-Key API.
    :param client_secret: The client secret for the Digi-Key API.
    :param redirect_uri: The redirect URI for the Digi-Key API.
    :return: A tuple containing the access token, its expiry time, the refresh token, and its expiry time.
    """
    grant_type = "authorization_code"

    # Prepare the data for the POST request
    data = {
        "code": authorization_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": grant_type,
    }

    # Make the POST request
    response = requests.post(token_endpoint, data=data)

    # Check the response
    if response.status_code == 200:
        # Parse the response JSON
        response_json = response.json()

        # Extract the access token and refresh token
        access_token = response_json.get("access_token")
        access_token_expiry = time.time() + int(response_json.get("expires_in"))
        refresh_token = response_json.get("refresh_token")
        refresh_token_expiry = time.time() + int(
            response_json.get("refresh_token_expires_in")
        )

        return access_token, access_token_expiry, refresh_token, refresh_token_expiry
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None, None, None, None


def refresh_access_token(client_id, client_secret, refresh_token) -> tuple:
    # Refreshes an access token using a refresh token.
    # Returns a tuple containing the new access token, its expiry time, the new refresh token, and its expiry time.
    # If the request fails, returns a tuple of None values.
    grant_type = "refresh_token"

    # Prepare the data for the POST request
    data = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": grant_type,
    }

    # Make the POST request
    response = requests.post(token_endpoint, data=data)

    # Check the response
    if response.status_code == 200:
        # Parse the response JSON
        response_json = response.json()

        # Extract the access token and refresh token
        access_token = response_json.get("access_token")
        access_token_expiry = time.time() + int(response_json.get("expires_in"))
        refresh_token = response_json.get("refresh_token")
        refresh_token_expiry = time.time() + int(
            response_json.get("refresh_token_expires_in")
        )

        return access_token, access_token_expiry, refresh_token, refresh_token_expiry
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None, None, None, None


def get_env_var(name, default=None):
    if os.getenv(name) is None and default is None:
        print(f"Please set the environment variable {name}.")
        exit(1)
    return os.getenv(name) or default


def set_env_vars(env_vars):
    with open(".env", "w") as f:
        for var, value in env_vars.items():
            f.write(f"{var}={value}\n")


def load_env_vars():
    DK_CLIENT_ID = get_env_var("DK_CLIENT_ID")
    DK_CLIENT_SECRET = get_env_var("DK_CLIENT_SECRET")
    DK_REFRESH_TOKEN = get_env_var("DK_REFRESH_TOKEN", "")
    DK_ACCESS_TOKEN = get_env_var("DK_ACCESS_TOKEN", "")
    DK_REFRESH_TOKEN_EXPIRY = round(float(get_env_var("DK_REFRESH_TOKEN_EXPIRY", "0")))
    DK_ACCESS_TOKEN_EXPIRY = round(float(get_env_var("DK_ACCESS_TOKEN_EXPIRY", "0")))

    return {
        "DK_CLIENT_ID": DK_CLIENT_ID,
        "DK_CLIENT_SECRET": DK_CLIENT_SECRET,
        "DK_REFRESH_TOKEN": DK_REFRESH_TOKEN,
        "DK_ACCESS_TOKEN": DK_ACCESS_TOKEN,
        "DK_REFRESH_TOKEN_EXPIRY": DK_REFRESH_TOKEN_EXPIRY,
        "DK_ACCESS_TOKEN_EXPIRY": DK_ACCESS_TOKEN_EXPIRY,
    }


def update_tokens(env_vars):
    # Updates the refresh token and access token for the Digi-Key API by obtaining a new authorization code and exchanging it for new tokens.
    # Parameters:
    # - env_vars: A dictionary containing the environment variables needed to obtain the new tokens.
    # Returns: None
    authorization_code = get_authorization_code()
    (
        access_token,
        access_token_expiry,
        refresh_token,
        refresh_token_expiry,
    ) = get_access_token(
        authorization_code, env_vars["DK_CLIENT_ID"], env_vars["DK_CLIENT_SECRET"]
    )
    env_vars.update(
        {
            "DK_REFRESH_TOKEN": refresh_token,
            "DK_ACCESS_TOKEN": access_token,
            "DK_REFRESH_TOKEN_EXPIRY": refresh_token_expiry,
            "DK_ACCESS_TOKEN_EXPIRY": access_token_expiry,
        }
    )
    set_env_vars(env_vars)


def refresh_token(env_vars):
    # Refreshes the access token for the Digi-Key API using a refresh token.
    # Parameters:
    # - env_vars: A dictionary containing the environment variables needed to refresh the token.
    # Returns: None
    access_token, access_token_expiry = refresh_access_token(
        env_vars["DK_CLIENT_ID"],
        env_vars["DK_CLIENT_SECRET"],
        env_vars["DK_REFRESH_TOKEN"],
    )
    env_vars.update(
        {"DK_ACCESS_TOKEN": access_token, "DK_ACCESS_TOKEN_EXPIRY": access_token_expiry}
    )
    set_env_vars(env_vars)
    return None

def check_token():
    """
    Checks if a valid refresh token and access token are available and refreshes the access token if it has expired.
    """
    env_vars = load_env_vars()

    if (
        not env_vars["DK_REFRESH_TOKEN"]
        or not env_vars["DK_ACCESS_TOKEN"]
        or env_vars["DK_REFRESH_TOKEN_EXPIRY"] < time.time()
    ):
        print("No valid refresh token or access token found. Generating new ones...")
        update_tokens(env_vars)

    if env_vars["DK_ACCESS_TOKEN_EXPIRY"] < time.time():
        print("Access token expired. Refreshing...")
        refresh_token(env_vars)
        print("Access token refreshed.")
    return None