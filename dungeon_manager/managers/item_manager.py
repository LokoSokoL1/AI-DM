from dungeon_manager.models.item import Item
from dungeon_manager.storage.json_storage import JSONStorage


class ItemManager:
    """
    Handles item creation and storage.
    """

    def __init__(self):
        self.storage = JSONStorage()

    def create_item(
        self,
        name: str,
        item_type: str,
        description: str = "",
        magical: bool = False,
        rarity: str = "Common",
        properties=None
    ):

        if properties is None:
            properties = []

        item = Item(
            name=name,
            item_type=item_type,
            description=description,
            magical=magical,
            rarity=rarity,
            properties=properties
        )

        self.save_item(item)

        return item


    def save_item(self, item: Item):

        data = {
            "name": item.name,
            "item_type": item.item_type,
            "description": item.description,
            "magical": item.magical,
            "rarity": item.rarity,
            "properties": item.properties
        }

        self.storage.save(
            "items",
            item.name.lower(),
            data
        )


    def load_item(self, name: str):

        data = self.storage.load(
            "items",
            name.lower()
        )

        if data is None:
            return None

        return Item(
            name=data["name"],
            item_type=data["item_type"],
            description=data["description"],
            magical=data["magical"],
            rarity=data["rarity"],
            properties=data["properties"]
        )