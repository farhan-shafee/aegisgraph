/** Exact UTF-8 logical-file verification; no uploads, extraction, or content rendering. */
export const MAX_BUNDLE_BYTES = 2 * 1024 * 1024;
const MAX_FILE_BYTES = 256 * 1024;
const MAX_NODES = 100_000;
const MAX_DEPTH = 32;
export const BUNDLE_LIMITATIONS = [
  "VALID means the supplied logical files match the supplied manifest's SHA-256 hashes and byte lengths.",
  "The manifest is unsigned and replaceable: replacing both content and its recorded hash cannot be detected here. Case, time, application, and projection metadata are not authenticated.",
  "Verification does not prove source telemetry truth, privileged-database integrity, authorship, or chain of custody.",
] as const;
const FIXED_PATHS = [
  "incident.json",
  "timeline.json",
  "alerts.json",
  "findings.json",
  "hypotheses.json",
  "notes.json",
  "audit.json",
  "entities.json",
  "README.txt",
];

export type BundleStatus =
  "VALID" | "MODIFIED" | "MISSING FILE" | "UNEXPECTED FILE" | "INVALID";
export type BundleFinding = {
  status: BundleStatus;
  path?: string;
  code: string;
};
export type BundleFileHash = { path: string; sha256: string; bytes: number };
export type BundleManifest = {
  format_version: "1";
  incident_id: string;
  scenario_id: "atlas-compromise" | null;
  projection: "public_synthetic" | "local_review";
  generated_at: string;
  evidence_ids: string[];
  files: BundleFileHash[];
  application: { name: "AegisGraph"; version: "0.1.0" };
  limitations: string[];
};
export type BundleVerification = {
  status: BundleStatus;
  findings: BundleFinding[];
  checked_files: number;
  limitations: string[];
  /** Schema-checked, still unsigned metadata; never includes logical file contents. */
  manifest?: BundleManifest;
};

class InvalidBundle extends Error {}
function invalid(code: string): never {
  throw new InvalidBundle(code);
}

// Retain integer-token identity: Python deliberately rejects bytes: 1.0 and 1e0.
class JsonNumber {
  constructor(
    readonly value: number,
    readonly integer: boolean,
  ) {}
}
type Json =
  null | boolean | string | JsonNumber | Json[] | { [key: string]: Json };
type JsonObject = { [key: string]: Json };

function utf8(value: string): Uint8Array<ArrayBuffer> {
  if (value.length > MAX_BUNDLE_BYTES) invalid("bundle_bytes_exceeded");
  for (let i = 0; i < value.length; i++) {
    const unit = value.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(++i);
      if (!(next >= 0xdc00 && next <= 0xdfff)) invalid("invalid_utf8");
    } else if (unit >= 0xdc00 && unit <= 0xdfff) invalid("invalid_utf8");
  }
  return new TextEncoder().encode(value);
}

/** A byte-, depth-, and node-bounded JSON grammar, preserving duplicate keys. */
function parse(raw: string | Uint8Array): Json {
  let text: string;
  if (typeof raw === "string") text = raw;
  else if (
    ArrayBuffer.isView(raw) &&
    Object.prototype.toString.call(raw) === "[object Uint8Array]"
  ) {
    if (raw.byteLength > MAX_BUNDLE_BYTES) invalid("bundle_bytes_exceeded");
    try {
      text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(
        raw,
      );
    } catch {
      invalid("invalid_utf8");
    }
  } else invalid("invalid_container");
  if (utf8(text).byteLength > MAX_BUNDLE_BYTES)
    invalid("bundle_bytes_exceeded");
  let position = 0,
    nodes = 0,
    stringBytes = 0;
  const number = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;
  function node(depth: number) {
    if (++nodes > MAX_NODES || depth > MAX_DEPTH)
      invalid("structure_limit_exceeded");
  }
  function whitespace() {
    while (position < text.length && /[\x20\t\r\n]/.test(text[position]))
      position++;
  }
  function string(): string {
    const start = position++;
    while (position < text.length) {
      const char = text[position++];
      if (char === "\\") position++;
      else if (char === '"') {
        let value: string;
        try {
          value = JSON.parse(text.slice(start, position)) as string;
        } catch {
          invalid("invalid_json");
        }
        stringBytes += utf8(value).byteLength;
        if (stringBytes > MAX_BUNDLE_BYTES) invalid("bundle_bytes_exceeded");
        return value;
      }
    }
    invalid("invalid_json");
  }
  function value(depth: number): Json {
    node(depth);
    whitespace();
    const char = text[position];
    if (char === '"') return string();
    if (char === "{" || char === "[") {
      // Matches the Python pre-parser's maximum of 32 open containers.
      if (depth >= MAX_DEPTH) invalid("structure_limit_exceeded");
      const object = char === "{";
      position++;
      whitespace();
      const result: JsonObject | Json[] = object
        ? (Object.create(null) as JsonObject)
        : [];
      const end = object ? "}" : "]";
      if (text[position] === end) {
        position++;
        return result;
      }
      while (position < text.length) {
        whitespace();
        if (object) {
          if (text[position] !== '"') invalid("invalid_json");
          node(depth + 1);
          const key = string();
          whitespace();
          if (Object.hasOwn(result, key)) invalid("duplicate_json_key");
          if (text[position++] !== ":") invalid("invalid_json");
          (result as JsonObject)[key] = value(depth + 1);
        } else (result as Json[]).push(value(depth + 1));
        whitespace();
        if (text[position] === end) {
          position++;
          return result;
        }
        if (text[position++] !== ",") invalid("invalid_json");
      }
      invalid("invalid_json");
    }
    for (const [token, result] of [
      ["true", true],
      ["false", false],
      ["null", null],
    ] as const) {
      if (text.startsWith(token, position)) {
        position += token.length;
        return result;
      }
    }
    number.lastIndex = position;
    const match = number.exec(text);
    if (!match) invalid("invalid_json");
    position = number.lastIndex;
    const result = Number(match[0]);
    if (!Number.isFinite(result)) invalid("invalid_json_value");
    return new JsonNumber(result, !/[.eE]/.test(match[0]));
  }
  const result = value(0);
  whitespace();
  if (position !== text.length) invalid("invalid_json");
  return result;
}

