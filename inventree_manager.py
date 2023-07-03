from inventree.api import InvenTreeAPI
from inventree.company import SupplierPart, Company, ManufacturerPart
from inventree.part import Part, PartCategory
from inventree.stock import StockItem, StockLocation
from dk_api import DigiKeyAPI, DKPart
import requests
import logging
import os
from typing import Optional


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
        possible_parts = Part.list(
            self.invapi,
            name=dkpart.ProductDescription,
            description=dkpart.DetailedDescription,
        )
        if not possible_parts:
            return None
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
        mfg = self.find_manufacturer(dkpart)

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

        logging.info("DigiKey part ", dkpart.ProductDescription, " created")

        return

    def parse_locaton(self, location: str) -> StockLocation:
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

    def get_category(self, part: DKPart):
        parent_pk = 1
        for category_name in part.LimitedTaxonomy:
            category = self.get_category_by_name(category_name)
            if category is None:
                category = self.create_category(category_name, parent_pk)
            parent_pk = category.pk
        return category

    def get_location_from_text(self, parent_name: str, child_name: str):
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

    def get_stock_by_part(self, part: Part):
        stock = StockItem.list(self.invapi)
        for idx, item in enumerate(stock):
            if item.part == part.pk:
                logging.info(f"Stock found for {part.name}")
                return item
        return None

    def find_supplier_part(self, dkpart: DKPart):
        supplier = self.get_digikey_supplier()
        supplier_parts = SupplierPart.list(self.invapi)
        for idx, supplier_part in enumerate(supplier_parts):
            if supplier_part.SKU == dkpart.DigiKeyPartNumber:
                logging.info(f"Supplier part found for {dkpart.ProductDescription}")
                return supplier_part
        return None

    def create_stock(self, dkpart: DKPart, location: str, quantity: int):
        part = self.get_part_by_name(dkpart.ProductDescription)
        stock = StockItem.create(
            self.invapi,
            {
                "part": part.pk,
                "supplier_part": self.find_supplier_part(dkpart).pk,
                "supplier": self.get_digikey_supplier().pk,
                "location": self.parse_location(location).pk,
                "quantity": quantity,
            },
        )
        logging.info(
            f"Stock created for {dkpart.ProductDescription} at {location} with quantity {quantity}"
        )
        return stock

    def update_stock(self, part: Part, new_quantity: int):
        stock = self.get_stock_by_part(part)
        if stock is None:
            logging.error("Stock not found for part: ", part)
            return

        stock.quantity = new_quantity
        stock.save()
        logging.info(f"Quantity updated. New quantity: {stock.quantity}")
        return stock

    def get_invpart_by_dkpart(self, dkpart: DKPart) -> Optional[Part]:
        logging.info(f"Searching for {dkpart} in inventory")
        for part in self.parts:
            if part.dkpart == dkpart:
                logging.info(f"Found {dkpart} in inventory")
                return part
        logging.info(f"{dkpart} not found in inventory")
        return None

    def check_part(self, dkpart: DKPart, location: str = None, quantity: int = 0):
        part = self.get_invpart_by_dkpart(dkpart)
        if part is None:
            logging.info("Part not found, creating")
            self.add_digikey_part(dkpart)
        else:
            logging.info("Part found, updating stock")
            self.update_stock(part, quantity)
