"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AlertTriangle, Download, FileCheck2 } from "lucide-react";
import {
  BUNDLE_LIMITATIONS,
  MAX_BUNDLE_BYTES,
  verifyBundle,
  type BundleVerification,
} from "@/lib/evidence-bundle";
import { ErrorNotice, Panel } from "./ui";
import styles from "./evidence-bundle-panel.module.css";

type Display = {
  source: string;
  busy: boolean;
  error: string | null;
  result: BundleVerification | null;
};
type DownloadLink = { url: string; name: string };

async function responseBytes(
  response: Response,
): Promise<Uint8Array<ArrayBuffer>> {
  const declared = response.headers.get("content-length");
  if (declared && Number(declared) > MAX_BUNDLE_BYTES)
    throw new Error("export_limit");
  if (!response.body) throw new Error("export_unavailable");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BUNDLE_BYTES) {
        await reader.cancel();
        throw new Error("export_limit");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

/** Remount the operation scope when navigation changes the canonical case. */
export function EvidenceBundlePanel({ incidentId }: { incidentId: string }) {
  return <BundleTools key={incidentId} incidentId={incidentId} />;
}

function BundleTools({ incidentId }: { incidentId: string }) {
  const inputId = useId();
  const descriptionId = useId();
  const [display, setDisplay] = useState<Display>({
    source: "",
    busy: false,
    error: null,
    result: null,
  });
  const [download, setDownload] = useState<DownloadLink | null>(null);
  const operation = useRef(0);
  const mounted = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controller.current?.abort();
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
    };
  }, []);

  function begin(source: string) {
    const current = ++operation.current;
    controller.current?.abort();
    controller.current = null;
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
    setDownload(null);
    setDisplay({ source, busy: true, error: null, result: null });
    return current;
  }
  function active(current: number) {
    return mounted.current && operation.current === current;
  }
  function failed(current: number, message: string) {
    if (active(current))
      setDisplay((previous) => ({
        ...previous,
        busy: false,
        error: message,
        result: null,
      }));
  }

  async function exportBundle() {
    const current = begin("Current investigation export");
    if (
      !/^INC-[A-Za-z0-9][A-Za-z0-9-]{0,75}$/.test(incidentId) ||
      incidentId.includes("\n")
    ) {
      failed(current, "This investigation cannot be exported.");
      return;
    }
    const abort = new AbortController();
    controller.current = abort;
    let bytes: Uint8Array<ArrayBuffer>;
    try {
      const response = await fetch(
        `/api/incidents/${encodeURIComponent(incidentId)}/export`,
        {
          method: "GET",
          signal: abort.signal,
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) throw new Error("export_unavailable");
      bytes = await responseBytes(response);
    } catch {
      abort.abort();
      failed(
        current,
        "Export could not be downloaded. The case may exceed the bounded export limits; try again or inspect it locally.",
      );
      return;
    }
    if (!active(current)) return;
    let result: BundleVerification;
    try {
      result = await verifyBundle(bytes);
    } catch {
      failed(
        current,
        "Secure browser SHA-256 verification is unavailable. Use HTTPS or verify with the local CLI.",
      );
      return;
    }
    if (!active(current)) return;
    if (result.manifest && result.manifest.incident_id !== incidentId) {
      failed(current, "The export did not match the requested investigation.");
      return;
    }
    setDisplay((previous) => ({ ...previous, busy: false, result }));
    if (result.status !== "VALID") return;
    try {
      const url = URL.createObjectURL(
        new Blob([bytes], { type: "application/json" }),
      );
      objectUrl.current = url;
      const name = `AegisGraph-${incidentId}.json`;
      setDownload({ url, name });
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      document.body.append(link);
      link.click();
      link.remove();
    } catch {
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
      setDownload(null);
      failed(
        current,
        "The verified export could not be saved by this browser. Try downloading again.",
      );
    }
  }

  async function selectFile(file: File) {
    const current = begin(file.name.slice(0, 160));
    if (file.size > MAX_BUNDLE_BYTES) {
      failed(current, "Choose a bundle no larger than 2 MiB.");
      return;
    }
    let bytes: Uint8Array;
    try {
      bytes = new Uint8Array(await file.arrayBuffer());
    } catch {
      failed(current, "The selected file could not be read. Choose it again.");
      return;
    }
    if (!active(current)) return;
    try {
      const result = await verifyBundle(bytes);
      if (active(current))
        setDisplay((previous) => ({ ...previous, busy: false, result }));
    } catch {
      failed(
        current,
        "Secure browser SHA-256 verification is unavailable. Use HTTPS or verify with the local CLI.",
      );
    }
  }

  const result = display.result;
  const manifest = result?.manifest;
  return (
    <Panel
      title="Evidence bundle"
      subtitle="Export this investigation and inspect its exact file hashes."
    >
      <div className={styles.body}>
        <p className={styles.intro}>
          A hash-verifiable export of synthetic investigation material.
          Verification runs in your browser; selected files are never uploaded
          or extracted.
        </p>
        <div className={styles.controls}>
          <button
            type="button"
            className="button"
            onClick={exportBundle}
            disabled={display.busy}
          >
            <Download size={16} aria-hidden="true" /> Download evidence bundle
          </button>
          <div className={styles.fileInput}>
            <label htmlFor={inputId}>Verify a local bundle</label>
            <input
              id={inputId}
              type="file"
              accept=".json,application/json"
              aria-describedby={descriptionId}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = "";
                if (file) void selectFile(file);
              }}
            />
            <span id={descriptionId}>
              JSON container · maximum 2 MiB · stays on this device
            </span>
          </div>
        </div>
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className={styles.status}
        >
          {display.busy ? (
            "Checking exact UTF-8 file contents…"
          ) : result ? (
            <>
              {result.status === "VALID" ? (
                <FileCheck2 size={18} aria-hidden="true" />
              ) : (
                <AlertTriangle size={18} aria-hidden="true" />
              )}
              <strong>{result.status}</strong>
              <span>
                {result.status === "VALID"
                  ? "Contents match the supplied manifest."
                  : "The bundle needs inspection."}
              </span>
            </>
          ) : (
            "Choose an export or local file to verify."
          )}
        </div>
        <ErrorNotice message={display.error} />
        {display.source && <p className={styles.source}>{display.source}</p>}
        {download && (
          <a className="text-link" href={download.url} download={download.name}>
            Download verified bundle again
          </a>
        )}
        {result && (
          <div className={styles.result}>
            {manifest && (
              <>
                <p>
                  {result.checked_files} of {manifest.files.length} declared
                  files checked · SHA-256 · format {manifest.format_version}
                </p>
                <dl className={styles.metadata}>
                  <div>
                    <dt>Incident label</dt>
                    <dd>{manifest.incident_id}</dd>
                  </div>
                  <div>
                    <dt>Projection</dt>
                    <dd>
                      {manifest.projection === "public_synthetic"
                        ? "Public synthetic"
                        : "Local review"}
                    </dd>
                  </div>
                  <div>
                    <dt>Export time</dt>
                    <dd>{manifest.generated_at}</dd>
                  </div>
                  <div>
                    <dt>Evidence files</dt>
                    <dd>{manifest.evidence_ids.length}</dd>
                  </div>
                </dl>
                <p className={styles.note}>
                  {manifest.projection === "public_synthetic"
                    ? "Public exports omit owner, evidence annotations, findings, notes, audit entries, and human hypothesis review state. Empty collections describe this projection."
                    : "Local exports include bounded committed case material. Human actor labels are not authenticated identities."}
                </p>
              </>
            )}
            {result.findings.length > 0 && (
              <ul className={styles.findings}>
                {result.findings.map((finding, index) => (
                  <li key={`${finding.path ?? "invalid"}-${index}`}>
                    <strong>{finding.status}</strong>
                    {finding.path && <code>{finding.path}</code>}
                    <span>{finding.code.replaceAll("_", " ")}</span>
                  </li>
                ))}
              </ul>
            )}
            {manifest && (
              <details className={styles.files}>
                <summary>Inspect declared files and SHA-256 hashes</summary>
                <ul>
                  {manifest.files.map((file) => (
                    <li key={file.path}>
                      <strong>{file.path}</strong>
                      <span>{file.bytes.toLocaleString()} bytes</span>
                      <code>{file.sha256}</code>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
        <ul className={styles.limitations}>
          {BUNDLE_LIMITATIONS.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