function record(value: Json, fields: string[], code: string): JsonObject {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    value instanceof JsonNumber
  )
    invalid(code);
  const keys = Object.keys(value);
  if (
    keys.length !== fields.length ||
    fields.some((field) => !Object.hasOwn(value, field))
  )
    invalid(code);
  return value;
}
function list(value: Json, maximum: number): Json[] {
  if (!Array.isArray(value) || value.length > maximum)
    invalid("collection_limit_exceeded");
  return value;
}
function matches(value: Json, pattern: RegExp): value is string {
  return typeof value === "string" && pattern.exec(value)?.[0] === value;
}
function identifier(value: Json, prefix: string): string {
  if (
    !matches(value, /^[A-Za-z][A-Za-z0-9-]{0,79}$/) ||
    !value.startsWith(prefix + "-") ||
    !/^[A-Za-z0-9]/.test(value.slice(prefix.length + 1))
  )
    invalid("invalid_identifier");
  return value;
}
function path(value: Json): string {
  if (
    !matches(value, /^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$/) ||
    value
      .split("/")
      .some(
        (part) =>
          !part ||
          part === "." ||
          part === ".." ||
          part.endsWith(".") ||
          /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part),
      )
  )
    invalid("unsafe_path");
  return value;
}
function timestamp(value: Json): string {
  if (typeof value !== "string") invalid("invalid_timestamp");
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{6}))?\+00:00$/.exec(
      value,
    );
  if (!match || match[0] !== value) invalid("invalid_timestamp");
  const [, year, month, day, hour, minute, second, micro] = match;
  const y = Number(year),
    m = Number(month),
    d = Number(day);
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (
    y < 1 ||
    m < 1 ||
    m > 12 ||
    d < 1 ||
    d > days[m - 1] ||
    Number(hour) > 23 ||
    Number(minute) > 59 ||
    Number(second) > 59 ||
    micro === "000000"
  )
    invalid("invalid_timestamp");
  return value;
}
function uniquePaths(rows: Json[], manifest: boolean): Map<string, JsonObject> {
  const result = new Map<string, JsonObject>();
  const folded = new Set<string>();
  for (const item of rows) {
    const row = record(
      item,
      manifest ? ["path", "sha256", "bytes"] : ["path", "content"],
      "invalid_file_entry",
    );
    const name = path(row.path);
    if (folded.has(name.toLowerCase())) invalid("duplicate_path");
    folded.add(name.toLowerCase());
    if (manifest) {
      if (!matches(row.sha256, /^[a-f0-9]{64}$/)) invalid("invalid_hash");
      const size = row.bytes;
      if (
        !(size instanceof JsonNumber) ||
        !size.integer ||
        !Number.isSafeInteger(size.value) ||
        size.value < 0 ||
        size.value > MAX_FILE_BYTES
      )
        invalid("invalid_file_size");
    } else if (
      typeof row.content !== "string" ||
      utf8(row.content).byteLength > MAX_FILE_BYTES
    )
      invalid("file_bytes_exceeded");
    result.set(name, row);
  }
  return result;
}
function container(raw: string | Uint8Array) {
  const value = record(
    parse(raw),
    ["format_version", "manifest", "files"],
    "invalid_container",
  );
  if (value.format_version !== "1") invalid("invalid_container");
  const manifest = record(
    value.manifest,
    [
      "format_version",
      "incident_id",
      "scenario_id",
      "projection",
      "generated_at",
      "evidence_ids",
      "files",
      "application",
      "limitations",
    ],
    "invalid_manifest",
  );
  if (manifest.format_version !== "1") invalid("invalid_manifest");
  const incident = identifier(manifest.incident_id, "INC");
  const generated = timestamp(manifest.generated_at);
  if (
    (manifest.scenario_id !== null &&
      manifest.scenario_id !== "atlas-compromise") ||
    (manifest.projection !== "public_synthetic" &&
      manifest.projection !== "local_review")
  )
    invalid("invalid_manifest");
  const application = record(
    manifest.application,
    ["name", "version"],
    "invalid_manifest",
  );
  const limitations = manifest.limitations;
  if (
    application.name !== "AegisGraph" ||
    application.version !== "0.1.0" ||
    !Array.isArray(limitations) ||
    limitations.length !== BUNDLE_LIMITATIONS.length ||
    BUNDLE_LIMITATIONS.some((line, index) => limitations[index] !== line)
  )
    invalid("invalid_manifest");
  const ids = list(manifest.evidence_ids, 80).map((item) =>
    identifier(item, "EVD"),
  );
  if (new Set(ids).size !== ids.length) invalid("duplicate_identifier");
  const expected = uniquePaths(list(manifest.files, 100), true);
  const actual = uniquePaths(list(value.files, 100), false);
  const inventory = new Set([
    ...FIXED_PATHS,
    ...ids.map((id) => `evidence/${id}.json`),
  ]);
  if (
    expected.size !== inventory.size ||
    [...expected.keys()].some((name) => !inventory.has(name))
  )
    invalid("invalid_manifest_inventory");
  const folded = new Map(
    [...expected.keys()].map((name) => [name.toLowerCase(), name]),
  );
  if (
    [...actual.keys()].some(
      (name) =>
        folded.has(name.toLowerCase()) &&
        name !== folded.get(name.toLowerCase()),
    )
  )
    invalid("duplicate_path");
  const metadata: BundleManifest = {
    format_version: "1",
    incident_id: incident,
    scenario_id: manifest.scenario_id,
    projection: manifest.projection,
    generated_at: generated,
    evidence_ids: ids,
    application: { name: "AegisGraph", version: "0.1.0" },
    limitations: [...BUNDLE_LIMITATIONS],
    files: [...expected].map(([name, row]) => ({
      path: name,
      sha256: row.sha256 as string,
      bytes: (row.bytes as JsonNumber).value,
    })),
  };
  return { expected, actual, metadata };
}

