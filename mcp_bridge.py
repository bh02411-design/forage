#!/usr/bin/env python3
"""Private, read-only MCP bridge for an already-running local Forage.

Run through a Secure MCP Tunnel using stdio. Never expose Forage's local
HTTP endpoint on a public interface. No OpenAI API key or model is required.
"""
import http.client
import json
import os
import re
import sys

MIB = 1024 * 1024
DEFAULT_WORKSPACE_MIB = 64
MAX_WORKSPACE_MIB = 128
PROTOCOL_VERSION = "2025-06-18"


def normalize(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower().split(" // ")[0])


def integer(value, default, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def read_workspace():
    port = integer(os.environ.get("FORAGE_PORT", "8765"), 8765, 1, 65535)
    limit_mib = integer(os.environ.get("FORAGE_MCP_MAX_MIB"), DEFAULT_WORKSPACE_MIB,
                        DEFAULT_WORKSPACE_MIB, MAX_WORKSPACE_MIB)
    max_bytes = limit_mib * MIB
    size_error = f"Forage workspace exceeds bridge size limit ({limit_mib} MiB)"
    # Direct loopback GET. HTTPConnection does not use proxies or follow redirects.
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    for path in ("/api/mcp-state", "/api/state"):
        try:
            connection.request("GET", path, headers={"Accept": "application/json"})
            with connection.getresponse() as response:
                # Older Forage builds only have the browser endpoint.
                if response.status == 404 and path == "/api/mcp-state":
                    continue
                if response.status != 200:
                    raise ValueError("Forage workspace request failed")
                if response.length is not None and response.length > max_bytes:
                    raise ValueError(size_error)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError(size_error)
        finally:
            connection.close()
        break

    try:
        state = json.loads(body)["state"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("Invalid Forage workspace response") from None
    if not isinstance(state, dict):
        raise ValueError("Invalid Forage workspace response")
    # Only the fields needed by tools leave this function.
    return {field: state[field] for field in ("active", "decks", "collection")
            if field in state}


def active_cards(deck):
    pins = set((deck.get("swap_categories") or {"in": "Swap In", "out": "Swap Out"}).values())
    return [c for c in deck.get("cards", [])
            if c.get("zone") == "commander"
            or (c.get("zone") == "main" and c.get("group") not in pins)]


def ownership(state, name, exclude_deck=None):
    target = normalize(name)
    owned = sum(int(c.get("qty", 1)) for c in state.get("collection", [])
                if normalize(c.get("name")) == target)
    assigned = sum(int(c.get("qty", 1))
                   for deck in state.get("decks", []) if deck.get("id") != exclude_deck
                   for c in deck.get("cards", []) if c.get("zone") in ("main", "commander")
                   and normalize(c.get("name")) == target)
    return {"owned": owned, "assigned_elsewhere": assigned,
            "available": max(0, owned - assigned),
            "collection_imported": bool(state.get("collection"))}


def find_deck(state, deck_id):
    if not deck_id:
        deck_id = state.get("active")
    deck = next((d for d in state.get("decks", []) if d.get("id") == deck_id), None)
    if deck is None:
        raise ValueError("Deck ID not found. Use list_decks first.")
    return deck


CARD_FIELDS = ("name", "qty", "zone", "group", "mv", "mana_cost",
               "type_line", "oracle_text", "color_identity", "roles",
               "land", "mdfc", "protected", "legalities", "meta_source")


def public_card(card):
    return {field: card[field] for field in CARD_FIELDS if field in card}


def list_decks(args, state):
    result = []
    for deck in state.get("decks", []):
        cards = active_cards(deck)
        result.append({"id": deck.get("id"), "name": deck.get("name"),
                       "mainboard_count": sum(int(c.get("qty", 1)) for c in cards),
                       "commander": [c.get("name") for c in cards
                                     if c.get("zone") == "commander"]})
    return {"decks": result, "active_deck_id": state.get("active"),
            "collection_imported": bool(state.get("collection"))}


def get_deck(args, state):
    deck = find_deck(state, args.get("deck_id"))
    zone = args.get("board", "mainboard")
    if zone not in ("mainboard", "considering", "all"):
        raise ValueError("board must be mainboard, considering or all")
    if zone == "mainboard":
        cards = active_cards(deck)
    elif zone == "considering":
        cards = [c for c in deck.get("cards", []) if c.get("zone") == "maybe"]
    else:
        cards = deck.get("cards", [])
    return {"deck_id": deck.get("id"), "name": deck.get("name"), "board": zone,
            "count": sum(int(c.get("qty", 1)) for c in cards),
            "cards": [public_card(c) for c in cards],
            "note": "Mainboard excludes swap-staging cards; all includes staging and Considering."}


def search_collection(args, state):
    needle = str(args.get("query", "")).strip().casefold()
    offset = integer(args.get("offset"), 0, 0, 1000000)
    limit = integer(args.get("limit"), 50, 1, 100)
    # Exact name substring search, with a fixed alphabetic ordering.
    stock = {}
    for card in state.get("collection", []):
        if needle and needle not in str(card.get("name", "")).casefold():
            continue
        name = normalize(card.get("name"))
        if not name:
            continue
        if name not in stock:
            stock[name] = public_card(card)
            stock[name]["qty"] = 0
        stock[name]["qty"] += int(card.get("qty", 1))
    matches = sorted(stock.values(), key=lambda c: str(c["name"]).casefold())
    cards = matches[offset:offset + limit]
    for card in cards:
        card["availability"] = ownership(state, card["name"])
    return {"total_matching_names": len(matches), "offset": offset,
            "next_offset": offset + len(cards) if offset + len(cards) < len(matches) else None,
            "cards": cards, "collection_imported": bool(state.get("collection"))}


def card_availability(args, state):
    name = str(args.get("name", "")).strip()
    if not name:
        raise ValueError("A card name is required")
    return {"name": name, **ownership(state, name, args.get("exclude_deck_id"))}


def propose_swap(args, state):
    deck = find_deck(state, args.get("deck_id"))
    add = str(args.get("add", "")).strip()
    cut = str(args.get("cut", "")).strip()
    if not add or not cut or normalize(add) == normalize(cut):
        raise ValueError("Provide two distinct card names: add and cut")
    cards = active_cards(deck)
    cut_card = next((c for c in cards if normalize(c.get("name")) == normalize(cut)
                     and c.get("zone") == "main"), None)
    if cut_card is None:
        raise ValueError("The cut is not currently in this deck's mainboard")
    if cut_card.get("protected"):
        raise ValueError("The chosen cut is protected")
    if any(normalize(c.get("name")) == normalize(add) for c in cards):
        raise ValueError("The addition is already on the mainboard or in the command zone")
    copies = [c for c in state.get("collection", []) if normalize(c.get("name")) == normalize(add)]
    available = ownership(state, add, deck.get("id"))
    warnings = []
    if not copies:
        warnings.append("Card not found in imported collection")
    elif available["available"] < 1:
        warnings.append("No unassigned owned copy outside this deck")
    commanders = [c for c in cards if c.get("zone") == "commander"]
    identity = set().union(*(c.get("color_identity", []) for c in commanders)) if commanders else set()
    addition = copies[0] if copies else None
    if not commanders:
        warnings.append("No commander assigned; color identity not verified")
    elif not addition or not isinstance(addition.get("color_identity"), list):
        warnings.append("Color identity not resolved for addition")
    elif not set(addition["color_identity"]).issubset(identity):
        warnings.append("Addition is outside commander color identity")
    if addition:
        legality = (addition.get("legalities") or {}).get("commander")
        if legality == "banned":
            warnings.append("Addition is banned in Commander")
        elif legality is None:
            warnings.append("Commander legality not resolved")
    return {"status": "review_only", "saved": False, "deck_id": deck.get("id"),
            "deck_name": deck.get("name"), "add": add, "cut": cut,
            "cut_card": public_card(cut_card),
            "add_card": public_card(addition) if addition else None,
            "availability": available, "warnings": warnings,
            "ready_to_consider": not warnings,
            "note": "Preview only. No deck or collection data has been changed."}


TOOLS = [
    {"name": "list_decks", "description": "List local Forage decks, deck IDs, and mainboard counts.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_deck", "description": "Read one Forage deck's cards and saved card metadata. Never changes the deck.",
     "inputSchema": {"type": "object", "properties": {
         "deck_id": {"type": "string", "description": "ID from list_decks; omit for active deck"},
         "board": {"type": "string", "enum": ["mainboard", "considering", "all"]}},
         "additionalProperties": False}},
    {"name": "search_collection", "description": "Read owned cards from the imported collection, including allocation across decks. Page through results.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Case-insensitive substring of card name; empty for all"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 100},
         "offset": {"type": "integer", "minimum": 0}},
         "additionalProperties": False}},
    {"name": "card_availability", "description": "Find owned and assigned copies of a card. Optional deck exclusion for evaluating an addition.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string"}, "exclude_deck_id": {"type": "string"}},
         "required": ["name"], "additionalProperties": False}},
    {"name": "propose_swap", "description": "Preview one add/cut swap against the current deck, owned copies and commander identity. Read-only; never applies edits.",
     "inputSchema": {"type": "object", "properties": {
         "deck_id": {"type": "string"}, "add": {"type": "string"}, "cut": {"type": "string"}},
         "required": ["add", "cut"], "additionalProperties": False}},
]
for item in TOOLS:
    item["annotations"] = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}

