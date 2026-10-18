# Forage

A local-first Commander deck builder with collection-aware AI, editable preferences, image/link drops, visual card categories, and verified application updates. New workspaces start empty. Decks, collection, chats and saved preferences live in the local `data` folder.

## Install and start

Extract the application into a writable folder. Install Python 3.10 or newer if needed, then run **Start-Forage.bat** on Windows. No pip dependencies are required. Keep its terminal open. On macOS/Linux run `python3 launcher.py --open`. Forage serves only on `127.0.0.1`, normally port 8765. Use `--port 8766` if needed.

Import a deck and collection separately. Use **Resolve card data** to retrieve Oracle text, costs, colors, power and images from Scryfall. Collection lookups run in resumable batches; unknown facts remain unknown. Import other decks to account for assigned physical copies. Membership in a deck is not proof of ownership.

## Local AI

Load a chat model in LM Studio and start its local server. Open **Local AI & settings**, use `http://127.0.0.1:1234/v1`, list the models, choose one and save. Only loopback HTTP AI endpoints are accepted. The application does not connect to paid cloud inference.

Requests include the active deck, saved preferences, recent conversation, relevant earlier excerpts and collection search results. Only Commander legality is included in model context. Explicit ranges such as 2–3 CMC filter collection candidates before retrieval. Automatic prompt compaction trims irrelevant per-card metadata and repeated evidence before conversation history, preserves the full roster and saved preferences, and adapts to context-overflow errors. Model reasoning quality still varies. See **LOCAL-MODEL-CHECK.md** for live tests.

Ability searches match Oracle words rather than card-name fragments or editable role tags. Existing mainboard/commander cards are excluded from addition searches except explicit ownership lookups. Known off-color and banned cards are filtered. Unknown metadata and unavailable copies are flagged. Search ordering is a retrieval hint, not a strategic rating.

Structured additions and swaps are checked against supplied facts, ownership, availability, current membership, known identity/legality, costs and protected cuts. Draw recommendations require a manifest or an explanation of insufficient evidence. An invalid answer gets one correction attempt and is then withheld if still invalid. These checks do not prove every prose claim or strategic conclusion. **Context used** exposes actual messages, searches and checked evidence.

## Working with cards

Switch between stacks, grid and list; group by category, type, mana or color. Category headings support rename/create/move/merge operations. AI changes are proposals until you apply them. Undo restores prior deck edits. Role tags support overlapping functions independently of display categories. Considering is separate from the mainboard.

Drop Scryfall/EDHREC card links or image drags with recognizable identity into the deck or composer. Review recognized names before adding. Screenshot recognition needs a local vision model; manual names also work. Cross-site drag behavior depends on the browser.

Explicit preference statements produce a **Remember** suggestion. Save it to retain the preference across conversations. Memories can apply to one deck or globally and can be edited or deleted. A bare yes/no is not automatically saved as a permanent preference.

Use Backup to export the local workspace. Restore creates an additional local copy before replacing data. No live database, chat history, personal deck export or local preferences belong in this repository or a release asset.

## Updates

The default release repository is `bh02411-design/forage`. Open **Local AI & settings → Application updates** to change the trusted public source, check now, or enable checks on launch. No GitHub credentials are stored. Only repository/version requests go to GitHub; local workspace contents are not uploaded.

**Update and restart** verifies the GitHub asset SHA-256, manifest, individual hashes, supported paths, version and Python syntax. The launcher stops the server before replacing application files. The allowlist excludes `data`. Previous code and a SQLite workspace snapshot are retained in `data/updates/backups`.

Interrupted installation is recovered before launching. If the updated server fails its startup check, the previous code is restored. **Roll back application** restores code while preserving current workspace data. Snapshots are available for manual recovery. Format-1 releases must remain compatible with the existing database; schema-breaking migrations need a separate upgrade path.

Checksums verify integrity relative to the configured release source; they are not independent publisher signatures. Trust that repository. Start with the launcher, not `server.py`, to enable supervised installation. Wait for active conversations/imports to finish before restarting.

For the one-time updater installation, stop Forage, replace program files from the downloaded bootstrap ZIP, preserve the existing `data` folder, and launch **Start-Forage.bat**. Existing local decks, chats and memories remain unchanged. Older installations with a saved empty release source should enter `bh02411-design/forage` once.

