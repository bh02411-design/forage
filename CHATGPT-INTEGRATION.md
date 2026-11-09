# Connect Forage to ChatGPT (private preview)

Forage now includes an **optional, read-only Model Context Protocol (MCP) bridge** in `mcp_bridge.py`. It gives ChatGPT access to decklists and owned collection cards without sending them to GitHub or turning the local Forage app into a public service.

This is **not** a replacement for the Forage chat interface and is **not** an OpenAI API integration. Your existing LM Studio settings remain unchanged. The bridge performs no AI inference and does not require paying for OpenAI model API calls. A Secure MCP Tunnel may require separate platform access and permissions.

## Available MCP tools

- `list_decks` — list current decks, IDs and mainboard counts.
- `get_deck` — read the mainboard, Considering board or complete deck, including card roles and Oracle metadata stored in Forage.
- `search_collection` — search and page through the owned collection with available/assigned copy counts.
- `card_availability` — check owned copies and assignments across all imported decks.
- `propose_swap` — **read-only preview** of an addition and cut, including ownership, Commander legality if known, and color-identity warnings. It does **not** save or apply a change.

All exposed actions are read-only. No ChatGPT tool can import, delete, update or otherwise mutate your workspace in this version. This is intentional until end-to-end authentication and access are verified.

## Start locally

1. Update or install Forage normally and keep it running on your Windows PC. This preview requires `mcp_bridge.py` from this branch or a future release that contains it.
2. In the Forage program folder, run `python mcp_bridge.py` **only when your MCP transport launches it**. It communicates over standard input/output; typing directly in its terminal is not a chat interface.
3. Forage defaults to `127.0.0.1:8765`. If its port is different, set the `FORAGE_PORT` environment variable for the MCP bridge process. The bridge always calls the loopback address.

To verify locally with Python (no ChatGPT account needed):

```bash
python -m unittest discover -s tests -p 'test_mcp_bridge.py'
```

## Use ChatGPT with Secure MCP Tunnel

See the current official setup guide:

https://developers.openai.com/api/docs/guides/secure-mcp-tunnels

Use the **stdio** mode of `tunnel-client`, with your installed Python interpreter and the absolute path to `mcp_bridge.py` as the MCP command. Follow the current `tunnel-client help quickstart` instructions, and configure your tunnel ID and runtime credential **locally**, never in the repo, a screenshot, or a chat message.

In ChatGPT on the **web**, open **Plugins → + → Add custom MCP server**, choose **Tunnel**, then select the tunnel associated with your account/workspace, if that functionality is available to you. Review the security warning and create the private plugin. It must pass tool discovery and successfully call `list_decks` before considering the integration live.

The tunnel runs outbound from your PC and avoids an inbound public port. **Do not expose Forage's port 8765 directly to the internet** or forward the local `/api/state` endpoint through a generic HTTP tunnel; it contains workspace data and a local mutation token. Only run the isolated MCP bridge through a trusted tunnel.

Custom MCP creation and private tunnel entitlements vary by ChatGPT account/workspace; the repository cannot provision those on your behalf. Installing this code alone does not connect ChatGPT.

## Privacy and limits

- The MCP tool responses include the deck and collection information that you request in ChatGPT. They are not anonymous or made public, but they do leave your PC when you use the tool.
- `mcp_bridge.py` does **not** return Forage settings, local CSRF token, chat history, saved memories, or deleted decks.
- The bridge reads a dedicated local `/api/mcp-state` snapshot instead of the full `/api/state` browser payload. This excludes unrelated workspace data before loading it and avoids the previous 12 MB full-workspace failure. A 64 MB local snapshot safety limit remains; the tunnel receives only each filtered tool result.
- Both the Forage server and `mcp_bridge.py` need updating. Restart Forage and the MCP tunnel after installing the updated version.
- Access remains available while Forage and your MCP tunnel are running. If either stops, ChatGPT cannot read live data.
- The bridge only checks whatever collection you imported; physical ownership and the legality metadata may be incomplete.
- `propose_swap` checks one-for-one changes, not whole-deck consistency, replacement category or full Commander legality. It intentionally provides advisory results rather than applying changes.
- Full automated edits should come later, behind explicit confirmation, current-deck version checks, backup/undo, and stronger user-specific authorization.
