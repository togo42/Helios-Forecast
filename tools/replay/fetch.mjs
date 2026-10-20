// Export hourly Recorder inputs only; replay itself needs no HA or network.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { haCall } from "./ha-ws.mjs";

export const WEATHER_FIELDS = ["cloud_cover", "ghi", "direct", "diffuse", "temperature", "wind_speed", "snow_depth"];

export function weatherStatisticIds(entryId) {
  if (typeof entryId !== "string" || !/^[a-zA-Z0-9_-]+$/.test(entryId)) {
    throw new Error("config entry_id must be a nonempty config entry identifier");
  }
  return Object.fromEntries(WEATHER_FIELDS.map((field) => [field, `helios_forecast:${entryId.toLowerCase()}_${field}`]));
}

export async function fetchInputs(config, start, end, call = haCall) {
  const mapping = weatherStatisticIds(config.entry_id);
  const production = config.production_statistic;
  if (typeof production !== "string" || !production) throw new Error("config production_statistic is required");
  const common = { type: "recorder/statistics_during_period", start_time: start.toISOString(), end_time: end.toISOString(), period: "hour" };
  const prod = await call({ ...common, statistic_ids: [production], types: ["change"], units: { energy: "kWh" } });
  const wx = await call({ ...common, statistic_ids: Object.values(mapping), types: ["mean"] });
  if (!(production in prod)) throw new Error("production statistic is missing from Recorder response");
  const weather = {};
  for (const [field, id] of Object.entries(mapping)) {
    // A missing statistic remains empty, never converted to a clear-sky or zero observation.
    weather[field] = (wx[id] ?? []).map((r) => [r.start, r.mean ?? null]);
  }
  return {
    production: prod[production].map((r) => [r.start, r.end, r.change ?? null]),
    weather,
    metadata: { entry_id: config.entry_id.toLowerCase(), production_statistic: production,
      start: start.toISOString(), end: end.toISOString(), fetched_at: new Date().toISOString(),
      weather_kind: "retrospective integration-owned hourly archive" },
  };
}

export async function main(argv = process.argv.slice(2)) {
  const options = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!["--config", "--data-dir", "--days", "--end"].includes(argv[i]) || !argv[i + 1]) {
      throw new Error("Usage: node tools/replay/fetch.mjs --config CONFIG --data-dir DIRECTORY [--days 75] [--end ISO]");
    }
    options[argv[i]] = argv[i + 1];
  }
  if (!options["--config"] || !options["--data-dir"]) throw new Error("--config and --data-dir are required");
  const days = Number(options["--days"] ?? 75);
  const end = options["--end"] ? new Date(options["--end"]) : new Date();
  if (!Number.isInteger(days) || days <= 0 || !Number.isFinite(end.getTime())) throw new Error("invalid days or end");
  const dataDir = path.resolve(options["--data-dir"]);
  for (const file of ["production.json", "weather.json", "metadata.json"]) {
    if (fs.existsSync(path.join(dataDir, file))) throw new Error(`refusing to overwrite ${file}; use a fresh data directory`);
  }
  const config = JSON.parse(fs.readFileSync(options["--config"], "utf8"));
  const start = new Date(end.getTime() - days * 86400e3);
  const inputs = await fetchInputs(config, start, end);
  fs.mkdirSync(dataDir, { recursive: true });
  for (const [key, value] of Object.entries(inputs)) {
    fs.writeFileSync(path.join(dataDir, `${key}.json`), JSON.stringify(value, null, 2) + "\n", { flag: "wx" });
  }
  console.log(`production: ${inputs.production.length} hours | weather: ${Object.values(inputs.weather).map((v) => v.length).join("/")} hours`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch((err) => { console.error(err.message); process.exitCode = 1; });
}