export async function verifyBundle(
  raw: string | Uint8Array,
): Promise<BundleVerification> {
  let bundle: ReturnType<typeof container>;
  try {
    bundle = container(raw);
  } catch (error) {
    if (!(error instanceof InvalidBundle)) throw error;
    return {
      status: "INVALID",
      findings: [{ status: "INVALID", code: error.message }],
      checked_files: 0,
      limitations: [...BUNDLE_LIMITATIONS],
    };
  }
  if (!globalThis.crypto?.subtle)
    throw new Error("Secure browser SHA-256 verification is unavailable.");
  const findings: BundleFinding[] = [];
  let checked = 0;
  for (const [name, entry] of [...bundle.expected].sort(([left], [right]) =>
    left < right ? -1 : left > right ? 1 : 0,
  )) {
    const file = bundle.actual.get(name);
    if (!file) {
      findings.push({
        status: "MISSING FILE",
        path: name,
        code: "file_missing",
      });
      continue;
    }
    checked++;
    const bytes = utf8(file.content as string);
    let digest: ArrayBuffer;
    try {
      digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    } catch {
      throw new Error("Secure browser SHA-256 verification is unavailable.");
    }
    const hash = Array.from(new Uint8Array(digest), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    if (
      bytes.byteLength !== (entry.bytes as JsonNumber).value ||
      hash !== entry.sha256
    )
      findings.push({
        status: "MODIFIED",
        path: name,
        code: "content_mismatch",
      });
  }
  for (const name of [...bundle.actual.keys()]
    .filter((name) => !bundle.expected.has(name))
    .sort())
    findings.push({
      status: "UNEXPECTED FILE",
      path: name,
      code: "file_unlisted",
    });
  const status =
    (["MODIFIED", "MISSING FILE", "UNEXPECTED FILE"] as const).find(
      (candidate) => findings.some((finding) => finding.status === candidate),
    ) ?? "VALID";
  return {
    status,
    findings,
    checked_files: checked,
    limitations: [...BUNDLE_LIMITATIONS],
    manifest: bundle.metadata,
  };
}
