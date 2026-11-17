import test from "node:test";
import assert from "node:assert/strict";
import { scaleLine, scaleFirstNumber, formatNumber, formatFactor, parseDirections, isHeader } from "../custom_components/paprika_recipes/frontend/scale.js";

const run = (line, f) => scaleLine(line, f).segments.map((s) => s.text).join("");

test("lines from the real Paprika screenshot", () => {
  assert.equal(run("16 oz package of little smokies (or small cooked sausages) I use Hillshire Farm brand", 2),
    "32 oz package of little smokies (or small cooked sausages) I use Hillshire Farm brand");
  assert.equal(run("15 slices bacon, each cut into 3 smaller sections", 2), "30 slices bacon, each cut into 3 smaller sections");
  assert.equal(run("3/4 cup light brown sugar, packed", 2), "1 1/2 cup light brown sugar, packed");
  assert.equal(run("3/4 cup light brown sugar, packed", 0.5), "3/8 cup light brown sugar, packed");
  assert.equal(run("1/2 tsp cayenne pepper more or less, according to your tastes", 2), "1 tsp cayenne pepper more or less, according to your tastes");
  assert.equal(run("pinch of black pepper (optional)", 2), "pinch of black pepper (optional)");
});

test("lines from the real feasibility output", () => {
  assert.equal(run("100 grams bread flour (scant 3/4 cup)", 2), "200 grams bread flour (scant 1 1/2 cup)");
  assert.equal(run("100 grams water (about 7 Tablespoons)", 2), "200 grams water (about 14 Tablespoons)");
  assert.equal(run("10 grams sourdough starter (ripe and active, see recipe notes for other options)", 2),
    "20 grams sourdough starter (ripe and active, see recipe notes for other options)");
  assert.equal(scaleLine("Levain (1:10:10, overnight 10-12 hours at 78ºF):", 2).kind, "header");
  assert.equal(scaleLine("Classic Sourdough Bread:", 3).kind, "header");
  assert.equal(run("Levain (1:10:10, overnight 10-12 hours at 78ºF):", 3), "Levain (1:10:10, overnight 10-12 hours at 78ºF)");
});

test("package-size descriptors are not scaled", () => {
  assert.equal(run("2 (14 oz) cans diced tomatoes", 2), "4 (14 oz) cans diced tomatoes");
  assert.equal(run("4 (6-oz) salmon fillets", 2), "8 (6-oz) salmon fillets");
  assert.equal(run("2 x 400g tins chopped tomatoes", 2), "4 x 400g tins chopped tomatoes");
  assert.equal(run("1 (14.5 oz) can tomatoes, plus 1/2 cup of the juice", 2), "2 (14.5 oz) can tomatoes, plus 1 cup of the juice");
  assert.equal(run("1 cup (240 ml) milk", 2), "2 cup (480 ml) milk");
});

test("number formats: ranges, mixed, unicode, decimals", () => {
  assert.equal(run("1-2 tablespoons olive oil", 2), "2-4 tablespoons olive oil");
  assert.equal(run("2 to 3 cloves garlic", 2), "4 to 6 cloves garlic");
  assert.equal(run("1/2 - 3/4 cup cream", 2), "1 - 1 1/2 cup cream");
  assert.equal(run("1 1/2 cups milk", 2), "3 cups milk");
  assert.equal(run("1 1/2 cups milk", 1 / 3), "1/2 cups milk");
  assert.equal(run("2-3/4 cups flour", 2), "5 1/2 cups flour");
  assert.equal(run("1½ cups flour", 2), "3 cups flour");
  assert.equal(run("½ cup sugar", 3), "1 1/2 cup sugar");
  assert.equal(run("1.5 lb chicken", 2), "3 lb chicken");
  assert.equal(run("1.5 lb chicken", 0.5), "0.75 lb chicken");
  assert.equal(run("3 large eggs", 0.5), "1 1/2 large eggs");
  assert.equal(run("250g flour", 1.5), "375g flour");
  assert.equal(run("100 grams flour", 1 / 3), "33 grams flour");
});

test("things that must not be scaled", () => {
  assert.equal(run("Salt and pepper to taste", 2), "Salt and pepper to taste");
  assert.equal(run("Juice of 1 lemon", 2), "Juice of 1 lemon");
  assert.equal(run("2% milk", 2), "2% milk");
  assert.equal(run("2 garlic cloves, minced (about 1 tablespoon)", 2), "4 garlic cloves, minced (about 2 tablespoon)");
  assert.equal(run("1 large egg", 2), "2 large egg");           // 'l'/'g' are not mistaken for units
  assert.equal(run("1 clove garlic, finely grated", 2), "2 clove garlic, finely grated");
  assert.equal(run("1/0 cup broken", 2), "1/0 cup broken");     // divide-by-zero guard
});

test("factor 1 returns the text untouched and marks the lead quantity", () => {
  const r = scaleLine("3/4 cup  light  brown sugar", 1).segments;
  assert.deepEqual(r, [{ text: "3/4", lead: true }, { text: " cup  light  brown sugar", lead: false }]);
});

test("headers", () => {
  assert.equal(isHeader("FOR THE SAUCE:"), true);
  assert.equal(isHeader("1 cup flour:"), false);
  assert.equal(isHeader("2 cups sugar"), false);
});

test("formatNumber / formatFactor", () => {
  assert.equal(formatNumber(2.0000001), "2");
  assert.equal(formatNumber(2.5), "2 1/2");
  assert.equal(formatNumber(1 / 3), "1/3");
  assert.equal(formatNumber(2 / 3), "2/3");
  assert.equal(formatNumber(0.125), "1/8");
  assert.equal(formatNumber(0.2), "0.2");
  assert.equal(formatNumber(0.05), "0.05");
  assert.equal(formatNumber(12.5, "decimal"), "12.5");
  assert.equal(formatFactor(1.5), "1 1/2×");
  assert.equal(formatFactor(2), "2×");
});

test("servings text", () => {
  assert.equal(scaleFirstNumber("30 slices (2 loaves)", 2), "60 slices (2 loaves)");
  assert.equal(scaleFirstNumber("Serves 4-6", 2), "Serves 8-12");
  assert.equal(scaleFirstNumber("8", 1.5), "12");
  assert.equal(scaleFirstNumber("a crowd", 2), "a crowd");
});

test("directions parsing", () => {
  const d = parseDirections("For the dough:\n1. Mix flour.\n2) Knead well.\n\n3. Bake.");
  assert.deepEqual(d, [{ kind: "header", text: "For the dough" }, { kind: "step", text: "Mix flour." },
    { kind: "step", text: "Knead well." }, { kind: "step", text: "Bake." }]);
  assert.deepEqual(parseDirections("Mix.\nBake."), [{ kind: "step", text: "Mix." }, { kind: "step", text: "Bake." }]);
});
