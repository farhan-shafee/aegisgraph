// Local HTTPS rehearsal only: temporary certificates and processes, no hosted deployment.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import https from "node:https";
import http from "node:http";

if (!process.env.DATABASE_URL?.startsWith("postgresql"))
  throw new Error("Supply a dedicated initialized PostgreSQL DATABASE_URL.");
const directory = path.resolve(".runtime/public-tls");
mkdirSync(directory, { recursive: true });
const key = path.join(directory, "key.pem");
const cert = path.join(directory, "cert.pem");
const openssl =
  process.env.E2E_OPENSSL ||
  (process.platform === "win32"
    ? "C:/Program Files/Git/usr/bin/openssl.exe"
    : "openssl");
const generated = spawnSync(
  openssl,
  [
    "req",
    "-x509",
    "-newkey",
    "rsa:2048",
    "-nodes",
    "-days",
    "2",
    "-keyout",
    key,
    "-out",
    cert,
    "-subj",
    "/CN=localhost",
    "-addext",
    "subjectAltName=DNS:localhost,IP:127.0.0.1",
  ],
  { stdio: "ignore", windowsHide: true },
);
if (generated.status !== 0)
  throw new Error("Could not generate temporary HTTPS test certificate.");

const pythonPath = path.resolve(
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const python =
  process.env.E2E_PYTHON || (existsSync(pythonPath) ? pythonPath : "python");
const env = {
  ...process.env,
  APP_MODE: "public_demo",
  AEGISGRAPH_LOAD_ENV: "false",
  AI_PROVIDER: "deterministic",
  ALLOWED_ORIGINS: "https://127.0.0.1:3443",
  ALLOWED_HOSTS: "127.0.0.1,localhost",
  API_INTERNAL_URL: "https://127.0.0.1:8443",
  NODE_EXTRA_CA_CERTS: cert,
  NEXT_TELEMETRY_DISABLED: "1",
};
delete env.OPENAI_API_KEY;
delete env.OPENAI_MODEL;
const children = [
  spawn(
    python,
    [
      "-m",
      "uvicorn",
      "aegisgraph.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8101",
      "--no-access-log",
      "--no-proxy-headers",
    ],
    { env, stdio: "inherit", windowsHide: true },
  ),
  spawn(
    process.execPath,
    [
      "apps/web/node_modules/next/dist/bin/next",
      "start",
      "apps/web",
      "--hostname",
      "127.0.0.1",
      "--port",
      "3101",
    ],
    { env, stdio: "inherit", windowsHide: true },
  ),
];
const servers = [
  [8443, 8101],
  [3443, 3101],
].map(([port, target]) => {
  const server = https.createServer(
    { key: readFileSync(key), cert: readFileSync(cert) },
    (req, res) => {
      const upstream = http.request(
        {
          hostname: "127.0.0.1",
          port: target,
          path: req.url,
          method: req.method,
          headers: req.headers,
        },
        (response) => {
          res.writeHead(response.statusCode, response.headers);
          response.pipe(res);
        },
      );
      upstream.on("error", () => {
        res.writeHead(503);
        res.end("Test service starting");
      });
      req.pipe(upstream);
    },
  );
  server.listen(port, "127.0.0.1");
  return server;
});
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const server of servers) server.close();
  for (const child of children) child.kill();
  setTimeout(() => process.exit(code), 200).unref();
}
for (const child of children) {
  child.on("error", () => stop(1));
  child.on("exit", (code) => {
    if (!stopping) stop(code || 1);
  });
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
