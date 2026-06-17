# Meta Ads CLI Parity Roadmap

This repo is the independent open source Meta Ads CLI. Meta now has the official Ads AI Connectors path and Ads CLI. The goal is to keep the independent version useful for operators who want a scriptable, inspectable, forkable workflow.

## Shipped in this track

- Broader command coverage: account, campaigns, adsets, ads.
- Reporting: insights by account, campaign, ad set, or ad.
- Media: standalone image upload command.
- Budget control: daily budget updates with dry-run default.
- Bulk operations: campaign status updates across many campaign IDs.
- Safety: live confirmations, daily budget cap, audit log.
- Client setup helpers: Claude, Cursor, Codex, and ChatGPT guidance.

## Next parity layer

| Capability | Status | Notes |
|---|---|---|
| Hosted MCP endpoint | Companion MCP | Belongs in the MCP repo, with CLI docs pointing to it. |
| OAuth login | Planned | Replace manual token setup with Meta OAuth flow. |
| Official-style command groups | In progress | Keep adding account, campaign, adset, ad, creative, insight, and setup verbs. |
| One-click Claude setup | Shipped local | Generates a local config block. |
| One-click ChatGPT setup | Blocked by hosted MCP | Requires a remote endpoint before it can be one-click. |
| One-click Cursor setup | Shipped local | Generates a local config block. |
| One-click Codex setup | Shipped local | Generates a local config block. |
| More API coverage | Planned | Add pages, pixels, custom audiences, catalog, creative library, previews, recommendations, and rules. |
| Approval workflow UI | Companion MCP | Best handled by hosted MCP plus a lightweight review page. |

## Non-copyable Meta advantages

- First-party Meta trust.
- Meta-hosted OAuth brand trust.
- Official platform support.
- Direct Meta roadmap access.

## Positioning

Meta is the institutional path. This project is the operator path: scriptable, forkable, self-managed, and conservative by default.
