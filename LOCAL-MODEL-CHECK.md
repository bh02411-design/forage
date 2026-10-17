# Check a local model

Use a disposable test workspace with resolved card data. These are quality checks, not a promise that every local model can follow the instructions.

1. Ask for owned card draw outside the active mainboard. Verify actual ownership, available quantities, identity, costs and rules text. A card-name substring must not count as an ability match.
2. Compare immediate net hand gain, discard/draw filtering and a creature cantrip. Count the card spent casting the spell, additional costs, activation costs and recurrence setup separately.
3. Ask about a commander-specific eligibility restriction using its supplied Oracle text. Check the exact restriction rather than a superficially similar value such as power versus mana value.
4. Save a sample deck preference, ask another question, then return to recommendations. Check that the saved preference still applies. Ask a short follow-up to test conversational continuity.
5. Mark a disposable card protected, then ask for swaps. Verify it is not proposed as a cut.
6. Remove collection data in a disposable workspace and ask for owned recommendations. The model should explain the missing evidence rather than invent ownership.

Open **Context used** to see what was actually sent and checked. Passing structured checks does not prove every sentence or strategic conclusion. Record the model identifier and specific errors when comparing models.
