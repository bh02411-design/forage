# Connect Forage to ChatGPT (private bridge)

Forage now includes an **optional Model Context Protocol (MCP) bridge** in `mcp_bridge.py`. It gives ChatGPT access to decklists and owned collection cards without sending them to GitHub or turning the local Forage app into a public service.

This is **not** a replacement for the Forage chat interface and is **not** an OpenAI API integration. Your existing LM Studio settings remain unchanged. The bridge performs no AI inference and does not require paying for OpenAI model API calls. A Secure MCP Tunnel may require separate platform access and permissions.

## Available MCP tools

- `list_decks` — list current decks, IDs and mainboard counts.
- `get_deck` — read the mainboard, Considering board or complete deck, including card roles and Oracle metadata stored in Forage.
- `search_collection` — search and page through the owned collection with available/assigned copy counts.
- `card_availability` — check owned copies and assignments across all imported decks.
- `propose_swap` — **read-only advisory preview** of an addition and cut. It does **not** save or apply a change.
- `preview_deck_swap` — **strict read-only preview** against the local app, checking 100-card count, ownership, commander legality and color identity, protected cuts, duplicate names, and returning a SHA-256 of the current deck.
- `apply_deck_swap` — write-enabled one-for-one swap, requiring user approval and the exact preview deck SHA. Verifies the current deck has not changed, saves a local SQLite backup, preserves existing custom categories/history, and checks the final deck.

The bridge also offers opt-in local write capabilities after this release is installed:

- `preview_collection_import` parses a complete Forage text import and returns existing/incoming quantities plus SHA-256 values without making any changes.
- `apply_collection_import` replaces the **entire** collection only after an explicit user confirmation and the exact matching preview hashes. The server rejects stale previews if the collection or import text changed. It saves a full SQLite backup under `data/mcp-backups/` before replacement. Existing deck lists and assignments are not rewritten.
- `preview_collection_change` supports `add`, `decrease`, `remove`, and `append`. Add and decrease take an exact card name and a copy count. Remove takes a card name and removes all owned copies. Append takes collection export text and adds the listed quantities to existing ownership.
- `apply_collection_change` takes the same operation and inputs, both hashes returned by preview, and `confirm: true` after explicit approval of that preview. Forage backs up SQLite before saving and verifies the saved collection. The local Collection screen uses the same review and backup flow.
- `create_deck_version` saves a named deck snapshot in the existing local saved-version database.

The write tools are still accessible **only through the private stdio MCP tunnel**. The bridge obtains a scoped token from the loopback-only `/api/mcp-auth` endpoint. This endpoint returns only the token and does not load workspace data. The token is restricted to the MCP operation routes and is never included in MCP results. It does not open a public port. Neither a preview nor a request to save a version grants blanket approval for collection replacement. Do not call `apply_collection_import` without approval for the specific import.

**Deployment:** Update Forage to a version that contains the new `/api/mcp-collection-import` and `/api/mcp-deck-swap` routes; replace any standalone copy of `mcp_bridge.py` used by your tunnel; restart the tunnel and refresh tool discovery. No live data is included in the GitHub release. If your custom MCP plugin caches the old tool set, refresh/reconnect it. Collection import text must fit Forage's 12 MiB POST limit.

Other write actions (separate add/remove operations, sleeve tags, restores) are **not yet exposed**. Continue using Forage's local UI for those operations until separately reviewed and tested.

## Remote application updates (opt-in)

After the first local upgrade of **both** Forage and the MCP bridge, ChatGPT can use:

- `check_updates` — check the configured trusted GitHub releases; does not install anything.
- `update_status` — read current/pending versions and rollback availability.
- `install_update` — with explicit user approval and the exact version found by a fresh check, download, verify hashes, check compatibility, and stage the latest release. Does not restart Forage.
- `restart_forage` — with separate explicit approval for the exact staged version, ask the existing launcher to restart Forage. A restarted app may interrupt the MCP connection; verify `list_decks` once the tunnel reconnects.

The bridge never accepts arbitrary URLs, repository changes, ZIP uploads, older version targets, or rollback requests. The application updater's existing release validation, compatibility checks, startup recovery and backup behavior remain authoritative.

**Windows deployment:** The v0.2.48 installer includes the bridge alongside `launcher.py`. For the default installer location, configure the existing Secure MCP Tunnel stdio command to use `%LOCALAPPDATA%\Programs\Forage\runtime\python.exe` with `%LOCALAPPDATA%\Programs\Forage\mcp_bridge.py` as its script argument. Use expanded absolute paths in the profile and preserve its existing tunnel ID and credentials. If you use the ZIP or the in-app updater, download the [matching bridge](https://raw.githubusercontent.com/bh02411-design/forage/v0.2.48/mcp_bridge.py) separately and point the profile to that file. Restart the tunnel process, then select **Refresh Tools** for the existing Forage plugin in ChatGPT. Reload ChatGPT or start a new chat to check the refreshed catalog. You should see 14 tools. If you see only the original eight, check the absolute path of the running bridge first. The bridge lists its tools even when Forage is stopped, so a large workspace cannot reduce discovery to eight tools. Future application updates and launcher restarts do not replace or restart an independently deployed bridge.

## Start locally

1. Update or install Forage normally and keep it running on your Windows PC. The bridge requires Forage v0.2.48 or newer for its authorized routes.
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
- The bridge prefers the compact local `/api/mcp-state` snapshot, which excludes unrelated workspace data before sending it to the bridge. On older Forage builds that return HTTP 404 for that route, the bridge reads the local browser endpoint and keeps only the fields the tools use. The tunnel receives only the filtered tool results.
- The local read limit defaults to 64 MiB. For larger workspaces, set `FORAGE_MCP_MAX_MIB` in the tunnel client's environment before starting it. The bridge accepts limits from 64 through 128 MiB.
- If your tunnel profile runs a standalone copy of `mcp_bridge.py`, replace that copy and restart the tunnel with the existing profile. Updating Forage itself enables the compact endpoint if your version lacks it.
- Access remains available while Forage and your MCP tunnel are running. If either stops, ChatGPT cannot read live data.
- The bridge only checks whatever collection you imported; physical ownership and the legality metadata may be incomplete.
- `propose_swap` checks one-for-one changes, not whole-deck consistency, replacement category or full Commander legality. It intentionally provides advisory results rather than applying changes.
- Other automated edits should follow with their own scope, explicit confirmations, current-deck version checks, and backup/undo. The current collection import checks the collection hash at apply time and backs up the entire database. Deck swaps use the same backup approach and enforce a fresh deck hash.
