# Planning and shopping automation

## Meal planning

`get_meal_plan_week(date)` reads the seven-day Cookidoo planning window containing an ISO date. Recipes can be added, removed, or moved using official or custom recipe IDs.

Use this safe sequence:

1. Read the current week.
2. Identify the exact date and recipe occurrence.
3. Call the mutation with `dry_run=true` and review the exact JSON preview.
4. Repeat the same scoped call with `dry_run=false`.
5. Read the week again and verify it.

Use `recipe_source="auto"` unless there is a reason to force `official` or `custom`.
A dry run validates dates, IDs, source inference, and operation order without
changing the calendar.

## Shopping list

`get_shopping_list_ingredients` returns structured ingredients for either the full Cookidoo list or a single recipe. Owned items and user-added items can be included or excluded.

To fill and tidy the list after planning:

1. Add the week's recipes with `add_recipes_to_shopping_list(recipe_ids, dry_run=true)`, review, then apply.
2. Preview `set_shopping_list_items_owned(names="eau, sel, poivre", dry_run=true)`. Names match whole words, ignoring case, accents, and French articles, so `sel` matches "du sel" but not "persil". The preview lists every matched item's ID, description, and current state, plus names that matched nothing.
3. Apply with `dry_run=false`. Owned items are then hidden from the default list.

Manual items can be managed with `add_additional_items_to_shopping_list` and `remove_additional_items_from_shopping_list`.

This output is suitable for handing to another grocery-search or cart integration. Cookidoo MCP does not choose store products or place purchases itself.
