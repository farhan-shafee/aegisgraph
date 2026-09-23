import { webcrypto } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import golden from "@/test/evidence-bundle-golden.json";
import { MAX_BUNDLE_BYTES, verifyBundle } from "./evidence-bundle";

beforeEach(() => vi.stubGlobal("crypto", webcrypto));

const copy = () => structuredClone(golden);

describe("browser evidence bundle verification", () => {
  it("matches a Python-built Unicode golden fixture and known SHA-256", async () => {
    const result = await verifyBundle(JSON.stringify(golden));
    expect(result.status).toBe("VALID");
    expect(result.checked_files).toBe(9);
    expect(
      result.manifest?.files.find((file) => file.path === "incident.json"),
    ).toEqual({
      path: "incident.json",
      bytes: 71,
      sha256:
        "93223c756414c0ebf113e1a38d9e7c26155cef449ee1ec85d3eae10c10d1bf10",
    });
    expect(
      (await verifyBundle(new TextEncoder().encode(JSON.stringify(golden))))
        .status,
    ).toBe("VALID");
  });

  it("detects exact Unicode and newline modifications", async () => {
    for (const replacement of ["normalized", "newline"]) {
      const bundle = copy();
      const file = bundle.files.find((item) => item.path === "incident.json")!;
      file.content =
        replacement === "normalized"
          ? file.content.normalize("NFC")
          : file.content + "\r\n";
      expect((await verifyBundle(JSON.stringify(bundle))).status).toBe(
        "MODIFIED",
      );
    }
  });

  it("lists missing and unexpected files without showing their contents", async () => {
    const bundle = copy();
    const missing = bundle.files.shift()!.path;
    bundle.files.push({
      path: "extra.txt",
      content: "<script>private-canary</script>",
    });
    const result = await verifyBundle(JSON.stringify(bundle));
    expect(result.status).toBe("MISSING FILE");
    expect(result.findings).toEqual([
      { status: "MISSING FILE", path: missing, code: "file_missing" },
      { status: "UNEXPECTED FILE", path: "extra.txt", code: "file_unlisted" },
    ]);
    expect(JSON.stringify(result)).not.toContain("private-canary");
  });

  it("reports an extra safe file independently", async () => {
    const bundle = copy();
    bundle.files.push({ path: "extra.txt", content: "unlisted" });
    expect((await verifyBundle(JSON.stringify(bundle))).status).toBe(
      "UNEXPECTED FILE",
    );
  });

  it("cannot authenticate replaced content and its unsigned manifest", async () => {
    const bundle = copy();
    const file = bundle.files[0];
    file.content = "abc";
    const entry = bundle.manifest.files.find(
      (item) => item.path === file.path,
    )!;
    entry.bytes = 3;
    entry.sha256 =
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
    bundle.manifest.incident_id = "INC-replaced";
    const result = await verifyBundle(JSON.stringify(bundle));
    expect(result.status).toBe("VALID");
    expect(result.limitations.join(" ")).toContain("unsigned and replaceable");
    expect(result.limitations.join(" ")).toContain("not authenticated");
  });

  it.each([
    "../secret",
    "/incident.json",
    "C:/x",
    "evidence\\x",
    "./x",
    "a//b",
    "NUL.txt",
    "a/%2e%2e/x",
    "x\u0000",
  ])("rejects unsafe path %s", async (path) => {
    const bundle = copy();
    bundle.files.push({ path, content: "hidden" });
    const result = await verifyBundle(JSON.stringify(bundle));
    expect(result.status).toBe("INVALID");
    expect(JSON.stringify(result)).not.toContain("hidden");
  });

  it.each([
    "duplicate-path",
    "case-collision",
    "unknown-version",
    "unknown-field",
    "inventory",
    "size-boolean",
    "invalid-date",
    "stripped-limitations",
  ])("fails closed on %s", async (mutation) => {
    const bundle = copy();
    if (mutation === "duplicate-path")
      bundle.files.push({ ...bundle.files[0] });
    if (mutation === "case-collision")
      bundle.files.push({
        ...bundle.files[0],
        path: bundle.files[0].path.toUpperCase(),
      });
    if (mutation === "unknown-version") bundle.format_version = "2";
    if (mutation === "unknown-field")
      Object.assign(bundle.manifest, { extra: true });
    if (mutation === "inventory")
      bundle.manifest.evidence_ids.push("EVD-absent" as never);
    if (mutation === "size-boolean")
      Object.assign(bundle.manifest.files[0], { bytes: true });
    if (mutation === "invalid-date")
      bundle.manifest.generated_at = "2026-02-30T12:00:00+00:00";
    if (mutation === "stripped-limitations") bundle.manifest.limitations = [];
    expect((await verifyBundle(JSON.stringify(bundle))).status).toBe("INVALID");
  });

  it.each([
    ["duplicate-key", '{"a":1,"a":2}'],
    ["escaped-key", '{"a":1,"\\u0061":2}'],
    ["nested-duplicate", '{"a":{"b":1,"b":2}}'],
    ["nan", '{"a":NaN}'],
    ["overflow", '{"a":1e309}'],
    ["surrogate", '{"a":"\\ud800"}'],
    ["depth", "[".repeat(33) + "]".repeat(33)],
    ["bom", "\ufeff{}"],
    ["bytes", "x".repeat(MAX_BUNDLE_BYTES + 1)],
  ])("rejects malformed serialized input: %s", async (_name, text) => {
    expect((await verifyBundle(text)).status).toBe("INVALID");
  });

  it("rejects invalid UTF-8, UTF-16, and UTF-8 BOM", async () => {
    for (const bytes of [
      new Uint8Array([255]),
      new Uint8Array([255, 254, 123, 0, 125, 0]),
      new Uint8Array([239, 187, 191, 123, 125]),
    ]) {
      expect((await verifyBundle(bytes)).status).toBe("INVALID");
    }
  });

  it("preserves Python's integer-only byte-length validation", async () => {
    const text = JSON.stringify(golden);
    for (const token of ["1.0", "1e0", "-0.0"]) {
      expect(
        (await verifyBundle(text.replace(/"bytes":\d+/, `"bytes":${token}`)))
          .status,
      ).toBe("INVALID");
    }
  });

  it("bounds files and structural work even within the byte limit", async () => {
    const bundle = copy();
    bundle.files[0].content = "x".repeat(256 * 1024 + 1);
    expect((await verifyBundle(JSON.stringify(bundle))).status).toBe("INVALID");
    expect(
      (await verifyBundle('{"items":[' + "0,".repeat(100000) + "0]}")).status,
    ).toBe("INVALID");
  });

  it("reports unavailable hashing without claiming the file is invalid", async () => {
    vi.stubGlobal("crypto", {});
    await expect(verifyBundle(JSON.stringify(golden))).rejects.toThrow(
      "SHA-256 verification is unavailable",
    );
  });
});
