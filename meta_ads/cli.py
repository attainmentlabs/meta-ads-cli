"""CLI entry point for meta-ads."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv

from meta_ads import __version__
from meta_ads.api import MetaAdsAPI, MetaAPIError
from meta_ads.campaign import create_full_campaign, print_campaign_status
from meta_ads.config import load_config, validate_config, ConfigError


def audit_log_path():
    configured = os.getenv("META_ADS_AUDIT_LOG_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".meta-ads-cli" / "audit.jsonl"


def check_audit_log_writable():
    path = audit_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        raise click.ClickException(f"Audit log is not writable at {path}: {exc}") from exc


def write_audit(action, request, result):
    """Write a local audit event without credentials or secrets."""
    path = audit_log_path()
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "ad_account_id": os.getenv("META_AD_ACCOUNT_ID"),
        "request": request,
        "result": result,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError as exc:
        return f"Audit log write failed at {path}: {exc}"
    return None


def echo_audit_warning(warning):
    if warning:
        click.echo(click.style(f"Warning: {warning}", fg="yellow"))


def bounded_limit(limit):
    return max(1, min(limit, 100))


def check_daily_budget_limit(daily_budget_cents, action):
    if daily_budget_cents <= 0:
        raise click.ClickException(f"{action} daily_budget_cents must be positive.")
    raw_limit = os.getenv("META_ADS_MAX_DAILY_BUDGET_CENTS")
    if not raw_limit:
        return
    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise click.ClickException("META_ADS_MAX_DAILY_BUDGET_CENTS must be an integer.") from exc
    if daily_budget_cents > limit:
        raise click.ClickException(
            f"{action} budget {daily_budget_cents} exceeds META_ADS_MAX_DAILY_BUDGET_CENTS={limit}."
        )


def echo_json(data):
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def get_api(dry_run=False):
    """Create a MetaAdsAPI instance from environment variables."""
    access_token = os.getenv("META_ACCESS_TOKEN")
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID")
    page_id = os.getenv("META_PAGE_ID")
    api_version = os.getenv("META_API_VERSION", "v21.0")

    missing = []
    if not access_token:
        missing.append("META_ACCESS_TOKEN")
    if not ad_account_id:
        missing.append("META_AD_ACCOUNT_ID")
    if not page_id:
        missing.append("META_PAGE_ID")

    if missing:
        click.echo(click.style("Missing required environment variables:", fg="red"))
        for var in missing:
            click.echo(click.style(f"  {var}", fg="red"))
        click.echo("\nSet them in .env or export them in your shell.")
        click.echo("See: https://github.com/attainmentlabs/meta-ads-cli#configuration")
        sys.exit(1)

    return MetaAdsAPI(
        access_token=access_token,
        ad_account_id=ad_account_id,
        page_id=page_id,
        api_version=api_version,
        dry_run=dry_run,
    )


@click.group()
@click.version_option(version=__version__, prog_name="meta-ads")
def cli():
    """Create and manage Meta ad campaigns from your terminal."""
    load_dotenv()


@cli.command()
@click.option("--config", "config_path", default="campaign.yaml", help="Path to campaign YAML config.")
@click.option("--dry-run", is_flag=True, help="Preview what would be created without making API calls.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def create(config_path, dry_run, yes):
    """Create a full campaign from a YAML config file."""
    try:
        config = load_config(config_path)
        validate_config(config)
    except ConfigError as e:
        click.echo(click.style(f"Config error:\n{e}", fg="red"))
        sys.exit(1)

    campaign_name = config["campaign"]["name"]
    status = config["campaign"].get("status", "PAUSED")
    budget = int(config["ad_set"]["daily_budget"]) / 100
    num_ads = len(config["ads"])

    click.echo(click.style("=" * 50, fg="blue"))
    click.echo(click.style("meta-ads create", fg="blue", bold=True))
    click.echo(click.style("=" * 50, fg="blue"))
    click.echo(f"Campaign:  {campaign_name}")
    click.echo(f"Budget:    ${budget:.2f}/day")
    click.echo(f"Ads:       {num_ads}")
    click.echo(f"Status:    {status}")
    click.echo(f"Mode:      {'DRY RUN' if dry_run else 'LIVE'}")
    try:
        check_daily_budget_limit(int(config["ad_set"]["daily_budget"]), "create")
    except click.ClickException as e:
        click.echo(click.style(f"Budget error: {e.message}", fg="red"))
        sys.exit(1)

    if not dry_run and not yes:
        click.echo()
        if not click.confirm(click.style("This will create real campaigns. Continue?", fg="yellow")):
            click.echo("Aborted.")
            sys.exit(0)
    confirmed = not dry_run
    if confirmed:
        check_audit_log_writable()

    api = get_api(dry_run=dry_run)

    try:
        result = create_full_campaign(api, config)
    except MetaAPIError as e:
        failure = {
                "success": False,
                "dry_run": dry_run,
                "confirmed": confirmed,
                "partial_result": getattr(api, "partial_campaign_result", {}),
                "error": str(e),
                "error_code": e.error_code,
        }
        audit_warning = write_audit(
            "create",
            {
                "config_path": config_path,
                "campaign_name": campaign_name,
                "daily_budget_cents": int(config["ad_set"]["daily_budget"]),
                "ad_count": num_ads,
                "dry_run": dry_run,
                "confirmed": confirmed,
            },
            failure,
        )
        echo_audit_warning(audit_warning)
        click.echo(click.style(f"\nAPI Error: {e}", fg="red"))
        if e.error_code:
            click.echo(click.style(f"Error code: {e.error_code}", fg="red"))
        sys.exit(1)
    audit_warning = write_audit(
        "create",
        {
            "config_path": config_path,
            "campaign_name": campaign_name,
            "daily_budget_cents": int(config["ad_set"]["daily_budget"]),
            "ad_count": num_ads,
            "dry_run": dry_run,
            "confirmed": confirmed,
        },
        result,
    )
    echo_audit_warning(audit_warning)

    # Summary
    click.echo(click.style("\n" + "=" * 50, fg="green"))
    click.echo(click.style("Done!", fg="green", bold=True))
    click.echo(click.style("=" * 50, fg="green"))
    click.echo(f"Campaign:  {result['campaign_id']} ({status})")
    click.echo(f"Ad Set:    {result['ad_set_id']} ({status})")
    click.echo(f"Creatives: {len(result['creatives'])}")
    click.echo(f"Ads:       {len(result['ads'])}")

    if not dry_run:
        click.echo(f"\nView in Ads Manager:")
        click.echo(f"  https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={api.ad_account_id}")


@cli.command("account")
@click.option("--json-output", is_flag=True, help="Print raw JSON.")
def account(json_output):
    """Show the configured Meta ad account summary."""
    api = get_api()
    try:
        account_data = api.get_ad_account()
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    if json_output:
        echo_json(account_data)
        return
    click.echo(click.style("Meta ad account", fg="blue", bold=True))
    for key in ["id", "name", "account_status", "currency", "timezone_name", "amount_spent", "balance"]:
        click.echo(f"  {key}: {account_data.get(key, 'N/A')}")


@cli.command("campaigns")
@click.option("--limit", default=25, show_default=True, help="Number of campaigns to return, max 100.")
@click.option("--json-output", is_flag=True, help="Print raw JSON.")
def campaigns(limit, json_output):
    """List campaigns in the configured ad account."""
    api = get_api()
    try:
        rows = api.list_campaigns(limit=bounded_limit(limit))
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    if json_output:
        echo_json({"campaigns": rows})
        return
    for row in rows:
        click.echo(f"{row.get('id')}  {row.get('status')}  {row.get('name')}")


@cli.command("adsets")
@click.option("--limit", default=25, show_default=True, help="Number of ad sets to return, max 100.")
@click.option("--json-output", is_flag=True, help="Print raw JSON.")
def adsets(limit, json_output):
    """List ad sets in the configured ad account."""
    api = get_api()
    try:
        rows = api.list_ad_sets(limit=bounded_limit(limit))
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    if json_output:
        echo_json({"ad_sets": rows})
        return
    for row in rows:
        budget = row.get("daily_budget", "N/A")
        click.echo(f"{row.get('id')}  {row.get('status')}  {budget}  {row.get('name')}")


@cli.command("ads")
@click.option("--limit", default=25, show_default=True, help="Number of ads to return, max 100.")
@click.option("--json-output", is_flag=True, help="Print raw JSON.")
def ads(limit, json_output):
    """List ads in the configured ad account."""
    api = get_api()
    try:
        rows = api.list_ads(limit=bounded_limit(limit))
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    if json_output:
        echo_json({"ads": rows})
        return
    for row in rows:
        click.echo(f"{row.get('id')}  {row.get('status')}  {row.get('name')}")


@cli.command("insights")
@click.argument("object_id", required=False)
@click.option("--level", default="", help="Optional account breakdown: campaign, adset, or ad.")
@click.option("--date-preset", default="last_7d", show_default=True, help="Meta date preset.")
@click.option("--limit", default=25, show_default=True, help="Number of rows to return, max 100.")
@click.option("--json-output", is_flag=True, help="Print raw JSON.")
def insights(object_id, level, date_preset, limit, json_output):
    """Show account, campaign, ad set, or ad insights."""
    api = get_api()
    target = object_id or api.act_id
    try:
        rows = api.get_insights(
            target,
            level=level or None,
            date_preset=date_preset,
            limit=bounded_limit(limit),
        )
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    payload = {"object_id": target, "level": level or None, "date_preset": date_preset, "insights": rows}
    if json_output:
        echo_json(payload)
        return
    for row in rows:
        click.echo(
            f"{row.get('campaign_name', target)}  spend={row.get('spend', '0')}  "
            f"clicks={row.get('clicks', '0')}  impressions={row.get('impressions', '0')}"
        )


@cli.command("budget")
@click.argument("object_id")
@click.argument("daily_budget_cents", type=int)
@click.option("--live", is_flag=True, help="Make the live Meta API change. Defaults to dry run.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def budget(object_id, daily_budget_cents, live, yes):
    """Update campaign or ad set daily budget."""
    dry_run = not live
    confirmed = live
    check_daily_budget_limit(daily_budget_cents, "budget")
    if not dry_run and not yes:
        dollars = daily_budget_cents / 100
        if not click.confirm(click.style(f"Set {object_id} to ${dollars:.2f}/day?", fg="yellow")):
            click.echo("Aborted.")
            return
    if confirmed:
        check_audit_log_writable()
    api = get_api(dry_run=dry_run)
    try:
        api.update_daily_budget(object_id, daily_budget_cents)
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    result = {
        "success": True,
        "object_id": object_id,
        "daily_budget_cents": daily_budget_cents,
        "dry_run": dry_run,
        "confirmed": confirmed,
    }
    audit_warning = write_audit(
        "budget",
        {
            "object_id": object_id,
            "daily_budget_cents": daily_budget_cents,
            "dry_run": dry_run,
            "confirmed": confirmed,
        },
        result,
    )
    echo_audit_warning(audit_warning)
    click.echo(click.style("Budget update accepted.", fg="green"))
    if dry_run:
        click.echo("Dry run only. No live Meta change was made.")


@cli.command("upload-image")
@click.argument("image_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--live", is_flag=True, help="Upload to Meta. Defaults to dry run.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def upload_image(image_path, live, yes):
    """Upload an image and return the Meta image hash."""
    dry_run = not live
    confirmed = live
    if not dry_run and not yes:
        if not click.confirm(click.style(f"Upload {image_path.name} to Meta?", fg="yellow")):
            click.echo("Aborted.")
            return
    if confirmed:
        check_audit_log_writable()
    api = get_api(dry_run=dry_run)
    try:
        image_hash = api.upload_image(image_path)
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    result = {"success": True, "image_hash": image_hash, "dry_run": dry_run, "confirmed": confirmed}
    audit_warning = write_audit(
        "upload-image",
        {"image_path": str(image_path), "dry_run": dry_run, "confirmed": confirmed},
        result,
    )
    echo_audit_warning(audit_warning)
    click.echo(click.style(f"Image hash: {image_hash}", fg="green"))
    if dry_run:
        click.echo("Dry run only. No live Meta upload was made.")


@cli.command("bulk-status")
@click.argument("status")
@click.argument("campaign_ids", nargs=-1, required=True)
@click.option("--live", is_flag=True, help="Make the live Meta API changes. Defaults to dry run.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def bulk_status(status, campaign_ids, live, yes):
    """Bulk pause, activate, or delete campaigns."""
    dry_run = not live
    confirmed = live
    status = status.upper()
    if status not in {"PAUSED", "ACTIVE", "DELETED"}:
        raise click.ClickException("status must be PAUSED, ACTIVE, or DELETED.")
    if not dry_run and not yes:
        if not click.confirm(click.style(f"Set {len(campaign_ids)} campaigns to {status}?", fg="yellow")):
            click.echo("Aborted.")
            return
    if confirmed:
        check_audit_log_writable()
    api = get_api(dry_run=dry_run)
    changed = []
    current_campaign_id = None
    try:
        for campaign_id in campaign_ids:
            current_campaign_id = campaign_id
            api.update_status(campaign_id, status)
            changed.append({"campaign_id": campaign_id, "status": status})
    except MetaAPIError as e:
        audit_warning = write_audit(
            "bulk-status",
            {
                "campaign_ids": list(campaign_ids),
                "status": status,
                "dry_run": dry_run,
                "confirmed": confirmed,
            },
            {
                "success": False,
                "dry_run": dry_run,
                "confirmed": confirmed,
                "changed": changed,
                "failed_campaign_id": current_campaign_id,
                "error": str(e),
                "error_code": e.error_code,
            },
        )
        echo_audit_warning(audit_warning)
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)
    result = {"success": True, "dry_run": dry_run, "confirmed": confirmed, "changed": changed}
    audit_warning = write_audit(
        "bulk-status",
        {"campaign_ids": list(campaign_ids), "status": status, "dry_run": dry_run, "confirmed": confirmed},
        result,
    )
    echo_audit_warning(audit_warning)
    click.echo(click.style(f"{len(changed)} campaign updates accepted.", fg="green"))
    if dry_run:
        click.echo("Dry run only. No live Meta change was made.")


@cli.command("setup")
@click.option(
    "--client",
    type=click.Choice(["claude", "cursor", "codex", "chatgpt"], case_sensitive=False),
    default="claude",
    show_default=True,
    help="Client setup snippet to print.",
)
def setup(client):
    """Print a one-step setup snippet for common AI clients."""
    client = client.lower()
    config = {
        "mcpServers": {
            "meta-ads": {
                "command": "uvx",
                "args": ["meta-ads-manager-mcp"],
                "env": {
                    "META_ACCESS_TOKEN": "your-token-here",
                    "META_AD_ACCOUNT_ID": "your-account-id",
                    "META_PAGE_ID": "your-page-id",
                    "META_ADS_MAX_DAILY_BUDGET_CENTS": "5000",
                },
            }
        }
    }
    if client == "chatgpt":
        click.echo("ChatGPT setup needs a hosted MCP endpoint. Use the hosted roadmap until remote MCP is shipped.")
        click.echo("For now, use Claude, Cursor, or Codex with the local config below.")
    else:
        click.echo(f"Add this block to your {client} MCP config:")
    echo_json(config)


@cli.command()
@click.argument("campaign_id")
def status(campaign_id):
    """Show the status of a campaign and its ads."""
    api = get_api()
    try:
        print_campaign_status(api, campaign_id)
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)


@cli.command()
@click.argument("campaign_id")
def pause(campaign_id):
    """Pause a campaign."""
    check_audit_log_writable()
    api = get_api()
    try:
        api.update_status(campaign_id, "PAUSED")
        audit_warning = write_audit("pause", {"campaign_id": campaign_id}, {"success": True, "campaign_id": campaign_id})
        echo_audit_warning(audit_warning)
        click.echo(click.style(f"Campaign {campaign_id} paused.", fg="green"))
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)


@cli.command()
@click.argument("campaign_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def activate(campaign_id, yes):
    """Activate a campaign. This will start spending your budget."""
    if not yes:
        if not click.confirm(click.style("This will start spending your ad budget. Continue?", fg="yellow")):
            click.echo("Aborted.")
            return
    confirmed = True
    check_audit_log_writable()

    api = get_api()
    try:
        api.update_status(campaign_id, "ACTIVE")
        audit_warning = write_audit(
            "activate",
            {"campaign_id": campaign_id, "confirmed": confirmed},
            {"success": True, "campaign_id": campaign_id, "confirmed": confirmed},
        )
        echo_audit_warning(audit_warning)
        click.echo(click.style(f"Campaign {campaign_id} activated.", fg="green"))
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)


@cli.command()
@click.argument("campaign_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def delete(campaign_id, yes):
    """Delete a campaign. This cannot be undone."""
    if not yes:
        if not click.confirm(click.style("This will permanently delete the campaign. Continue?", fg="red")):
            click.echo("Aborted.")
            return
    confirmed = True
    check_audit_log_writable()

    api = get_api()
    try:
        api.delete_campaign(campaign_id)
        audit_warning = write_audit(
            "delete",
            {"campaign_id": campaign_id, "confirmed": confirmed},
            {"success": True, "campaign_id": campaign_id, "confirmed": confirmed},
        )
        echo_audit_warning(audit_warning)
        click.echo(click.style(f"Campaign {campaign_id} deleted.", fg="green"))
    except MetaAPIError as e:
        click.echo(click.style(f"API Error: {e}", fg="red"))
        sys.exit(1)


@cli.command()
@click.option("--config", "config_path", default="campaign.yaml", help="Path to campaign YAML config.")
def validate(config_path):
    """Validate a campaign YAML config without making API calls."""
    try:
        config = load_config(config_path)
        validate_config(config)
    except ConfigError as e:
        click.echo(click.style(f"Validation failed:\n{e}", fg="red"))
        sys.exit(1)

    campaign_name = config["campaign"]["name"]
    num_ads = len(config["ads"])
    budget = int(config["ad_set"]["daily_budget"]) / 100

    click.echo(click.style("Config is valid.", fg="green"))
    click.echo(f"  Campaign: {campaign_name}")
    click.echo(f"  Budget:   ${budget:.2f}/day")
    click.echo(f"  Ads:      {num_ads}")
