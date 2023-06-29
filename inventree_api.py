from inventree.api import InvenTreeAPI
from inventree.company import SupplierPart, Company, ManufacturerPart
from inventree.part import Part, PartCategory
from inventree.stock import StockItem, StockLocation

INVENTREE_API_URL = ""
USERNAME = ""
PASSWORD = ""

API = InvenTreeAPI(INVENTREE_API_URL, username=USERNAME, password=PASSWORD)

ManufacturerPart.create(API, {
    'part': 1,
    'manufacturer': 1,
    'MPN': 'MPN-1234',
    'link': 'https://www.google.com',
    'description': 'Test MPN',
    'active': True,
    'approved': True,
    'note': 'Test note',
    'internal_part': False,
    'minimum_order_quantity': 1,
    'multiple_order_quantity': 1,
    'lead_time': 1,
    'packaging': 'Test packaging',
    'moq': 1,
    'spq': 1,
    'URL': 'https://www.google.com',
    'is_template': False,
    'assembly': 1,
    'reference': 'Test reference',
    'notes': 'Test notes',
})