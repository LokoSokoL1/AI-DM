from .campaign_manager import CampaignManager


def main():

    manager = CampaignManager()

    campaign = manager.create_campaign(
        "Lost Mine Adventure",
        "A group searches for the lost mine of Phandelver."
    )

    campaign.add_character(
        "Nekria"
    )

    campaign.add_note(
        "The party discovered mysterious ruins."
    )

    manager.save_campaign(
        campaign
    )

    print("Created:")
    print(campaign)

    loaded = manager.load_campaign(
        "Lost Mine Adventure"
    )

    print("\nLoaded:")
    print(loaded)


if __name__ == "__main__":
    main()