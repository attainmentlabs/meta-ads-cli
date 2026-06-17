"""Meta Graph API client for ad management."""

import json
import click
import requests


class MetaAPIError(Exception):
    """Raised when the Meta API returns an error."""

    def __init__(self, status_code, message, error_code=None):
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class MetaAdsAPI:
    """Lightweight wrapper around the Meta Marketing API."""

    def __init__(self, access_token, ad_account_id, page_id, api_version="v21.0", dry_run=False):
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.act_id = f"act_{ad_account_id}"
        self.page_id = page_id
        self.api_version = api_version
        self.base_url = f"https://graph.facebook.com/{api_version}"
        self.dry_run = dry_run
        self._dry_run_counter = 0

    def _request(self, method, endpoint, **kwargs):
        """Make an API request to the Meta Graph API."""
        url = f"{self.base_url}/{endpoint}"
        kwargs.setdefault("params", {})
        kwargs["params"]["access_token"] = self.access_token

        if self.dry_run:
            self._dry_run_counter += 1
            fake_id = f"dry_run_{self._dry_run_counter}"
            click.echo(click.style(f"  [DRY RUN] {method} {endpoint}", fg="yellow"))
            params = {k: v for k, v in kwargs.get("params", {}).items() if k != "access_token"}
            if params:
                preview = json.dumps(params, indent=2)
                if len(preview) > 500:
                    preview = preview[:500] + "..."
                click.echo(click.style(f"  Params: {preview}", fg="yellow"))
            if "files" in kwargs:
                click.echo(click.style(f"  Files: {list(kwargs['files'].keys())}", fg="yellow"))
            return {"id": fake_id}

        resp = getattr(requests, method.lower())(url, **kwargs)

        if resp.status_code != 200:
            try:
                error_data = resp.json().get("error", {})
                message = error_data.get("message", resp.text)
                error_code = error_data.get("code")
            except Exception:
                message = resp.text
                error_code = None
            raise MetaAPIError(resp.status_code, message, error_code)

        return resp.json()

    def upload_image(self, image_path):
        """Upload an ad image to the ad account. Returns the image hash."""
        with open(image_path, "rb") as f:
            result = self._request(
                "POST",
                f"{self.act_id}/adimages",
                files={"filename": (image_path.name, f, "image/png")},
            )

        if self.dry_run:
            return "dry_run_hash"

        images = result.get("images", {})
        for key, val in images.items():
            return val.get("hash")

        raise MetaAPIError(0, f"Unexpected image upload response: {result}")

    def create_campaign(self, name, objective="OUTCOME_TRAFFIC", status="PAUSED", special_ad_categories=None):
        """Create an ad campaign. Returns the campaign ID."""
        result = self._request(
            "POST",
            f"{self.act_id}/campaigns",
            params={
                "name": name,
                "objective": objective,
                "status": status,
                "special_ad_categories": json.dumps(special_ad_categories or []),
                "is_adset_budget_sharing_enabled": "false",
            },
        )
        return result.get("id", "dry_run_id")

    def create_ad_set(self, name, campaign_id, daily_budget, targeting, optimization_goal="LINK_CLICKS",
                      billing_event="IMPRESSIONS", bid_strategy="LOWEST_COST_WITHOUT_CAP", status="PAUSED"):
        """Create an ad set with targeting. Returns the ad set ID."""
        # Build targeting spec from config
        targeting_spec = {
            "age_min": targeting.get("age_min", 18),
            "age_max": targeting.get("age_max", 65),
            "genders": targeting.get("genders", [0]),
            "geo_locations": {
                "countries": targeting.get("countries", ["US"]),
            },
        }

        if targeting.get("interests"):
            targeting_spec["flexible_spec"] = [
                {"interests": targeting["interests"]}
            ]

        platforms = targeting.get("platforms", ["facebook", "instagram"])
        targeting_spec["publisher_platforms"] = platforms

        if "facebook" in platforms:
            targeting_spec["facebook_positions"] = targeting.get(
                "facebook_positions", ["feed"]
            )
        if "instagram" in platforms:
            targeting_spec["instagram_positions"] = targeting.get(
                "instagram_positions", ["stream", "story", "reels"]
            )

        result = self._request(
            "POST",
            f"{self.act_id}/adsets",
            params={
                "name": name,
                "campaign_id": campaign_id,
                "daily_budget": str(daily_budget),
                "billing_event": billing_event,
                "optimization_goal": optimization_goal,
                "bid_strategy": bid_strategy,
                "status": status,
                "targeting": json.dumps(targeting_spec),
            },
        )
        return result.get("id", "dry_run_id")

    def create_ad_creative(self, name, image_hash, primary_text, headline, description, link, cta="LEARN_MORE"):
        """Create an ad creative. Returns the creative ID."""
        result = self._request(
            "POST",
            f"{self.act_id}/adcreatives",
            params={
                "name": name,
                "object_story_spec": json.dumps({
                    "link_data": {
                        "image_hash": image_hash,
                        "link": link,
                        "message": primary_text,
                        "name": headline,
                        "description": description,
                        "call_to_action": {
                            "type": cta,
                            "value": {"link": link},
                        },
                    },
                    "page_id": self.page_id,
                }),
            },
        )
        return result.get("id", "dry_run_id")

    def create_ad(self, name, ad_set_id, creative_id, status="PAUSED"):
        """Create an ad linking a creative to an ad set. Returns the ad ID."""
        result = self._request(
            "POST",
            f"{self.act_id}/ads",
            params={
                "name": name,
                "adset_id": ad_set_id,
                "creative": json.dumps({"creative_id": creative_id}),
                "status": status,
            },
        )
        return result.get("id", "dry_run_id")

    def get_campaign(self, campaign_id, fields="name,status,objective"):
        """Get campaign details."""
        return self._request("GET", campaign_id, params={"fields": fields})

    def get_ad_account(self, fields="id,name,account_status,currency,timezone_name,amount_spent,balance"):
        """Get configured ad account details."""
        return self._request("GET", self.act_id, params={"fields": fields})

    def list_campaigns(self, fields="id,name,status,effective_status,objective,created_time,updated_time", limit=25):
        """List campaigns in the configured ad account."""
        result = self._request(
            "GET",
            f"{self.act_id}/campaigns",
            params={"fields": fields, "limit": str(limit)},
        )
        return result.get("data", [])

    def list_ad_sets(self, fields="id,name,status,effective_status,daily_budget,campaign_id", limit=25):
        """List ad sets in the configured ad account."""
        result = self._request(
            "GET",
            f"{self.act_id}/adsets",
            params={"fields": fields, "limit": str(limit)},
        )
        return result.get("data", [])

    def list_ads(self, fields="id,name,status,effective_status,adset_id,campaign_id", limit=25):
        """List ads in the configured ad account."""
        result = self._request(
            "GET",
            f"{self.act_id}/ads",
            params={"fields": fields, "limit": str(limit)},
        )
        return result.get("data", [])

    def get_ad_sets(self, campaign_id, fields="name,status,daily_budget"):
        """Get ad sets for a campaign."""
        result = self._request("GET", f"{campaign_id}/adsets", params={"fields": fields})
        return result.get("data", [])

    def get_ads(self, campaign_id, fields="name,status,effective_status"):
        """Get ads for a campaign."""
        result = self._request("GET", f"{campaign_id}/ads", params={"fields": fields})
        return result.get("data", [])

    def update_status(self, object_id, status):
        """Update the status of a campaign, ad set, or ad."""
        return self._request("POST", object_id, params={"status": status})

    def get_insights(
        self,
        object_id,
        fields="impressions,clicks,spend,cpc,cpm,ctr,actions",
        level=None,
        date_preset="last_7d",
        limit=25,
    ):
        """Get insights for an account, campaign, ad set, or ad."""
        params = {
            "fields": fields,
            "date_preset": date_preset,
            "limit": str(limit),
        }
        if level:
            params["level"] = level
        result = self._request("GET", f"{object_id}/insights", params=params)
        return result.get("data", [])

    def update_daily_budget(self, object_id, daily_budget_cents):
        """Update daily budget for a campaign or ad set."""
        return self._request(
            "POST",
            object_id,
            params={"daily_budget": str(daily_budget_cents)},
        )

    def delete_campaign(self, campaign_id):
        """Delete a campaign (sets status to DELETED)."""
        return self.update_status(campaign_id, "DELETED")
