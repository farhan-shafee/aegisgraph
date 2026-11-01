import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import test from "node:test";

const require = createRequire(import.meta.url);

test("ordinary Node processes load the unmodified upstream API", () => {
  const output = execFileSync(
    process.execPath,
    [
      "-e",
      'const m = require("minimatch"); console.log(JSON.stringify([typeof m, typeof m.minimatch]));',
    ],
    { encoding: "utf8" },
  );
  assert.deepEqual(JSON.parse(output), ["object", "function"]);
});

test("the lockfile installs only the real patched minimatch package", () => {
  const lock = JSON.parse(
    readFileSync(new URL("../package-lock.json", import.meta.url), "utf8"),
  );
  const matchers = Object.entries(lock.packages).filter(([path]) =>
    path.endsWith("node_modules/minimatch"),
  );
  assert.ok(matchers.length > 0);
  for (const [, entry] of matchers) {
    assert.equal(entry.version, "11.0.1");
    assert.equal(
      entry.resolved,
      "https://registry.npmjs.org/minimatch/-/minimatch-11.0.1.tgz",
    );
    assert.ok(entry.integrity.startsWith("sha512-"));
  }
});

test("legacy CommonJS and ESM callers share the patched named API", async () => {
  const cjs = require("minimatch");
  const esm = await import("minimatch");
  assert.equal(typeof cjs, "function");
  assert.equal(typeof esm.default, "function");
  assert.equal(esm.Minimatch, cjs.Minimatch);
  assert.equal(esm.minimatch, cjs.minimatch);
  for (const match of [cjs, esm.default, esm.minimatch]) {
    assert.equal(match("src/app/page.tsx", "**/*.{ts,tsx}"), true);
    assert.equal(match(".hidden", "*"), false);
    assert.equal(match(".hidden", "*", { dot: true }), true);
    assert.equal(match("src/app/page.js", "**/*.tsx"), false);
  }
  assert.equal(new cjs.Minimatch("**/*.tsx").match("src/page.tsx"), true);
  assert.deepEqual(["one.ts", "two.js"].filter(cjs.filter("*.ts")), ["one.ts"]);
  assert.deepEqual(cjs.match(["one.ts", "two.js"], "*.js"), ["two.js"]);
  assert.deepEqual(cjs.braceExpand("file.{js,ts}"), ["file.js", "file.ts"]);
  assert.equal(cjs.defaults({ nocase: true })("FILE.TS", "*.ts"), true);
});

test("React glob exceptions still accept allowed names and report violations", async () => {
  const { ESLint } = await import("eslint");
  const react = require("eslint-plugin-react");
  const eslint = new ESLint({
    overrideConfigFile: true,
    overrideConfig: {
      languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
      plugins: { react },
      rules: { "react/jsx-pascal-case": ["error", { ignore: ["Ignored_*"] }] },
    },
  });
  const [result] = await eslint.lintText(
    "const view = <><Ignored_Component /><Bad_Component /></>;",
  );
  assert.equal(result.errorCount, 1);
  assert.equal(result.messages[0].ruleId, "react/jsx-pascal-case");
  assert.match(result.messages[0].message, /Bad_Component/);
});

test("import allow globs still distinguish permitted and forbidden side effects", async () => {
  const { ESLint } = await import("eslint");
  const imports = require("eslint-plugin-import");
  const eslint = new ESLint({
    overrideConfigFile: true,
    overrideConfig: {
      plugins: { import: imports },
      rules: {
        "import/no-unassigned-import": ["error", { allow: ["allowed/**"] }],
      },
    },
  });
  const [result] = await eslint.lintText(
    'import "allowed/setup"; import "blocked/setup";',
  );
  assert.equal(result.errorCount, 1);
  assert.equal(result.messages[0].ruleId, "import/no-unassigned-import");
  assert.equal(result.messages[0].column, 25);
});

test("accessibility rules keep checking nested custom controls", async () => {
  const { ESLint } = await import("eslint");
  const accessibility = require("eslint-plugin-jsx-a11y");
  const eslint = new ESLint({
    overrideConfigFile: true,
    overrideConfig: {
      languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
      plugins: { "jsx-a11y": accessibility },
      rules: {
        "jsx-a11y/label-has-associated-control": [
          "error",
          { assert: "nesting", controlComponents: ["Ui_*"] },
        ],
      },
    },
  });
  const [result] = await eslint.lintText(
    "const view = <><label>Name<Ui_Control /></label><label>Name<span /></label></>;",
  );
  assert.equal(result.errorCount, 1);
  assert.equal(
    result.messages[0].ruleId,
    "jsx-a11y/label-has-associated-control",
  );
  assert.match(result.messages[0].message, /associated with a control/);
});

test("internal import restrictions keep enforcing allow and forbid patterns", async () => {
  const { ESLint } = await import("eslint");
  const imports = require("eslint-plugin-import");
  for (const options of [
    { forbid: ["**/format.ts"] },
    { allow: ["**/timeline.ts"] },
  ]) {
    const eslint = new ESLint({
      overrideConfigFile: true,
      overrideConfig: {
        plugins: { import: imports },
        rules: { "import/no-internal-modules": ["error", options] },
      },
    });
    const [result] = await eslint.lintText(
      'import "./src/lib/format.ts"; import "./src/lib/timeline.ts";',
      { filePath: "lint-dependency-fixture.js" },
    );
    assert.equal(result.errorCount, 1);
    assert.equal(result.messages[0].ruleId, "import/no-internal-modules");
    assert.match(result.messages[0].message, /format\.ts/);
  }
});

test("ESLint's ESM configuration packages can import the legacy default", async () => {
  const { ConfigArray } = await import("@eslint/config-array");
  const { Legacy } = await import("@eslint/eslintrc");
  const config = new ConfigArray([{ files: ["**/*.js"] }], {
    basePath: process.cwd(),
  });
  await config.normalize();
  assert.equal(
    config.getConfigStatus(`${process.cwd()}/included.js`),
    "matched",
  );
  assert.equal(
    config.getConfigStatus(`${process.cwd()}/excluded.txt`),
    "unconfigured",
  );
  assert.equal(typeof Legacy.ConfigArrayFactory, "function");
});

test("the real Next configuration loads and enforces React Hooks rules", async () => {
  const { ESLint } = await import("eslint");
  const eslint = new ESLint();
  const [result] = await eslint.lintText(
    'import { useState } from "react"; export function Component({ flag }) { if (flag) useState(0); return null; }',
    { filePath: "src/lint-dependency-fixture.tsx" },
  );
  assert.ok(
    result.messages.some(
      (message) => message.ruleId === "react-hooks/rules-of-hooks",
    ),
  );
  assert.equal(result.fatalErrorCount, 0);
});
