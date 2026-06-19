# meta-ads-cli

Create and manage Meta (Facebook/Instagram) ad campaigns from your terminal.

> Built by [Attainment Labs](https://attainmentlabs.com)

## Status in the Meta Ads ecosystem

This is an early independent open source Meta Ads CLI, first published in February 2026 before Meta later introduced its official Ads AI Connectors and Ads CLI.

Use Meta's official connector if you want Meta-hosted OAuth and first-party support. Use this project if you want a lightweight, self-managed, scriptable CLI that you can inspect, fork, and run inside your own workflow.

Related:

- [Meta's official Ads CLI documentation](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli/ads-cli-overview)
- [Attainment's companion MCP server](https://github.com/attainmentlabs/meta-ads-mcp)
- [Meta Ads Automation Playbook](https://attainmentlabs.com/meta-ads-playbook)

## Why

Meta Ads Manager is slow. Clicking through 15 screens to launch a campaign is a waste of time when you already know what you want to run.

This tool lets you define a campaign in a YAML file and deploy it with one command.

```
meta-ads create --config campaign.yaml
```

One campaign. One ad set. Multiple ads. All created in seconds. You also get account lookup, campaign listings, insights, budget updates, bulk status operations, setup snippets, spend limits, and local audit logs.

## Install

```bash
pip install meta-ads-cli
```

Or install from source:

```bash
git clone https://github.com/attainmentlabs/meta-ads-cli.git
cd meta-ads-cli
pip install -e .
```

## Quick Start

**1. Set up your credentials**

```bash
cp .env.example .env
# Edit .env with your Meta access token, ad account ID, and page ID
```

**2. Create your campaign config**

```bash
cp campaign.example.yaml campaign.yaml
# Edit campaign.yaml with your ad copy, images, targeting, and budget
```

**3. Validate your config**

```bash
meta-ads validate --config campaign.yaml
```

**4. Preview with dry run**

```bash
meta-ads create --config campaign.yaml --dry-run
```

**5. Deploy**

```bash
meta-ads create --config campaign.yaml
```

Your campaign is created as PAUSED by default. Review it in Ads Manager, then activate it when ready.

## Configuration

### Environment Variables

Create a `.env` file in your project root (or export these in your shell):

| Variable | Required | Description |
|----------|----------|-------------|
| `META_ACCESS_TOKEN` | Yes | Your Meta API access token |
| `META_AD_ACCOUNT_ID` | Yes | Your ad account ID (numbers only, no `act_` prefix) |
| `META_PAGE_ID` | Yes | Your Facebook Page ID |
| `META_API_VERSION` | No | API version (default: `v21.0`) |
| `META_ADS_MAX_DAILY_BUDGET_CENTS` | No | Optional daily budget guardrail |
| `META_ADS_AUDIT_LOG_PATH` | No | Optional JSONL audit log path |

### Campaign Config (YAML)

Your campaign is defined in a single YAML file. Here is the full schema:

```yaml
campaign:
  name: "My Campaign"
  objective: OUTCOME_TRAFFIC        # See objectives below
  status: PAUSED                    # PAUSED or ACTIVE
  special_ad_categories: []         # Leave empty unless required

ad_set:
  name: "My Ad Set"
  daily_budget: 1000                # In cents. 1000 = $10/day
  optimization_goal: LINK_CLICKS    # See optimization goals below
  targeting:
    age_min: 18
    age_max: 65
    genders: [0]                    # 0 = all, 1 = male, 2 = female
    countries: ["US"]
    interests:                      # Optional
      - id: "6003139266461"
        name: "Fitness and wellness"
    platforms: ["facebook", "instagram"]
    facebook_positions: ["feed"]
    instagram_positions: ["stream", "story", "reels"]

ads:
  - name: "My Ad"
    image: ./images/ad.png          # Path relative to YAML file
    primary_text: "Your ad copy."
    headline: "Your Headline"
    description: "Short description"
    cta: LEARN_MORE                 # See CTAs below
    link: "https://example.com"
```

**Campaign Objectives:** `OUTCOME_TRAFFIC`, `OUTCOME_AWARENESS`, `OUTCOME_ENGAGEMENT`, `OUTCOME_LEADS`, `OUTCOME_SALES`, `OUTCOME_APP_PROMOTION`

**Optimization Goals:** `LINK_CLICKS`, `IMPRESSIONS`, `REACH`, `LANDING_PAGE_VIEWS`, `APP_INSTALLS`, `OFFSITE_CONVERSIONS`, `LEAD_GENERATION`

**CTA Options:** `LEARN_MORE`, `SIGN_UP`, `DOWNLOAD`, `SHOP_NOW`, `BOOK_NOW`, `GET_OFFER`, `SUBSCRIBE`, `CONTACT_US`, `APPLY_NOW`, `WATCH_MORE`

## Commands

### `meta-ads setup`

Print local MCP setup snippets for Claude, Cursor, Codex, or ChatGPT.

```bash
meta-ads setup --client claude
meta-ads setup --client cursor
meta-ads setup --client codex
meta-ads setup --client chatgpt
```

ChatGPT requires a hosted MCP endpoint. Until that ships, the command prints the local config and notes the hosted requirement.

### `meta-ads create`

Create a full campaign from your YAML config.

```bash
# Preview first
meta-ads create --dry-run

# Deploy (will ask for confirmation)
meta-ads create

# Deploy without confirmation
meta-ads create --yes

# Use a custom config file
meta-ads create --config path/to/campaign.yaml
```

### `meta-ads status <campaign-id>`

Check the status of a campaign and all its ads.

```bash
meta-ads status 120243616427570285
```

### `meta-ads account`

Show the configured ad account.

```bash
meta-ads account
meta-ads account --json-output
```

### `meta-ads campaigns`

List recent campaigns.

```bash
meta-ads campaigns --limit 25
meta-ads campaigns --json-output
```

### `meta-ads adsets`

List recent ad sets.

```bash
meta-ads adsets --limit 25
```

### `meta-ads ads`

List recent ads.

```bash
meta-ads ads --limit 25
```

### `meta-ads insights`

Pull account, campaign, ad set, or ad insights.

```bash
meta-ads insights --level campaign --date-preset last_7d
meta-ads insights 120243616427570285 --date-preset last_30d --json-output
```

### `meta-ads budget <object-id> <daily-budget-cents>`

Update daily budget for a campaign or ad set. This defaults to dry run.

```bash
meta-ads budget 120243616427570285 3000
meta-ads budget 120243616427570285 3000 --live
meta-ads budget 120243616427570285 3000 --live --yes
```

If `META_ADS_MAX_DAILY_BUDGET_CENTS` is set, updates above that cap are blocked.

### `meta-ads upload-image <image-path>`

Upload an image and return its Meta image hash. This defaults to dry run.

```bash
meta-ads upload-image ./images/ad.png
meta-ads upload-image ./images/ad.png --live
meta-ads upload-image ./images/ad.png --live --yes
```

### `meta-ads bulk-status <status> <campaign-id...>`

Bulk pause, activate, or delete campaigns. This defaults to dry run.

```bash
meta-ads bulk-status PAUSED 111 222 333
meta-ads bulk-status ACTIVE 111 222 333 --live
meta-ads bulk-status DELETED 111 222 333 --live --yes
```

### `meta-ads pause <campaign-id>`

Pause a running campaign.

```bash
meta-ads pause 120243616427570285
```

### `meta-ads activate <campaign-id>`

Activate a paused campaign. This starts spending your budget.

```bash
meta-ads activate 120243616427570285
```

### `meta-ads delete <campaign-id>`

Permanently delete a campaign.

```bash
meta-ads delete 120243616427570285
```

### `meta-ads validate`

Validate your YAML config without making any API calls.

```bash
meta-ads validate --config campaign.yaml
```

## Safety controls

- Campaigns are created as `PAUSED` by default.
- `meta-ads budget`, `meta-ads upload-image`, and `meta-ads bulk-status` default to dry run.
- Live budget, media upload, and bulk operations require `--live`, with an interactive confirmation unless `--yes` is passed.
- `META_ADS_MAX_DAILY_BUDGET_CENTS` blocks budget changes above your chosen cap.
- Mutating commands write JSONL audit events. Default path: `~/.meta-ads-cli/audit.jsonl`.

## Automation

Built for scripting. Mutating commands take `--yes` to skip the prompt, read commands take `--json-output` for machine-readable output, and every command exits non-zero on failure, so it drops into shell scripts, cron, or CI cleanly.

Create many campaigns from a folder of configs:

```bash
for cfg in campaigns/*.yaml; do
  meta-ads create --config "$cfg" --yes
done
```

Pipe results into other tools:

```bash
meta-ads campaigns --json-output | jq '.[] | {id, name, status}'
meta-ads insights --level campaign --date-preset last_7d --json-output > insights.json
```

`--date-preset` accepts any Meta preset (`yesterday`, `last_7d`, `last_30d`, and so on).

Guardrails still apply unattended: campaigns create as `PAUSED`, `META_ADS_MAX_DAILY_BUDGET_CENTS` caps budget changes, and every mutating run appends a JSONL audit event.

## Getting a Meta Access Token

This is the part most people get stuck on. Here is the short version:

1. Go to [Meta for Developers](https://developers.facebook.com/) and create an app (type: Business)
2. Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
3. Select your app, then request these permissions: `ads_management`, `pages_read_engagement`, `pages_show_list`
4. Click "Generate Access Token" and authorize
5. Copy the token to your `.env` file

**Important:** Graph API Explorer tokens expire after about 2 hours. For production use, exchange it for a long-lived token:

```bash
curl "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=YOUR_APP_ID&\
client_secret=YOUR_APP_SECRET&\
fb_exchange_token=YOUR_SHORT_LIVED_TOKEN"
```

Long-lived tokens last about 60 days.

## Finding Interest IDs

Interest targeting requires Meta's internal IDs. Search for them using the API:

```bash
curl "https://graph.facebook.com/v21.0/search?\
type=adinterest&\
q=fitness&\
access_token=YOUR_TOKEN"
```

This returns interest names and IDs you can use in your campaign YAML.

## Examples

See the [`examples/`](examples/) directory for ready-to-customize campaign configs:

- **[ecommerce.yaml](examples/ecommerce.yaml)**: Product launch targeting skincare enthusiasts
- **[app-install.yaml](examples/app-install.yaml)**: Mobile app install campaign for fitness users

## How It Works

This tool wraps the [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis/) with `requests`. No heavy SDKs. The full chain:

1. Uploads your ad images to your ad account
2. Creates a campaign with your objective
3. Creates an ad set with your budget and targeting
4. Creates ad creatives linking your images and copy
5. Creates ads linking creatives to the ad set

Everything is created as `PAUSED` by default so you can review before spending.

## Want the Full Playbook?

We wrote a free guide covering Meta Ads AI automation end to end: when to use CLI, when to use MCP, OAuth setup walkthrough, audience segmentation strategy, budget allocation frameworks, creative testing, scaling rules, and common API errors with fixes.

**[Get the Guide: The Engineer's Playbook for Meta Ads](https://attainmentlabs.com/meta-ads-playbook)**

## Contributing

PRs welcome. Keep it simple. This tool is intentionally lightweight.

```bash
git clone https://github.com/attainmentlabs/meta-ads-cli.git
cd meta-ads-cli
pip install -e .
meta-ads --help
```

## License

MIT. See [LICENSE](LICENSE).
