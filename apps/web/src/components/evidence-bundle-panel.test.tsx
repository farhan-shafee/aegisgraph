import { webcrypto } from "node:crypto";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  act,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import golden from "@/test/evidence-bundle-golden.json";
import { MAX_BUNDLE_BYTES } from "@/lib/evidence-bundle";
import { EvidenceBundlePanel } from "./evidence-bundle-panel";

const bytes = () => new TextEncoder().encode(JSON.stringify(golden));
const fetcher = vi.fn();
const createUrl = vi.fn(() => "blob:synthetic-bundle");
const revokeUrl = vi.fn();

function selectFile(
  name: string,
  read: () => Promise<ArrayBuffer>,
  size = bytes().byteLength,
) {
  const file = new File([], name, { type: "application/json" });
  Object.defineProperties(file, {
    arrayBuffer: { value: read },
    size: { value: size },
  });
  fireEvent.change(screen.getByLabelText("Verify a local bundle"), {
    target: { files: [file] },
  });
}

beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  vi.stubGlobal("fetch", fetcher);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createUrl,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: revokeUrl,
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fetcher.mockReset();
  createUrl.mockClear();
  revokeUrl.mockClear();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("evidence bundle panel", () => {
  it("requests export only after a click, verifies it, and revokes the download URL", async () => {
    fetcher.mockResolvedValue(new Response(bytes(), { status: 200 }));
    const { unmount } = render(<EvidenceBundlePanel incidentId="INC-golden" />);
    expect(fetcher).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Download evidence bundle" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("VALID"),
    );
    expect(fetcher).toHaveBeenCalledWith(
      "/api/incidents/INC-golden/export",
      expect.objectContaining({ method: "GET" }),
    );
    expect(
      screen.getByRole("link", { name: "Download verified bundle again" }),
    ).toHaveAttribute("download", "AegisGraph-INC-golden.json");
    expect(screen.getByText(/9 of 9 declared files checked/)).toBeVisible();
    expect(screen.getByText(/unsigned and replaceable/)).toBeVisible();
    expect(createUrl).toHaveBeenCalledOnce();
    unmount();
    expect(revokeUrl).toHaveBeenCalledWith("blob:synthetic-bundle");
  });

  it("verifies selected files locally without uploading or displaying their contents", async () => {
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    selectFile("review.json", async () => bytes().buffer);
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("VALID"),
    );
    expect(screen.getByText("review.json")).toBeVisible();
    expect(fetcher).not.toHaveBeenCalled();
    expect(createUrl).not.toHaveBeenCalled();
    expect(screen.queryByText("Synthetic café / café / 東京 / 🔎")).toBeNull();
  });

  it("blocks oversized files before reading them", async () => {
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    const reader = vi.fn();
    selectFile("large.json", reader, MAX_BUNDLE_BYTES + 1);
    expect(await screen.findByRole("alert")).toHaveTextContent("2 MiB");
    expect(reader).not.toHaveBeenCalled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("shows a safe download failure without exposing backend error contents", async () => {
    fetcher.mockResolvedValue(new Response("private-canary", { status: 500 }));
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    await userEvent.click(
      screen.getByRole("button", { name: "Download evidence bundle" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Export could not be downloaded",
    );
    expect(screen.queryByText("private-canary")).toBeNull();
    expect(createUrl).not.toHaveBeenCalled();
  });

  it("clears an earlier passing result when another file cannot be read", async () => {
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    selectFile("good.json", async () => bytes().buffer);
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("VALID"),
    );
    selectFile("unreadable.json", async () => {
      throw new Error("private-read-error");
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The selected file could not be read",
    );
    expect(screen.getByRole("status")).not.toHaveTextContent("VALID");
    expect(screen.queryByText("private-read-error")).toBeNull();
  });

  it("ignores stale asynchronous reads when a newer file is selected", async () => {
    let finish!: (value: ArrayBuffer) => void;
    const delayed = new Promise<ArrayBuffer>((resolve) => {
      finish = resolve;
    });
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    selectFile("old-valid.json", () => delayed);
    selectFile(
      "new-invalid.json",
      async () => new TextEncoder().encode("invalid").buffer,
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("INVALID"),
    );
    await act(async () => finish(bytes().buffer));
    expect(screen.getByText("new-invalid.json")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("INVALID");
    expect(screen.queryByText("old-valid.json")).toBeNull();
  });

  it("aborts an export and ignores its late result when a local file replaces it", async () => {
    let finish!: (value: Response) => void;
    fetcher.mockReturnValue(
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
    );
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    await userEvent.click(
      screen.getByRole("button", { name: "Download evidence bundle" }),
    );
    const signal = fetcher.mock.calls[0][1].signal as AbortSignal;
    selectFile(
      "new-invalid.json",
      async () => new TextEncoder().encode("invalid").buffer,
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("INVALID"),
    );
    expect(signal.aborted).toBe(true);
    await act(async () => finish(new Response(bytes(), { status: 200 })));
    expect(screen.getByText("new-invalid.json")).toBeVisible();
    expect(createUrl).not.toHaveBeenCalled();
  });

  it("does not offer a download for modified server content", async () => {
    const modified = structuredClone(golden);
    modified.files[0].content += "extra";
    fetcher.mockResolvedValue(
      new Response(JSON.stringify(modified), { status: 200 }),
    );
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    await userEvent.click(
      screen.getByRole("button", { name: "Download evidence bundle" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("MODIFIED"),
    );
    expect(createUrl).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("link", { name: "Download verified bundle again" }),
    ).toBeNull();
  });

  it("bounds streamed responses even when content length is absent", async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream({
      start(control) {
        control.enqueue(new Uint8Array(MAX_BUNDLE_BYTES));
        control.enqueue(new Uint8Array([0]));
      },
      cancel,
    });
    fetcher.mockResolvedValue(new Response(stream, { status: 200 }));
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    await userEvent.click(
      screen.getByRole("button", { name: "Download evidence bundle" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Export could not be downloaded",
    );
    expect(cancel).toHaveBeenCalledOnce();
    expect(createUrl).not.toHaveBeenCalled();
  });

  it("revokes an earlier download when another file is selected", async () => {
    fetcher.mockResolvedValue(new Response(bytes(), { status: 200 }));
    render(<EvidenceBundlePanel incidentId="INC-golden" />);
    await userEvent.click(
      screen.getByRole("button", { name: "Download evidence bundle" }),
    );
    await waitFor(() => expect(createUrl).toHaveBeenCalledOnce());
    selectFile("review.json", async () => bytes().buffer);
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("VALID"),
    );
    expect(revokeUrl).toHaveBeenCalledWith("blob:synthetic-bundle");
    expect(
      screen.queryByRole("link", { name: "Download verified bundle again" }),
    ).toBeNull();
  });
});
