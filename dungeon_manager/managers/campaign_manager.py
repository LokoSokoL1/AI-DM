from dungeon_manager.models.campaign import Campaign
from dungeon_manager.storage.json_storage import JSONStorage


class CampaignManager:
    """
    Handles campaign creation and storage.
    """

    def __init__(self, storage=None):
        self.storage = storage if storage is not None else JSONStorage()

    def create_campaign(
        self,
        name: str,
        description: str = ""
    ):

        campaign = Campaign(
            name=name,
            description=description
        )

        self.save_campaign(campaign)

        return campaign


    def save_campaign(self, campaign: Campaign):

        data = {
            "name": campaign.name,
            "description": campaign.description,
            "characters": campaign.characters,
            "locations": campaign.locations,
            "notes": campaign.notes
        }

        self.storage.save(
            "campaigns",
            campaign.name.lower(),
            data
        )


    def load_campaign(self, name: str):

        data = self.storage.load(
            "campaigns",
            name.lower()
        )

        if data is None:
            return None

        return Campaign(
            name=data["name"],
            description=data["description"],
            characters=data["characters"],
            locations=data["locations"],
            notes=data["notes"]
        )
