from inventree.api import InvenTreeAPI
from inventree.company import SupplierPart, Company, ManufacturerPart
from inventree.part import Part, PartCategory
from inventree.stock import StockItem, StockLocation
from dk_api import DigiKeyAPI, DKPart
import requests
import logging
import os
from typing import Optional

# set logging levels
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("inventree").setLevel(logging.WARNING)


class InvenTreeManager:
    def __init__(self, invapi: InvenTreeAPI, dkapi: DigiKeyAPI):
        self.invapi = invapi
        self.dkapi = dkapi

    def get_digikey_supplier(self) -> Optional[Company]:
        suppliers = Company.list(self.invapi, is_supplier=True)

        if not suppliers:
            logging.warning("No suppliers found")
            dk = Company.create(
                self.invapi,
                {
                    "name": "Digi-Key",
                    "is_supplier": True,
                    "description": "Electronics Supply Store",
                },
            )
            logging.info("Digi-Key supplier created")
            return dk

        for supplier in suppliers:
            if supplier.name == "Digi-Key":
                return supplier

        return None

    def create_manufacturer(
        self, mfg_name: str, is_supplier: bool = False
    ) -> Optional[Company]:
        logging.info(f"Creating manufacturer {mfg_name}")
        return Company.create(
            self.invapi,
            {
                "name": mfg_name,
                "is_manufacturer": True,
                "is_supplier": is_supplier,
                "description": mfg_name,
            },
        )

    def get_manufacturer(self, dkpart: DKPart) -> Company | None:
        possible_manufacturers = Company.list(self.invapi, name=dkpart.Manufacturer)
        if len(possible_manufacturers) == 0:
            mfg = self.create_manufacturer(dkpart.Manufacturer)
            logging.info(f"Manufacturer {dkpart.Manufacturer} created")
            return mfg
        else:
            logging.info(f"Manufacturer {dkpart.Manufacturer} found")
            return possible_manufacturers[0]

    def upload_picture(self, dkpart: DKPart, invPart: Part):
        if dkpart.PrimaryPhoto:
            try:
                r = requests.get(dkpart.PrimaryPhoto)
                r.raise_for_status()

                with open("temp.jpg", "wb") as f:
                    f.write(r.content)

                if invPart.uploadImage("temp.jpg") is None:
                    logging.error(f"Error uploading image for {invPart.name}")
                else:
                    logging.info(f"Image uploaded for {invPart.name}")
            except requests.exceptions.HTTPError as err:
                logging.error(
                    f"Error downloading image for {invPart.name}. Error: {err}"
                )
            finally:
                if os.path.exists("temp.jpg"):
                    os.remove("temp.jpg")

    def create_inventree_part(self, dkpart: DKPart):
        category = self.get_category(dkpart)
        part = Part.create(
            self.invapi,
            {
                "name": dkpart.ProductDescription,
                "description": dkpart.DetailedDescription,
                "category": category.pk,
                "IPN": dkpart.ManufacturerPartNumber,
                "active": True,
                "virtual": False,
                "component": True,
                "purchaseable": 1,
                "assembly": False,
            },
        )
        logging.info(f"InvenTree Part {dkpart.ProductDescription} created")
        self.upload_picture(dkpart, part)
        return part

    def add_digikey_part(
        self, dkpart: DKPart, stock_location: str, quantity: int
    ) -> None:
        dk = self.get_digikey_supplier()
        inv_part = self.create_inventree_part(dkpart)
        if inv_part == -1:
            return
        base_pk = int(inv_part.pk) if inv_part else None
        mfg = self.get_manufacturer(dkpart)

        ManufacturerPart.create(
            self.invapi,
            {
                "part": base_pk,
                "supplier": dk.pk,
                "MPN": dkpart.ManufacturerPartNumber,
                "manufacturer": mfg.pk,
                "description": dkpart.DetailedDescription,
                "link": dkpart.ProductUrl,
            },
        )
        logging.info(f"Manufacturer Part {dkpart.ManufacturerPartNumber} created")

        SupplierPart.create(
            self.invapi,
            {
                "part": base_pk,
                "supplier": dk.pk,
                "SKU": dkpart.DigiKeyPartNumber,
                "manufacturer": mfg.pk,
                "description": dkpart.DetailedDescription,
                "link": dkpart.ProductUrl,
            },
        )
        logging.info(f"Supplier Part {dkpart.DigiKeyPartNumber} created")
        
        StockItem.create(
            self.invapi,
            {
                "part": base_pk,
                "supplier_part": self.find_supplier_part(dkpart).pk,
                "supplier": dk.pk,
                "location": self.parse_locaton(stock_location).pk,
                "quantity": quantity,
            },
        )
        logging.info(f"Stock created for {dkpart.ProductDescription}")

        logging.info(f"Part {dkpart.ProductDescription} created successfully.")

        return

    def parse_locaton(self, location: str) -> Optional[StockLocation]:
        # location is a string in the format A11A
        # A1 is the parent location
        # 1A is the child location
        parent = location[0:2]
        child = location[2:4]
        return self.get_location_from_text(parent, child)

    def get_category_by_name(self, name: str) -> Optional[PartCategory]:
        return next(
            (
                category
                for category in PartCategory.list(self.invapi)
                if category.name == name
            ),
            None,
        )

    def get_category_by_id(self, pk: int) -> Optional[PartCategory]:
        return next(
            (
                category
                for category in PartCategory.list(self.invapi)
                if category.pk == pk
            ),
            None,
        )

    def create_category(self, name: str, parent: int) -> Optional[PartCategory]:
        category = PartCategory.create(
            self.invapi,
            {
                "name": name,  # name of the category
                "parent": parent,  # primary key of the parent category
            },
        )
        logging.info("Category ", name, " created")
        return category

    def get_category(self, part: DKPart) -> Optional[PartCategory]:
        parent_pk = 1
        category = None
        for category_name in part.LimitedTaxonomy:
            category = self.get_category_by_name(category_name)
            if category is None:
                category = self.create_category(category_name, parent_pk)
            parent_pk = category.pk
        return category

    def get_location_from_text(
        self, parent_name: str, child_name: str
    ) -> Optional[StockLocation]:
        all_locations = StockLocation.list(self.invapi)
        for location in all_locations:
            if location.name == parent_name:
                parent_location = StockLocation(self.invapi, location.pk)
                child_locations = parent_location.getChildLocations()
                return next(
                    (
                        StockLocation(self.invapi, child.pk)
                        for child in child_locations
                        if child.name == child_name
                    ),
                    None,
                )
        return None

    def get_stock_by_part(self, part: Part) -> Optional[StockItem]:
        stock = StockItem.list(self.invapi)
        for idx, item in enumerate(stock):
            if item.part == part.pk:
                logging.info(f"Stock found for {part.name}")
                return item
        return None

    def find_supplier_part(self, dkpart: DKPart) -> Optional[SupplierPart]:
        supplier = self.get_digikey_supplier()
        supplier_parts = SupplierPart.list(self.invapi)
        for idx, supplier_part in enumerate(supplier_parts):
            if supplier_part.SKU == dkpart.DigiKeyPartNumber:
                logging.info(f"Supplier part found for {dkpart.ProductDescription}")
                return supplier_part
        return None

    def create_stock(
        self, dkpart: DKPart, location: str, quantity: int
    ) -> Optional[StockItem]:
        part = self.get_invpart_by_dkpart(dkpart)
        stock = StockItem.create(
            self.invapi,
            {
                "part": part.pk,
                "supplier_part": self.find_supplier_part(dkpart).pk,
                "supplier": self.get_digikey_supplier().pk,
                "location": self.parse_locaton(location).pk,
                "quantity": quantity,
            },
        )
        logging.info(
            f"Stock created for {dkpart.ProductDescription} at {location} with quantity {quantity}"
        )
        return stock

    def update_stock(self, part: Part, new_quantity: int) -> Optional[StockItem]:
        stock = self.get_stock_by_part(part)
        if stock is None:
            logging.error("Stock not found for this part: ")
            return
        stock.addStock(new_quantity) if new_quantity > 0 else stock.removeStock(
            abs(new_quantity)
        )
        logging.info(f"Quantity updated.")
        return stock

    def get_stock_quantity(self, part: Part) -> Optional[int]:
        stock = self.get_stock_by_part(part)
        if stock is None:
            logging.error("Stock not found for this part: ")
            return
        return int(stock.quantity)

    def get_loaction_from_pk(self, pk: int) -> Optional[StockLocation]:
        return next(
            (
                location
                for location in StockLocation.list(self.invapi)
                if location.pk == pk
            ),
            None,
        )

    def get_location_name_from_location(self, location: StockLocation) -> str:
        parent = location.getParentLocation()
        if parent is None:
            return location.name
        return parent.name + location.name

    def get_invpart_by_dkpart(self, dkpart: DKPart) -> Optional[Part]:
        logging.info(f"Searching for {dkpart.ProductDescription} in inventory")
        parts = Part.list(self.invapi)
        for idx, part in enumerate(parts):
            if str(part.IPN) == str(dkpart.ManufacturerPartNumber):
                logging.info(f"InvenTree Part found: {part.name}")
                return part

    def check_part(
        self, dkpart: DKPart, location: str = "", quantity: int = 0
    ) -> Optional[Part]:
        part = self.get_invpart_by_dkpart(dkpart)
        if part is None:
            logging.info("Part not found, creating")
            location = input("Enter location: ")
            quantity = int(input("Enter quantity: "))
            self.add_digikey_part(dkpart, location, quantity)
            logging.info("Part created successfully")
            return
        else:
            current_qty = self.get_stock_quantity(part)
            logging.info(f"Current stock quantity: {current_qty}")
            if current_qty == None:
                # stock item does not exist, create it
                logging.info("Stock item not found, creating")
                location = input("Enter location: ")
                quantity = int(input("Enter quantity: "))
                self.create_stock(dkpart, location, quantity)
                dkpart.write_labels()
                return
            else:
                location_pk = self.get_stock_by_part(part).getLocation().pk
                location = self.get_loaction_from_pk(location_pk)
                logging.info(
                    f"Current location: {self.get_location_name_from_location(location)}"
                )
                quantity = int(
                    input("Enter quantity adjustment, enter 0 to reprint labels: ")
                )
                if quantity == 0:
                    logging.info("Reprinting labels")
                    dkpart.write_labels()
                    return
                else:
                    self.update_stock(part, quantity)
                    logging.info("Quantity updated successfully")
                    return
