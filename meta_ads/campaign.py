"""Campaign orchestration: create, status, and management."""

from pathlib import Path

import click


def create_full_campaign(api, config):
    """Create a complete campaign from config: campaign, ad set, creatives, and ads.

    Returns a dict with all created object IDs.
    """
    campaign_cfg = config["campaign"]
    ad_set_cfg = config["ad_set"]
    ads_cfg = config["ads"]
    status = campaign_cfg.get("status", "PAUSED")

    result = {
        "campaign_id": None,
        "ad_set_id": None,
        "creatives": [],
        "ads": [],
    }
    api.partial_campaign_result = result

    # Step 1: Upload images
    click.echo(click.style("\n[1/4] Uploading images", fg="blue", bold=True))
    image_hashes = {}
    for ad in ads_cfg:
        image_path = Path(ad["image"])
        click.echo(f"  Uploading {image_path.name}...")
        image_hashes[ad["name"]] = api.upload_image(image_path)
        click.echo(click.style(f"  Done.", fg="green"))

    # Step 2: Create campaign
    click.echo(click.style("\n[2/4] Creating campaign", fg="blue", bold=True))
    click.echo(f"  Name: {campaign_cfg['name']}")
    campaign_id = api.create_campaign(
        name=campaign_cfg["name"],
        objective=campaign_cfg.get("objective", "OUTCOME_TRAFFIC"),
        status=status,
        special_ad_categories=campaign_cfg.get("special_ad_categories"),
    )
    result["campaign_id"] = campaign_id
    click.echo(click.style(f"  Campaign ID: {campaign_id}", fg="green"))

    # Step 3: Create ad set
    click.echo(click.style("\n[3/4] Creating ad set", fg="blue", bold=True))
    click.echo(f"  Name: {ad_set_cfg['name']}")
    budget_dollars = int(ad_set_cfg['daily_budget']) / 100
    click.echo(f"  Budget: ${budget_dollars:.2f}/day")
    ad_set_id = api.create_ad_set(
        name=ad_set_cfg["name"],
        campaign_id=campaign_id,
        daily_budget=ad_set_cfg["daily_budget"],
        targeting=ad_set_cfg.get("targeting", {}),
        optimization_goal=ad_set_cfg.get("optimization_goal", "LINK_CLICKS"),
        billing_event=ad_set_cfg.get("billing_event", "IMPRESSIONS"),
        bid_strategy=ad_set_cfg.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
        status=status,
    )
    result["ad_set_id"] = ad_set_id
    click.echo(click.style(f"  Ad Set ID: {ad_set_id}", fg="green"))

    # Step 4: Create creatives and ads
    click.echo(click.style("\n[4/4] Creating ads", fg="blue", bold=True))
    for ad in ads_cfg:
        click.echo(f"  Creating: {ad['name']}")

        creative_id = api.create_ad_creative(
            name=f"{ad['name']} - Creative",
            image_hash=image_hashes[ad["name"]],
            primary_text=ad["primary_text"].strip(),
            headline=ad.get("headline", ""),
            description=ad.get("description", ""),
            link=ad["link"],
            cta=ad.get("cta", "LEARN_MORE"),
        )
        result["creatives"].append(creative_id)

        ad_id = api.create_ad(
            name=ad["name"],
            ad_set_id=ad_set_id,
            creative_id=creative_id,
            status=status,
        )
        result["ads"].append(ad_id)
        click.echo(click.style(f"  Ad ID: {ad_id}", fg="green"))

    return result


def print_campaign_status(api, campaign_id):
    """Fetch and display campaign status with ad sets and ads."""
    campaign = api.get_campaign(campaign_id, fields="name,status,objective,daily_budget")
    click.echo(click.style(f"\nCampaign: {campaign['name']}", bold=True))
    click.echo(f"  ID: {campaign['id']}")
    click.echo(f"  Status: {campaign['status']}")
    click.echo(f"  Objective: {campaign.get('objective', 'N/A')}")

    ad_sets = api.get_ad_sets(campaign_id, fields="name,status,daily_budget")
    if ad_sets:
        click.echo(click.style("\n  Ad Sets:", bold=True))
        for ad_set in ad_sets:
            budget = int(ad_set.get("daily_budget", 0)) / 100
            click.echo(f"    {ad_set['name']}: {ad_set['status']} (${budget:.2f}/day)")

    ads = api.get_ads(campaign_id, fields="name,status,effective_status")
    if ads:
        click.echo(click.style("\n  Ads:", bold=True))
        for ad in ads:
            effective = ad.get("effective_status", ad["status"])
            click.echo(f"    {ad['name']}: {effective}")
