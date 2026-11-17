"""Shape raw Paprika recipe dicts into the small public JSON the viewer uses."""


from __future__ import annotations


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _http_url(value):
    text = _text(value)
    if text and text.lower().startswith(("http://", "https://")):
        return text
    return None


def _rating(value):
    try:
        return max(0, min(5, int(value)))
    except (TypeError, ValueError):
        return 0


def category_names(recipe, categories):
    names = []
    for cid in recipe.get("categories") or []:
        name = categories.get(cid)
        if name:
            names.append(name)
    return names


def summary(recipe, categories, has_photo):
    uid = recipe["uid"]
    return {
        "uid": uid,
        "name": _text(recipe.get("name")) or "(untitled)",
        "photo": bool(has_photo),
        "categories": category_names(recipe, categories),
        "rating": _rating(recipe.get("rating")),
        "favorite": bool(recipe.get("on_favorites")),
        "servings": _text(recipe.get("servings")),
        "prep_time": _text(recipe.get("prep_time")),
        "cook_time": _text(recipe.get("cook_time")),
        "total_time": _text(recipe.get("total_time")),
        "difficulty": _text(recipe.get("difficulty")),
        "source": _text(recipe.get("source")),
    }


def public_recipe(recipe, categories, has_photo):
    data = summary(recipe, categories, has_photo)
    data.update(
        {
            "description": _text(recipe.get("description")),
            "ingredients": recipe.get("ingredients") or "",
            "directions": recipe.get("directions") or "",
            "notes": _text(recipe.get("notes")),
            "nutritional_info": _text(recipe.get("nutritional_info")),
            "source_url": _http_url(recipe.get("source_url")),
        }
    )
    return data
