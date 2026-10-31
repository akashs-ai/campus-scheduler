const fs = require("node:fs");
const path = require("node:path");
const root = path.join(__dirname, "..", "exports");
const files = ["schedule.json", "schedule_after.json"];
for (const file of files) {
  const data = JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
  if (!data.metadata.validated || data.metadata.hardConstraintViolations !== 0 || !Array.isArray(data.sessions)) {
    throw new Error(`${file} failed the export contract`);
  }
  const occupied = new Set();
  for (const session of data.sessions) {
    const key = `${session.day}|${session.startPeriod}|${session.room}`;
    if (occupied.has(key)) throw new Error(`${file} has a room collision at ${key}`);
    occupied.add(key);
  }
  console.log(`${file}: valid (${data.sessions.length} sessions, 0 hard violations)`);
}