## Development and releases

The repository root contains the application. `.gitignore` excludes local data, caches, databases and builds. The bundled tests use synthetic workspaces, not personal deck snapshots.

Run:

```sh
python -m unittest discover -s tests -p 'test*.py'
node --check static/app.js
node tests/test_cards.cjs
node tests/test_render.cjs
python build_release.py --output dist/Forage-update.zip
```

Increase the stable version in `version.json` before a release. Pushing that version change to `main` automatically tests and publishes the update. You can also push a matching `vMAJOR.MINOR.PATCH` tag or use **Actions → Test and publish Forage release → Run workflow**. The workflow tests, builds and publishes `Forage-update.zip` using the repository's built-in token. The updater requires GitHub to supply a SHA-256 digest for the release asset. Application releases contain code only.

Lifecycle tests cover installation, restart, manual rollback, failed-server recovery, archive rejection, and preservation of live data. Supervisor process tests run in Linux CI; Windows launch and live GitHub downloads also need environment-specific verification.

### Visual recommendations

New checked AI additions appear as card graphics beneath the reply. Inspect a card by clicking its artwork. Use **Find a swap** to ask for a cut, **Accept swap** to apply it, **Different cut** to keep the addition and request an alternative, or **Pass** to record your decision. You can also add an unswapped suggestion to Mainboard or save it to Considering. Proposed additions and cuts appear side by side; nothing is changed until you choose an action. Accepted swaps support Undo. Artwork uses resolved local card data and does not consume model context. Unresolved artwork shows a named placeholder; unranked search fallbacks appear as graphical **Collection matches**, with the same inspection and decision controls, rather than being presented as ranked recommendations.

Pending suggestions are accessible through **Pending decisions** in the chat header. The count combines unresolved card choices, swaps and category plans without counting a card and its swap twice. The former On the table section has been removed, so analytics sit directly beneath the workspace.

### Update history and version switching

Open **Local AI & settings → Application updates → Update history & versions** to see release changes, your installed version and verified stable packages. After updating from 0.2.8 or earlier, close Forage and reopen **Start-Forage.bat** once to activate the new launcher.

Selecting a version opens a review screen. Switching verifies the release hashes and workspace-format compatibility before changing application files, then saves previous application files and a SQLite workspace snapshot under `data/updates/backups/`. Application rollback also snapshots the current workspace under `data/updates/rollback-snapshots/`. Your live workspace is preserved; a version switch does not restore old deck data. Future releases must explicitly declare supported workspace formats. Known releases 0.2.0–0.2.8 use workspace format 1. An older release restores its earlier interface; its Application updates screen can install the latest release again.

History uses published releases from your configured GitHub repository. Cached history and bundled notes remain readable when GitHub is unavailable; downloading another release still requires connectivity. Keep using a repository you trust.

### Changelog

**0.2.30**

- Hide chat from its header or the board toolbar to give the board full width. Reopen with Show chat. Uses the saved per-deck view preference and restores the latest conversation when reopened.

**0.2.29**

- Remove Mainboard/Considering labels from cards in shared Swap In and Swap Out categories and their category editor. Present the section as Swap staging, separate from both board totals.

**0.2.28**

- Exclude Swap In and Swap Out cards from Mainboard and Considering totals, including renamed swap categories. Keep each staging category’s own count visible.
- Use the unstaged mainboard plus commander for deck size, curve, roles and mana comparison statistics. Returning a card to an ordinary category counts it again.

**0.2.27**

- Collapse the desktop sidebar to an icon rail with the arrow button; expand it again at any time. Your preference is remembered on this browser.
- Navigation and settings remain accessible with tooltips; smaller screens keep their full horizontal menu.

**0.2.26**

- Show commander-identity colors only in mana comparison stats; combine all assigned commanders. Show colorless when production/cost uses it, or for colorless commanders.
- Keep all colors visible when commander identity is unresolved. Visible color cards fill the panel width, and displayed percentages normalize to visible colors.

**0.2.25**

- Move Mana cost vs production, including Optimize basics, above the mana curve and role panels.

**0.2.24**

- Add the branded green Forage favicon to browser tabs. The scalable icon is bundled directly in the page and matches the Windows tray mark.

**0.2.23**