HANDLERS = {
    "list_decks": list_decks,
    "get_deck": get_deck,
    "search_collection": search_collection,
    "card_availability": card_availability,
    "propose_swap": propose_swap,
}


def dispatch(message):
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "forage-private", "version": "0.1.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        if name not in HANDLERS:
            raise ValueError("Unknown Forage tool")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")
        result = HANDLERS[name](args, read_workspace())
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    raise KeyError(method)


def serve(input_stream=sys.stdin, output_stream=sys.stdout):
    for line in input_stream:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                continue
            # Notifications have no id and must not receive responses.
            if "id" not in request:
                continue
            ident = request["id"]
            try:
                result = dispatch(request)
                response = {"jsonrpc": "2.0", "id": ident, "result": result}
            except KeyError:
                response = {"jsonrpc": "2.0", "id": ident,
                            "error": {"code": -32601, "message": "Method not found"}}
            except Exception as exc:
                # Do not leak filesystem paths, settings, or tokens in errors.
                message = "Forage is unavailable or could not complete the request"
                if isinstance(exc, ValueError):
                    message = str(exc)[:240]
                response = {"jsonrpc": "2.0", "id": ident,
                            "error": {"code": -32000, "message": message}}
            output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
            output_stream.flush()
        except (ValueError, TypeError):
            continue


if __name__ == "__main__":
    serve()
