import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from cookidoo_api.types import CookidooAdditionalItem, CookidooIngredientItem

from cookidoo_service import (
    CookidooService,
    shopping_item_name_matches,
    shopping_item_name_words,
)


class FakeShoppingApi:
    async def get_shopping_list_recipes(self):
        return [
            SimpleNamespace(
                id="recipe-1",
                name="Recipe One",
                url="https://example.test/recipe-1",
                image=None,
                thumbnail=None,
                ingredients=[
                    SimpleNamespace(
                        id="ingredient-1",
                        name="Rice",
                        description="200 g rice",
                    ),
                    SimpleNamespace(
                        id="ingredient-2",
                        name="Salt",
                        description="1 tsp salt",
                    ),
                ],
            ),
            SimpleNamespace(
                id="recipe-2",
                name="Recipe Two",
                url="https://example.test/recipe-2",
                image=None,
                thumbnail=None,
                ingredients=[
                    SimpleNamespace(
                        id="ingredient-3",
                        name="Water",
                        description="500 g water",
                    )
                ],
            ),
        ]

    async def get_ingredient_items(self):
        return [
            SimpleNamespace(id="ingredient-1", is_owned=False),
            SimpleNamespace(id="ingredient-2", is_owned=True),
            SimpleNamespace(id="ingredient-3", is_owned=False),
        ]

    async def get_additional_items(self):
        return [
            SimpleNamespace(id="additional-1", name="Napkins", is_owned=False),
            SimpleNamespace(id="additional-2", name="Soap", is_owned=True),
        ]


def service_with_fake_api() -> CookidooService:
    service = CookidooService("test@example.com", "secret")
    service._api_client = FakeShoppingApi()
    return service


def test_shopping_list_is_grouped_and_excludes_owned_by_default() -> None:
    async def run():
        result = await service_with_fake_api().get_shopping_list_ingredients()
        assert result["summary"] == {
            "recipe_count": 2,
            "ingredient_count": 2,
            "additional_item_count": 1,
            "owned_ingredient_count": 1,
            "include_owned": False,
            "filtered_recipe_id": None,
        }
        assert [item["name"] for item in result["ingredients"]] == [
            "Rice",
            "Water",
        ]
        assert result["recipes"][0]["ingredients"][0]["recipe_id"] == "recipe-1"
        assert result["additional_items"][0]["name"] == "Napkins"

    asyncio.run(run())


def test_shopping_list_can_filter_one_recipe_and_include_owned() -> None:
    async def run():
        result = await service_with_fake_api().get_shopping_list_ingredients(
            recipe_id="recipe-1",
            include_owned=True,
            include_additional_items=False,
        )
        assert result["summary"]["recipe_count"] == 1
        assert result["summary"]["ingredient_count"] == 2
        assert result["recipes"][0]["id"] == "recipe-1"
        assert result["additional_items"] == []

    asyncio.run(run())


def test_unknown_shopping_list_recipe_reports_available_ids() -> None:
    async def run():
        with pytest.raises(ValueError, match="recipe-1"):
            await service_with_fake_api().get_shopping_list_ingredients(
                recipe_id="missing"
            )

    asyncio.run(run())


CUSTOM_RECIPE_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
WRITE_METHODS = (
    "add_ingredient_items_for_recipes",
    "add_ingredient_items_for_custom_recipes",
    "remove_ingredient_items_for_recipes",
    "remove_ingredient_items_for_custom_recipes",
    "edit_ingredient_items_ownership",
    "add_additional_items",
    "remove_additional_items",
    "edit_additional_items_ownership",
    "clear_shopping_list",
)


