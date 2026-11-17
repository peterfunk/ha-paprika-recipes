/* Home Assistant panel: hosts <paprika-viewer> and feeds it from the websocket API. */
import "./viewer.js";

class PaprikaRecipesPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this._viewer) this._build();
  }

  set narrow(_) {}
  set panel(_) {}
  set route(_) {}

  _build() {
    this.style.display = "block";
    this.style.height = "100%";
    this.style.overflow = "auto";
    const viewer = document.createElement("paprika-viewer");
    viewer.style.display = "block";
    this.appendChild(viewer);
    this._viewer = viewer;
    const call = (msg) => this._hass.callWS(msg);
    viewer.provider = {
      listRecipes: async () => (await call({ type: "paprika_recipes/list" })).recipes,
      getRecipe: (uid) => call({ type: "paprika_recipes/get", uid }),
      photoUrl: (item) => item.photo,
    };
  }
}

if (!customElements.get("paprika-recipes-panel")) {
  customElements.define("paprika-recipes-panel", PaprikaRecipesPanel);
}
