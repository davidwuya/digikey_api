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
            return dk[0]

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
        if len(possible_manufacturers) == 0:
            mfg = self.create_manufacturer(dkpart.Manufacturer)
            return mfg
        else:
            return possible_manufacturers[0]

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
                "category": category.pk,
                "IPN": dkpart.ManufacturerPartNumber,
                "active": True,
                "virtual": False,
                "component": True,
                "purchaseable": 1,
                "assembly": False,
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
                "location": self.parse_locaton(input("Location: ")).pk,
                "quantity": int(input("Quantity: ")),
            },
        )

        print("Part ", dkpart.ProductDescription, " created")

        return

    def parse_locaton(self, location: str) -> StockLocation | None:
        # location is a string in the format A11A
        # A1 is the parent location
        # 1A is the child location
        parent = location[0:2]
        child = location[2:4]
        return self.get_location(parent, child)

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
    
    def get_digikey_supplier(self) -> Company|None:
        suppliers = Company.list(self.invapi, is_supplier=True)
        for supplier in suppliers:
            if supplier.name == "Digi-Key":
                return supplier
        return None
    
    def get_location(self, parent_name: str, child_name: str):
        """
        Get a StockLocation object by its name and parent name.

        :param api: The InvenTreeAPI instance to use for the request.
        :param child_name: The name of the stock location.
        :param parent_name: The name of the parent stock location.
        :return: A StockLocation object if one with the given name is found under the specified parent; otherwise None.
        """
        all_locations = StockLocation.list(self.invapi)

        for location in all_locations:
            if location.name == parent_name:
                parent_location = StockLocation(self.invapi, location.pk)
                child_locations = parent_location.getChildLocations()

                for child_location in child_locations:
                    if child_location.name == child_name:
                        return StockLocation(self.invapi, child_location.pk)

        return None

    def find_supplier_part(self, dkpart: DKPart):
        supplier = self.get_digikey_supplier()
        supplier_parts = SupplierPart.list(self.invapi)
        for idx, supplier_part in enumerate(supplier_parts):
            if supplier_part.SKU == dkpart.DigiKeyPartNumber:
                return supplier_part
        return None
    
    def create_stock(self, dkpart: DKPart):
        part = self.get_part_by_name(dkpart.ProductDescription)
        stock = StockItem.create(
            self.invapi,
            {
                "part": part.pk,
                "supplier_part": self.find_supplier_part(dkpart).pk,
                "supplier": self.get_digikey_supplier().pk,
                "location": self.parse_locaton(input("Location: ")).pk,
                "quantity": int(input("Quantity: ")),
            },

        )
        return stock
    
    def update_stock(self, dkpart: DKPart):
        part = self.get_part_by_name(dkpart.ProductDescription)
        stock = StockItem.list(self.invapi, part=part.pk)
        if len(stock) == 0:
            print("No stock for this part")
            return self.create_stock(dkpart)
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
            return stock_item

    def get_part_by_name(self, name: str) -> Part | None:
        parts = Part.list(self.invapi)
        for idx, part in enumerate(parts):
            if part.description == name:
                return part
        return None
    
    def get_part_by_dkpn(self, dkbn: str) -> Part | None:
        parts = SupplierPart.list(self.invapi)
        for idx, part in enumerate(parts):
            if part.SKU == dkbn:
                return part
        return None

        
    def check_part(self, dkpart: DKPart):
        part = self.get_part_by_name(dkpart.ProductDescription)
        if part is None or len(part) == 0:
            print("Part not found, creating")
            return self.add_digikey_part(dkpart)
        else:
            print("Part found, updating")
            return self.update_stock(dkpart)