- Add mana cost versus potential production statistics, W/U/B/R/G/C breakdowns, and a mana-permanents toggle. Counts use Mainboard + commander and explicitly separate potential color coverage from simultaneous production.

- Add Optimize basics to the Mana cost vs production panel header. Preview changes to ordinary basics using colored casting-cost demand, optional early weighting and fixed direct land sources.
- Keep total basics and deck size constant. Preserve nonbasics, snow basics, Wastes, protected copies and Considering. Collection-only mode requires confirmed copies for increases.
- Apply a reviewed suggestion in one undoable edit; reject stale previews and missing required metadata. See the modal’s methodology for heuristic limits.

**0.2.22**

- Show the same pinned Swap In and Swap Out cards on Mainboard and Considering, with source-board labels.
- Moving existing cards into the shared categories preserves their board assignment. Collection drops into these categories enter Considering; moving a card explicitly to a board tab still changes its assignment.
- Board counts include only cards actually assigned to the selected board. Ordinary categories remain scoped to that board; shared categories retain normal editing and Undo.

**0.2.21**

- Use a focused prompt for cut reviews. Accept clear numbered/bulleted removal lists, tables and common structured field aliases; validate the resulting candidates normally.
- Preserve local-model format failures under Context used diagnostics, clearly marked as unverified, instead of exposing internal schema requirements in chat.

**0.2.20**

- Enlarge clicked-card dialogs, with a large artwork column and editing controls beside it; use a single-column view on smaller screens.

- Pin Swap In and Swap Out as real categories in a separate right-hand Mainboard column. They remain visible across grouping, sorting and filtering; smaller screens place them beneath the board.
- Support normal category movement, naming, bulk selection/removal and Undo. Cards in these categories are Mainboard entries and count toward deck totals. Rename preserves pinning; the two pinned categories cannot be deleted or merged together.
- Hide empty ordinary category placeholders; preserve category definitions for later use.

**0.2.19**

- Distinguish requests for cuts from requests for additions, including cuts to make room for draw spells.
- Scope cuts to Mainboard and check unique names, requested count and protection flags. Display verified names and mana values with model-provided tradeoffs.
- On cut failures, explain the failure without substituting collection additions. Suggestions never remove cards automatically.

**0.2.18**

- Add compact roster rows for large Mainboard/Considering prompts, retaining all entries, mana values, roles, categories, quantities and protection flags.
- Reduce pending-plan and decision detail before shortening conversation; preserve the current question and latest exchange. Saved data stays unchanged.
- Correct misleading prompt-budget errors and add roster coverage to context diagnostics.

**0.2.17**

- Fix manually created Uncategorized categories blocking the Auto-categorize button. Explicit auto-categorizing resets unassigned categories; automatic board entry continues to preserve manual choices.

- Auto-categorize now retrieves missing rules text and card types from Scryfall in batches, using saved data and cache first. Card images alone are not sufficient metadata.
- Show busy status and retrieval failures; retain custom categories, board scope and one-step Undo. Offline requests still categorize cards with saved data.

**0.2.16**

- Add Select all, partial-selection counts and board labels in Edit category.
- Remove selected entries (all their copies) from the deck with one-step Undo. Collection ownership is unchanged; protected cards and commanders cannot be bulk removed.

**0.2.15**

- Add seven collection sort options and ascending/descending controls.
- Remember sort choices and keep missing metadata at the end.

**0.2.14**

- Add local Scryfall-style filters and clickable syntax keys to deck and collection search.
- Keep unknown metadata distinct from negative results, and show errors for unsupported fields.

**0.2.13**

- Add the branded green Forage tray icon. Quit and reopen Forage once after updating to load the new icon.

**0.2.12**

- Add Windows tray mode and optional startup at sign-in.
- Add in-app setup, a Start-menu shortcut and background logging.

**0.2.11**

- Automatically categorize unassigned cards entering Mainboard or Considering.
- Add an undoable Auto-categorize button; retain custom assignments.

**0.2.10**

- Render prose-prefixed, fenced and nested AI JSON as readable chat.
- Preserve embedded swap proposals for validation and graphical decisions instead of displaying internal fields.

**0.2.9**

- Add Update history with readable changes, installed-version labels and stable-release selection.
- Check workspace compatibility and create a workspace snapshot before switching or rolling back.

