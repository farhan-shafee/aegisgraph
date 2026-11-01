// Database-free regression against a production Next server and local HTTPS API.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import https from "node:https";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const temp = await mkdtemp(path.join(os.tmpdir(), "aegisgraph-routing-"));
const cert = path.join(temp, "cert.pem");
const key = path.join(temp, "key.pem");
let child;
let backend;
let logs = "";
let runtimeStatus = 200;
let runtimeCalls = 0;
let dataCalls = 0;
let unsafe = false;
const runtime = {
  app_mode: "public_demo",
  read_only: true,
  analyst_provider: "deterministic",
  questions: ["What most likely happened?", "What malware family was used?"],
  capabilities: {},
};
try {
  const generated = spawnSync("openssl", [
    "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
    "-keyout", key, "-out", cert, "-subj", "/CN=127.0.0.1",
    "-addext", "subjectAltName=IP:127.0.0.1",
  ], { encoding: "utf8" });
  assert.equal(generated.status, 0, "local HTTPS certificate generation failed");
  backend = https.createServer({ key: await readFile(key), cert: await readFile(cert) }, (req, res) => {
    if (req.url === "/api/runtime") {
      runtimeCalls++;
      res.writeHead(runtimeStatus, { "Content-Type": "application/json", "Retry-After": "2" });
      res.end(JSON.stringify(unsafe ? { ...runtime, read_only: false } : runtime));
    } else {
      dataCalls++;
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "Not found" }));
    }
  });
  backend.listen(0, "127.0.0.1");
  await once(backend, "listening");
  const portProbe = net.createServer();
  portProbe.listen(0, "127.0.0.1");
  await once(portProbe, "listening");
  const port = portProbe.address().port;
  await new Promise((resolve) => portProbe.close(resolve));
  const base = `http://127.0.0.1:${port}`;
  child = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", String(port)], {
    cwd: path.join(root, "apps/web"),
    env: { ...process.env, NODE_ENV: "production", APP_MODE: "public_demo",
      API_INTERNAL_URL: `https://127.0.0.1:${backend.address().port}`,
      NODE_EXTRA_CA_CERTS: cert, NEXT_TELEMETRY_DISABLED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (data) => { logs += data; });
  child.stderr.on("data", (data) => { logs += data; });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw new Error("Next exited before readiness");
    try {
      const response = await fetch(`${base}/icon.svg`);
      await response.arrayBuffer();
      ready = response.status === 200;
      if (ready) break;
    } catch { /* Server is still starting. */ }
    await delay(100);
  }
  assert.ok(ready, "production Next server did not become ready");
  const missing = ["/__route_audit__", "/config.json", "/nested/absent.txt", "/architecture/absent", "/incidents/id/absent", "/api/config.json"];
  const checkMissing = async () => {
    for (const pathname of missing) {
      for (const method of ["GET", "HEAD"]) {
        const response = await fetch(`${base}${pathname}`, { method });
        await response.arrayBuffer();
        assert.equal(response.status, 404, `${method} ${pathname}`);
      }
    }
  };
  await checkMissing();
  assert.equal(runtimeCalls, 0, "unknown paths must not consume runtime/API budget");
  console.log("PASS: unknown paths and malformed API paths make zero runtime calls");
  const real = await fetch(`${base}/architecture`);
  const html = await real.text();
  assert.equal(real.status, 200);
  assert.ok(html.includes("Evidence is the system of record"));
  assert.equal(runtimeCalls, 1, "real page still validates the runtime");
  console.log("PASS: a real page retains runtime validation and application content");
  const dynamicPage = await fetch(`${base}/detections/APP-002`);
  assert.equal(dynamicPage.status, 200);
  assert.ok((await dynamicPage.text()).includes("Detection workbench"));
  const apiRoute = await fetch(`${base}/api/runtime`);
  assert.equal(apiRoute.status, 200);
  assert.deepEqual(await apiRoute.json(), runtime);
  console.log("PASS: specific dynamic pages, API routes and static assets retain priority");
  runtimeStatus = 429;
  const before = runtimeCalls;
  await checkMissing();
  assert.equal(runtimeCalls, before, "unknown paths must stay independent of a throttled backend");
  const throttled = await fetch(`${base}/api/overview`);
  assert.equal(throttled.status, 503);
  assert.equal(throttled.headers.get("retry-after"), "2");
  assert.ok(!(await throttled.text()).includes("127.0.0.1"));
  console.log("PASS: missing pages stay 404 while API throttling returns 503 and safe retry guidance");
  runtimeStatus = 200;
  unsafe = true;
  const rejected = await fetch(`${base}/events`);
  assert.equal(rejected.status, 500);
  await rejected.arrayBuffer();
  const deniedApi = await fetch(`${base}/api/overview`);
  assert.equal(deniedApi.status, 503);
  await deniedApi.arrayBuffer();
  assert.equal(dataCalls, 0, "unsafe runtime must not permit application-data requests");
  console.log("PASS: unsafe public runtime still fails closed for real pages and API routes");
} catch (error) {
  console.error(logs.slice(-3000));
  throw error;
} finally {
  if (child && child.exitCode === null) {
    child.kill("SIGTERM");
    await once(child, "exit");
  }
  if (backend) await new Promise((resolve) => backend.close(resolve));
  await rm(temp, { recursive: true, force: true });
}
