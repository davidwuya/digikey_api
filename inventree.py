from inventree.api import InvenTreeAPI
from inventree.company import SupplierPart, Company, ManufacturerPart
from inventree.part import Part, PartCategory
from inventree.stock import StockItem, StockLocation
from dk_api import DigiKeyAPI, DKPart
import requests
import os

class InvenTreeManager:
    def __init__(self, invapi: InvenTreeAPI, dkapi: DigiKeyAPI):
        self.invapi = invapi
        self.dkapi = dkapi

    def get_digikey_supplier(self) -> Company | None:
        dk = Company.list(self.invapi, name="Digi-Key")
        if dk and len(dk) == 0:
            dk = Company.create(
                self.invapi,
                {
                    "name": "Digi-Key",
                    "is_supplier": True,
                    "description": "Electronics Supply Store",
                },
            )
            print("Supplier created")
            return dk
        else:
            return dk[0] if dk else None

    def create_manufacturer(
        self, mfg_name: str, is_supplier: bool = False
    ) -> Company | None:
        mfg = Company.create(
            self.invapi,
            {
                "name": mfg_name,
                "is_manufacturer": True,
                "is_supplier": is_supplier,
                "description": mfg_name,
            },
        )
        return mfg if mfg else None

    def find_manufacturer(self, dkpart: DKPart) -> Company | None:
        possible_manufacturers = Company.list(self.invapi, name=dkpart.Manufacturer)
        if not possible_manufacturers:
            return None
        elif possible_manufacturers and len(possible_manufacturers) == 0:
            mfg = self.create_manufacturer(dkpart.Manufacturer)
            return mfg
        else:
            print("=" * 20)
            print("Choose a manufacturer")
            for idx, mfg in enumerate(possible_manufacturers):
                print(
                    "\t%d %s"
                    % (
                        idx,
                        mfg.name,
                    )
                )
            print("=" * 20)
            idx = int(input("> "))
            return possible_manufacturers[idx]

    def upload_picture(self, dkpart: DKPart, invPart):
        if dkpart.PrimaryPhoto:
            # download the picture to a file
            r = requests.get(dkpart.PrimaryPhoto)
            with open("temp.jpg", "wb") as f:
                f.write(r.content)
            # upload the picture to the part
            invPart.uploadImage("temp.jpg")
            # delete the picture
            os.remove("temp.jpg")
            print("Image uploaded for %s" % invPart.name)

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
                "category": category.pk if category else None,
                "active": True,
                "virtual": False,
                "component": True,
                "purchaseable": 1,
            },
        )
        self.upload_picture(dkpart, part)
        return part

    def add_digikey_part(self, dkpart: DKPart):
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
                "supplier": dk.pk if dk else None,
                "MPN": dkpart.ManufacturerPartNumber,
                "manufacturer": mfg.pk if mfg else None,
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

        print("Part ", dkpart.ProductDescription, " created")

        return

    def get_category_by_name(self, name: str) -> PartCategory | None:
        categories = PartCategory.list(self.invapi)
        for idx, category in enumerate(categories):
            if category.name == name:
                return category
        return None

    def get_category_by_id(self, pk: int) -> PartCategory | None:
        categories = PartCategory.list(self.invapi)
        for idx, category in enumerate(categories):
            if category.pk == pk:
                return category
        return None

    def create_category(self, name: str, parent: int) -> PartCategory | None:
        category = PartCategory.create(
            self.invapi,
            {
                "name": name,  # name of the category
                "parent": parent,  # primary key of the parent category
            },
        )
        return category

    def get_category(self, part: DKPart):
        parent_pk = 1
        for i in range(len(part.LimitedTaxonomy)):
            category = self.get_category_by_name(part.LimitedTaxonomy[i])
            if category is None:
                category = self.create_category(part.LimitedTaxonomy[i], parent_pk)
            parent_pk = category.pk
        return category

    def get_location(self, name: str) -> StockLocation | None:
        locations = StockLocation.list(self.invapi)
        for idx, location in enumerate(locations):
            if location.name == name:
                return location
        return None

    def create_location(self, name: str, parent: int) -> StockLocation | None:
        location = StockLocation.create(
            self.invapi,
            {
                "name": name,  # name of the category
                "parent": parent,  # primary key of the parent category
            },
        )
        return location

    def get_location_by_id(self, pk: int) -> StockLocation | None:
        locations = StockLocation.list(self.invapi)
        for idx, location in enumerate(locations):
            if location.pk == pk:
                return location
        return None

    def update_stock(self, dkpart: DKPart):
        part = Part.list(
            self.invapi,
            name=dkpart.ProductDescription,
            description=dkpart.DetailedDescription,
        )[0] # there should only be one
        stock = StockItem.list(self.invapi, part=part.pk)
        if len(stock) == 0:
            print("No stock for this part")
            return
        else:
            print("Choose a stock item")
            for idx, item in enumerate(stock):
                print(
                    "\t%d %s"
                    % (
                        idx,
                        item.name,
                    )
                )
            print("=" * 20)
            idx = int(input("> "))
            stock_item = stock[idx]
            print("Current stock: %d" % stock_item.quantity)
            print("Enter new stock: ")
            new_stock = int(input("> "))
            stock_item.quantity = new_stock
            stock_item.save()
            print("Stock updated")

    def update_location(self, dkpart: DKPart):
        part = Part.list(
            self.invapi,
            name=dkpart.ProductDescription,
            description=dkpart.DetailedDescription,
        )[0]
        stock = StockItem.list(self.invapi, part=part.pk)
        if len(stock) == 0:
            print("No stock for this part")
            return
        else:
            print("Choose a stock item")
            for idx, item in enumerate(stock):
                print(
                    "\t%d %s"
                    % (
                        idx,
                        item.name,
                    )
                )
            print("=" * 20)
            idx = int(input("> "))
            stock_item = stock[idx]
            print("Current location: %s" % stock_item.location.name)
            print("Enter new location: ")
            new_location = input("> ")
            location = self.get_location(new_location)
            if location is None:
                location = self.create_location(new_location, 1)
            stock_item.location = location.pk
            stock_item.save()
            print("Location updated")

    def get_part_by_name(self, pk: int) -> Part | None:
        parts = Part.list(self.invapi)
        for idx, part in enumerate(parts):
            if part.pk == pk:
                return part
        return None

    def update_digikey_part(self, dkpart: DKPart):
        part = Part.list(
            self.invapi, name=dkpart.ProductDescription, description=dkpart.DetailedDescription
        )[0]
        print("Choose an option")
        print("\t1 Update stock")
        print("\t2 Update location")
        print("=" * 20)
        idx = int(input("> "))
        if idx == 1:
            self.update_stock(dkpart)
        elif idx == 2:
            self.update_location(dkpart)
        else:
            print("Invalid option")
            return