**0.2.8**

- Move pending card choices, swaps and category plans into the chat header.
- Remove the duplicate On the table section and bring analytics up.

**0.2.7**

- Display unranked collection-search fallbacks as graphical card options with decision controls.

**0.2.6**

- Display checked recommendations and proposed cuts as cards inside the conversation.
- Add inspection, Considering, swap acceptance, different-cut requests and passing.

**0.2.5**

- Reduce repeated card metadata in AI prompts while preserving conversation context.
- Honor explicit mana-value ranges in collection searches.

**0.2.4**

- Open conversations at the latest reply and preserve your position when reading older messages.

**0.2.3**

- Keep commanders at the top left across grouping and sorting modes.

**0.2.2**

- Move card quantities to the top left and widen the gap between deck and chat.

**0.2.1**

- Earlier updater release; see its GitHub release notes for details.

**0.2.0**

- Introduce supervised GitHub release installation, application backups and startup recovery.


Mainboard and Considering use existing categories where possible, based on saved roles, then card text, then card type. These defaults are editable presentation heuristics. Unresolved cards stay Uncategorized until metadata is available. Adding, moving, importing and resolving cards all use this behavior. Each board’s Auto-categorize button organizes existing unassigned cards on that board without changing custom categories; Undo restores the prior board. No AI request is needed.

### Windows tray and startup

After updating, open **Local AI & settings → Windows tray & startup**, choose whether to start at Windows sign-in, and click **Save & run in tray**. The existing server hands off to a background launcher using the same data folder. Close the old console if it remains open. Future launches through **Start-Forage.bat** also start the tray service and return immediately. A **Forage** shortcut is created in your Start menu.

Double-click the tray icon to open the browser. Right-click it for **Open Forage**, **Start with Windows**, or **Quit Forage**. Closing the browser leaves the server running. Sign-in starts the service quietly without opening the browser. Startup uses the current user’s registry Run entry `ForageLocalDeckBuilder`; disabling it from the tray or setup removes only that entry. No administrator privileges or pip packages are required. Windows PowerShell, .NET Windows Forms and Python’s `pythonw.exe` supply the native tray UI.

Logs are written to `data/forage.log` (or your configured data directory); the previous log is retained as `forage.previous.log` when it exceeds 2 MB on launch. Only one tray launcher owns a data directory and port. A small launcher bootstrap and fallback are retained under `data/desktop/` so tray startup remains available when switching to an earlier application version. Update supervision continues in tray mode. Quit waits for active requests before stopping the server; older app releases without the shutdown endpoint are terminated when quitting their tray launcher. Windows tray appearance, startup registration and shortcuts need verification on Windows; automated CI runs on Linux.

### Search syntax

Deck and collection filters support common Scryfall-style syntax: `o:draw`, `o:"sacrifice a creature"`, `t:creature`, `mv<=3` (`cmc` alias), `pow<=3`, `tou>=4`, `id<=bg`, `id=wbr`, `c:r`, `c=0`, `s:blb`, `r:rare`, `kw:flying`, `f:commander`, and `is:mdfc`. Combine terms with spaces/AND, OR and parentheses, and exclude with `-` or NOT. Use `!"Exact Card Name"` for an exact name. `role:`, `group:` and `qty>=2` are Forage extras. Plain words retain Forage’s broad name/rules/type/role matching.

Each search has a **Syntax key** with clickable examples. This is a local subset, not the entire Scryfall query engine: unsupported fields, Tagger tags, regex and price queries produce clear errors. Missing metadata stays unknown even under negation, with a notice to Resolve card data. Scryfall card colors are stored separately from color identity; existing records may need resolving once for the added fields. Printing-level filters run before collection rows merge; name-only imports may use a different Scryfall printing than the physical copy, and commanders stay pinned in deck views. New metadata is kept out of AI prompts.

The collection toolbar includes Sort and Order controls for Name, Mana value, Color identity, Type, Rarity, Owned quantity and Available quantity. Both card and table views share the selected order, remembered on this browser. Sorting happens after filtering and before pagination. Unresolved values remain last in either direction; ties use name order. Quantity sorts use total owned copies across printings and remaining unassigned copies across imported mainboards/commanders. Considering does not reserve copies.
