"""A small in-memory product catalog with stock tracking."""


class Catalog:
    def __init__(self):
        self.items = {}

    def add_item(self, name, quantity, tags=[]):
        """Register an item. Every item is automatically tagged 'in-stock'."""
        tags.append("in-stock")
        self.items[name] = {"quantity": quantity, "tags": tags}

    def tags_for(self, name):
        """Return the list of tags for an item."""
        return self.items[name]["tags"]

    def quantity_of(self, name):
        """Return the current quantity of an item."""
        return self.items[name]["quantity"]

    def low_stock(self, threshold):
        """Return names of items whose quantity is at or below threshold."""
        return [
            name
            for name, item in self.items.items()
            if item["quantity"] < threshold
        ]
