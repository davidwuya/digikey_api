from blabel import LabelWriter


def write_labels(ManufacturerPartNumber: str, Category: str, Description: str)->None:
    label_writer = LabelWriter("template.html", default_stylesheets=("style.css",))
    records = [
        dict(
            ManufacturerPartNumber = ManufacturerPartNumber,
            Category = Category,
            Description = Description,
        ),
    ]
    fname = f"{ManufacturerPartNumber}.pdf"
    label_writer.write_labels(records, target=fname)