class FakeFrenchShoppingApi:
    """Stateful shopping list with French phrasing that records every write."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, Any]] = []
        self.ingredients = {
            "ing-eau": ("d'eau", "500 g", False),
            "ing-sel": ("du sel", "1 pincée", False),
            "ing-sel-2": ("de sel", "1 c. à café", False),
            "ing-poivre": ("poivre moulu", "1 pincée", False),
            "ing-eau-chaude": ("eau bouillante", "1 l", True),
            "ing-persil": ("persil", "1 bouquet", False),
            "ing-selle": ("selle d'agneau", "1 kg", False),
            "ing-poivron": ("Poivron rouge", "2", False),
        }
        self.recipe_ingredients = {
            "r460132": ["ing-eau", "ing-sel", "ing-poivre", "ing-persil"],
            CUSTOM_RECIPE_ID: [
                "ing-sel-2",
                "ing-eau-chaude",
                "ing-selle",
                "ing-poivron",
            ],
        }
        self.additional = {
            "add-sel": ("Sel de Guérande", False),
            "add-serviettes": ("Serviettes", False),
        }

    async def get_shopping_list_recipes(self):
        return [
            SimpleNamespace(
                id=recipe_id,
                name=f"Recette {recipe_id}",
                url=None,
                image=None,
                thumbnail=None,
                ingredients=[
                    SimpleNamespace(
                        id=ingredient_id,
                        name=self.ingredients[ingredient_id][0],
                        description=self.ingredients[ingredient_id][1],
                    )
                    for ingredient_id in ingredient_ids
                ],
            )
            for recipe_id, ingredient_ids in self.recipe_ingredients.items()
        ]

    async def get_ingredient_items(self):
        return [
            SimpleNamespace(id=item_id, name=name, description=desc, is_owned=owned)
            for item_id, (name, desc, owned) in self.ingredients.items()
        ]

    async def get_additional_items(self):
        return [
            SimpleNamespace(id=item_id, name=name, is_owned=owned)
            for item_id, (name, owned) in self.additional.items()
        ]

    async def add_ingredient_items_for_recipes(self, recipe_ids):
        self.writes.append(("add_ingredient_items_for_recipes", recipe_ids))
        for recipe_id in recipe_ids:
            self.recipe_ingredients.setdefault(recipe_id, [])
        return []

    async def add_ingredient_items_for_custom_recipes(self, recipe_ids):
        self.writes.append(("add_ingredient_items_for_custom_recipes", recipe_ids))
        for recipe_id in recipe_ids:
            self.recipe_ingredients.setdefault(recipe_id, [])
        return []

    async def remove_ingredient_items_for_recipes(self, recipe_ids):
        self.writes.append(("remove_ingredient_items_for_recipes", recipe_ids))
        for recipe_id in recipe_ids:
            self.recipe_ingredients.pop(recipe_id, None)

    async def remove_ingredient_items_for_custom_recipes(self, recipe_ids):
        self.writes.append(
            ("remove_ingredient_items_for_custom_recipes", recipe_ids)
        )
        for recipe_id in recipe_ids:
            self.recipe_ingredients.pop(recipe_id, None)

    async def edit_ingredient_items_ownership(self, ingredient_items):
        self.writes.append(("edit_ingredient_items_ownership", ingredient_items))
        for item in ingredient_items:
            name, description, _ = self.ingredients[item.id]
            self.ingredients[item.id] = (name, description, item.is_owned)
        return ingredient_items

    async def add_additional_items(self, names):
        self.writes.append(("add_additional_items", names))
        added = []
        for index, name in enumerate(names):
            item_id = f"add-new-{index}"
            self.additional[item_id] = (name, False)
            added.append(SimpleNamespace(id=item_id, name=name, is_owned=False))
        return added

    async def remove_additional_items(self, item_ids):
        self.writes.append(("remove_additional_items", item_ids))
        for item_id in item_ids:
            del self.additional[item_id]

    async def edit_additional_items_ownership(self, additional_items):
        self.writes.append(("edit_additional_items_ownership", additional_items))
        for item in additional_items:
            self.additional[item.id] = (self.additional[item.id][0], item.is_owned)
        return additional_items

    async def clear_shopping_list(self):
        self.writes.append(("clear_shopping_list", None))
        raise AssertionError("clear_shopping_list must never be called")


def french_service() -> tuple[CookidooService, FakeFrenchShoppingApi]:
    service = CookidooService("test@example.com", "secret")
    api = FakeFrenchShoppingApi()
    service._api_client = api
    return service, api


@pytest.mark.parametrize(
    ("item_name", "query"),
    [
        ("d'eau", "eau"),
        ("d’eau", "eau"),
        ("du sel", "sel"),
        ("de sel", "SEL"),
        ("Sel", "du sel"),
        ("poivre moulu", "poivre"),
        ("eau bouillante", "eau"),
        ("Crème fraîche épaisse", "creme fraiche"),
        ("l'huile d'olive", "huile"),
        ("des œufs", "oeufs"),
        ("pomme-de-terre", "pomme de terre"),
    ],
)
def test_shopping_item_names_match_french_phrasing(item_name, query) -> None:
    assert shopping_item_name_matches(item_name, query)


@pytest.mark.parametrize(
    ("item_name", "query"),
    [
        ("selle d'agneau", "sel"),
        ("persil", "sel"),
        ("Poivron rouge", "poivre"),
        ("eau", "eau de rose"),
        ("du sel", "de"),
    ],
)
def test_shopping_item_names_reject_partial_words(item_name, query) -> None:
    assert not shopping_item_name_matches(item_name, query)


def test_shopping_item_name_words_drop_articles_and_accents() -> None:
    assert shopping_item_name_words("L'Eau GAZÉIFIÉE de la source") == (
        "eau",
        "gazeifiee",
        "source",
    )


@pytest.mark.parametrize(
    ("recipe_ids", "expected_writes"),
    [
        (["r460132"], [("add_ingredient_items_for_recipes", ["r460132"])]),
        (
            [CUSTOM_RECIPE_ID],
            [("add_ingredient_items_for_custom_recipes", [CUSTOM_RECIPE_ID])],
        ),
        (
            ["r1", CUSTOM_RECIPE_ID, "r2", "r1"],
            [
                ("add_ingredient_items_for_recipes", ["r1", "r2"]),
                ("add_ingredient_items_for_custom_recipes", [CUSTOM_RECIPE_ID]),
            ],
        ),
    ],
)
def test_add_shopping_list_recipes_routes_official_and_custom_ids(
    recipe_ids,
    expected_writes,
) -> None:
    async def run():
        service, api = french_service()
        result = await service.add_shopping_list_recipes(recipe_ids)

        assert api.writes == expected_writes
        assert result["operation"] == "added"
        assert set(result["shopping_list"]) == {
            "recipes",
            "ingredients",
            "additional_items",
            "summary",
        }
        assert {recipe["id"] for recipe in result["shopping_list"]["recipes"]} >= set(
            recipe_ids
        )

    asyncio.run(run())


def test_add_shopping_list_recipes_honours_explicit_source() -> None:
    async def run():
        service, api = french_service()
        await service.add_shopping_list_recipes(["my-recipe"], "custom")
        assert api.writes == [
            ("add_ingredient_items_for_custom_recipes", ["my-recipe"])
        ]

    asyncio.run(run())


@pytest.mark.parametrize(
    ("recipe_ids", "expected_writes"),
    [
        (["r460132"], [("remove_ingredient_items_for_recipes", ["r460132"])]),
        (
            [CUSTOM_RECIPE_ID],
            [("remove_ingredient_items_for_custom_recipes", [CUSTOM_RECIPE_ID])],
        ),
        (
            ["r460132", CUSTOM_RECIPE_ID],
            [
                ("remove_ingredient_items_for_recipes", ["r460132"]),
                (
                    "remove_ingredient_items_for_custom_recipes",
                    [CUSTOM_RECIPE_ID],
                ),
            ],
        ),
    ],
)
def test_remove_shopping_list_recipes_routes_official_and_custom_ids(
    recipe_ids,
    expected_writes,
) -> None:
    async def run():
        service, api = french_service()
        result = await service.remove_shopping_list_recipes(recipe_ids)

        assert api.writes == expected_writes
        assert result["operation"] == "removed"
        remaining = {recipe["id"] for recipe in result["shopping_list"]["recipes"]}
        assert remaining.isdisjoint(recipe_ids)

    asyncio.run(run())


@pytest.mark.parametrize(
    "recipe_ids",
    [[], ["  "], ["not-a-recipe-id"]],
)
def test_invalid_shopping_list_recipe_ids_never_write(recipe_ids) -> None:
    async def run():
        service, api = french_service()
        with pytest.raises(ValueError):
            await service.add_shopping_list_recipes(recipe_ids)
        with pytest.raises(ValueError):
            await service.remove_shopping_list_recipes(recipe_ids)
        assert api.writes == []

    asyncio.run(run())


def test_staples_are_matched_by_french_names_and_marked_owned() -> None:
    async def run():
        service, api = french_service()
        result = await service.set_shopping_list_items_owned(
            [],
            ["eau", "sel", "poivre"],
        )

        changed = {change["id"] for change in result["changes"]}
        assert changed == {
            "ing-eau",
            "ing-sel",
            "ing-sel-2",
            "ing-poivre",
            "add-sel",
        }
        assert [item["id"] for item in result["already_in_state"]] == [
            "ing-eau-chaude"
        ]
        assert result["warnings"] == []
        assert result["operation"] == "updated ownership"

        (ingredient_call, ingredient_items), (additional_call, extra_items) = (
            api.writes
        )
        assert ingredient_call == "edit_ingredient_items_ownership"
        assert all(isinstance(i, CookidooIngredientItem) for i in ingredient_items)
        assert {i.id for i in ingredient_items} == changed - {"add-sel"}
        assert all(i.is_owned for i in ingredient_items)
        assert additional_call == "edit_additional_items_ownership"
        assert all(isinstance(i, CookidooAdditionalItem) for i in extra_items)
        assert [(i.id, i.is_owned) for i in extra_items] == [("add-sel", True)]

        for false_positive in ("ing-persil", "ing-selle", "ing-poivron"):
            assert api.ingredients[false_positive][2] is False
        owned = {
            item["id"]: item["is_owned"]
            for item in result["shopping_list"]["ingredients"]
        }
        assert owned["ing-sel"] is True and owned["ing-persil"] is False

    asyncio.run(run())


def test_ownership_plan_lists_ids_state_and_description() -> None:
    async def run():
        service, api = french_service()
        plan = await service.plan_shopping_list_ownership([], ["sel"])

        first = plan["changes"][0]
        assert first == {
            "id": "ing-sel",
            "kind": "ingredient",
            "name": "du sel",
            "description": "1 pincée",
            "recipe_id": "r460132",
            "recipe_name": "Recette r460132",
            "current_is_owned": False,
            "new_is_owned": True,
            "matched_by": {"item_id": False, "names": ["sel"]},
        }
        assert api.writes == []

    asyncio.run(run())


def test_unmatched_names_and_ids_are_reported_not_silently_ignored() -> None:
    async def run():
        service, api = french_service()
        result = await service.set_shopping_list_items_owned(
            ["missing-id"],
            ["cumin", "sel"],
        )

        assert result["unmatched_names"] == ["cumin"]
        assert result["unmatched_item_ids"] == ["missing-id"]
        assert "No shopping-list item matches name 'cumin'." in result["warnings"]
        assert "No shopping-list item has ID 'missing-id'." in result["warnings"]
        assert {change["id"] for change in result["changes"]} == {
            "ing-sel",
            "ing-sel-2",
            "add-sel",
        }

    asyncio.run(run())


def test_ownership_with_nothing_to_change_does_not_write() -> None:
    async def run():
        service, api = french_service()
        result = await service.set_shopping_list_items_owned([], ["cumin"])

        assert result["operation"] == "unchanged"
        assert result["changes"] == []
        assert result["unmatched_names"] == ["cumin"]
        assert api.writes == []

    asyncio.run(run())


def test_items_can_be_selected_by_id_and_marked_needed_again() -> None:
    async def run():
        service, api = french_service()
        result = await service.set_shopping_list_items_owned(
            ["ing-eau-chaude", "ing-persil"],
            [],
            owned=False,
        )

        assert [change["id"] for change in result["changes"]] == [
            "ing-eau-chaude"
        ]
        assert [item["id"] for item in result["already_in_state"]] == [
            "ing-persil"
        ]
        assert [(i.id, i.is_owned) for i in api.writes[0][1]] == [
            ("ing-eau-chaude", False)
        ]

    asyncio.run(run())


@pytest.mark.parametrize(
    ("item_ids", "names"),
    [([], []), ([" "], [""]), ([], ["de la"])],
)
def test_ownership_requires_a_meaningful_selection(item_ids, names) -> None:
    async def run():
        service, api = french_service()
        with pytest.raises(ValueError):
            await service.set_shopping_list_items_owned(item_ids, names)
        assert api.writes == []

    asyncio.run(run())


def test_additional_items_can_be_added_and_removed() -> None:
    async def run():
        service, api = french_service()
        added = await service.add_shopping_list_additional_items(
            ["Café", "Café", " "]
        )
        assert api.writes == [("add_additional_items", ["Café"])]
        new_id = added["added_items"][0]["id"]
        assert new_id in {
            item["id"] for item in added["shopping_list"]["additional_items"]
        }

        removed = await service.remove_shopping_list_additional_items([new_id])
        assert api.writes[-1] == ("remove_additional_items", [new_id])
        assert removed["removed_items"][0]["name"] == "Café"

    asyncio.run(run())


def test_additional_item_removal_refuses_unknown_or_ingredient_ids() -> None:
    async def run():
        service, api = french_service()
        with pytest.raises(ValueError, match="ing-sel"):
            await service.remove_shopping_list_additional_items(
                ["add-serviettes", "ing-sel"]
            )
        assert api.writes == []

    asyncio.run(run())
