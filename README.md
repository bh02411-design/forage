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

