# A Digi-Key API - InvenTree Wrapper
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
## Overview
This is a Python-based application designed to interact with the Digi-Key API and the InvenTree API to manage parts in an InvenTree inventory system. The application scans DigiKey parts by barcode, retrieves details about these parts from the DigiKey API, and manages these parts in an InvenTree inventory system.

## Environment Variables
Several environment variables must be set.
* `CLIENT_ID`: Digi-Key API Client ID.
* `API_KEY`: The API key for authenticating with our own OAuth backend, implemented [here](https://github.com/davidwuya/oauth-callback). Ideally it should be a long random string matching with the backend.
* `OAUTH_STATE`: The OAuth state to use with our own OAuth backend. Should be a random string and matching with that of the backend.
* `INVENTREE_ADDRESS`: IP address or domain name for the InvenTree system.
* `INVENTREE_USERNAME`: InvenTree username with editing privledges.
* `INVENTREE_PASSWORD`: InvenTree password.

## Usage
To run the program, execute the ``main.py`` script, then follow the prompts to scan barcodes and manage the parts in your inventory.
