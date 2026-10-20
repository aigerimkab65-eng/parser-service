#!/usr/bin/env node
/**
 * Минимальный клиент parser-service (Node fetch).
 *
 *   API_KEY=... node examples/client.js https://example.com/
 *
 * Env: BASE_URL (default http://127.0.0.1:8000), API_KEY, TIMEOUT_MS (default 60000)
 */

const BASE_URL = (process.env.BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_KEY = process.env.API_KEY;
const TIMEOUT_MS = Number(process.env.TIMEOUT_MS || 60_000);
const target = process.argv[2] || "https://example.com/";

class ParserApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.name = "ParserApiError";
    this.code = code;
    this.status = status;
  }
}

async function parse(url, { base = BASE_URL, apiKey = API_KEY, timeoutMs = TIMEOUT_MS } = {}) {
  if (!apiKey) {
    throw new Error("Задайте API_KEY");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(`${base}/v1/parse`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ url, render: "never" }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new ParserApiError("TIMEOUT", `Таймаут ${timeoutMs} мс`, 0);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  let body;
  try {
    body = await response.json();
  } catch {
    throw new ParserApiError(
      "INVALID_RESPONSE",
      `Не JSON (HTTP ${response.status})`,
      response.status,
    );
  }

  if (!response.ok || (body && body.error)) {
    const err = body && body.error ? body.error : {};
    throw new ParserApiError(
      err.code || "HTTP_ERROR",
      err.message || `HTTP ${response.status}`,
      response.status,
    );
  }

  return body;
}

async function main() {
  try {
    const data = await parse(target);
    console.log(JSON.stringify(data, null, 2));
  } catch (err) {
    if (err instanceof ParserApiError) {
      console.error(
        JSON.stringify({ error: { code: err.code, message: err.message } }, null, 2),
      );
      process.exit(1);
    }
    console.error(err && err.message ? err.message : err);
    process.exit(1);
  }
}

main();
