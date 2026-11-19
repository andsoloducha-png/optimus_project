const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const sandbox = {
  console,
  Utilities: {
    parseDate(value) {
      return new Date(value.replace(" ", "T") + "Z");
    },
    formatDate(value) {
      return value.toISOString().slice(0, 19).replace("T", " ");
    }
  }
};
vm.createContext(sandbox);

for (const filename of ["Kod.gs.txt", "Czyszczenie.gs.txt"]) {
  const source = fs.readFileSync(
    path.join(root, "skrypty_google_sheets", filename),
    "utf8"
  );
  vm.runInContext(source, sandbox, {filename});
}

class FakeRange {
  constructor(sheet, row, column, rowCount, columnCount) {
    this.sheet = sheet;
    this.row = row - 1;
    this.column = column - 1;
    this.rowCount = rowCount;
    this.columnCount = columnCount;
  }

  getValues() {
    return this.values_(value => value);
  }

  getDisplayValues() {
    return this.values_(value => (value === null || value === undefined ? "" : String(value)));
  }

  setValues(values) {
    assert.equal(values.length, this.rowCount);
    values.forEach(row => assert.equal(row.length, this.columnCount));

    for (let r = 0; r < this.rowCount; r++) {
      const targetRow = this.row + r;
      while (this.sheet.rows.length <= targetRow) this.sheet.rows.push([]);
      for (let c = 0; c < this.columnCount; c++) {
        this.sheet.rows[targetRow][this.column + c] = values[r][c];
      }
    }
  }

  values_(convert) {
    const output = [];
    for (let r = 0; r < this.rowCount; r++) {
      const sourceRow = this.sheet.rows[this.row + r] || [];
      const row = [];
      for (let c = 0; c < this.columnCount; c++) {
        row.push(convert(sourceRow[this.column + c] ?? ""));
      }
      output.push(row);
    }
    return output;
  }
}

class FakeSheet {
  constructor(name, rows) {
    this.name = name;
    this.rows = rows.map(row => row.slice());
  }

  getName() {
    return this.name;
  }

  getLastRow() {
    return this.rows.length;
  }

  getLastColumn() {
    return this.rows.reduce((maximum, row) => Math.max(maximum, row.length), 0);
  }

  getRange(row, column, rowCount, columnCount) {
    return new FakeRange(this, row, column, rowCount, columnCount);
  }

  deleteRows(startRow, rowCount) {
    this.rows.splice(startRow - 1, rowCount);
  }
}

assert.equal(sandbox.parseArchiveDurationSeconds_("00:38:01"), 2281);
assert.equal(sandbox.parseArchiveDurationSeconds_("24:00:00"), 86400);
assert.equal(sandbox.parseArchiveDurationSeconds_("00:60:00"), null);
assert.equal(sandbox.parseArchiveDurationSeconds_("bad"), null);

const collisionSafeKeyA = sandbox.buildRowKey_(["a|b", "c"], [0, 1]);
const collisionSafeKeyB = sandbox.buildRowKey_(["a", "b|c"], [0, 1]);
assert.notEqual(collisionSafeKeyA, collisionSafeKeyB);

const targetSheet = new FakeSheet("alarm_events_db", [
  ["event_ts", "sorter_id", "code", "full_name", "duration"],
  ["2026-02-19 21:56:00", "20", 35, "Whisker activated", "00:00:39"]
]);
const sourceHeaders = [
  "event_ts",
  "sorter_id",
  "code",
  "full_name",
  "duration",
  "event_start_ts"
];

const targetHeaders = sandbox.ensureTargetHeaders_(targetSheet, sourceHeaders);
assert.deepEqual(Array.from(targetHeaders), sourceHeaders);
assert.equal(targetSheet.rows[0][5], "event_start_ts");

const fakeSpreadsheet = {
  getSpreadsheetTimeZone() {
    return "UTC";
  }
};
sandbox.backfillEventStartTimestamps_(
  fakeSpreadsheet,
  targetSheet,
  targetHeaders
);
assert.equal(targetSheet.rows[1][5], "2026-02-19 21:55:21");

const dateIndexes = sandbox.resolveDateHeaderIndexes_(
  sourceHeaders,
  ["event_start_ts", "event_ts"]
);
assert.deepEqual(Array.from(dateIndexes), [5, 0]);
assert.equal(
  sandbox.firstNonEmptyValue_(["2026-02-19 21:56:00", "", "", "", "", ""], dateIndexes),
  "2026-02-19 21:56:00"
);
assert.equal(
  sandbox.firstNonEmptyValue_(["2026-02-19 21:56:00", "", "", "", "", "2026-02-19 21:55:21"], dateIndexes),
  "2026-02-19 21:55:21"
);

const archiveSource = new FakeSheet("alarm_events", [
  sourceHeaders,
  ["2026-02-19 21:56:00", "20", 35, "Whisker activated", "00:00:39", "2026-02-19 21:55:21"],
  ["2026-02-19 22:00:00", "20", 35, "Whisker activated", "00:00:10", "2026-02-19 21:59:50"],
  ["2026-02-19 22:00:00", "20", 35, "Whisker activated", "00:00:10", "2026-02-19 21:59:50"]
]);
const archiveTarget = new FakeSheet("alarm_events_db", [
  ["event_ts", "sorter_id", "code", "full_name", "duration"],
  ["2026-02-19 21:56:00", "20", 35, "Whisker activated", "00:00:39"]
]);
const archiveSpreadsheet = {
  getSheetByName(name) {
    return name === "alarm_events" ? archiveSource : archiveTarget;
  },
  getSpreadsheetTimeZone() {
    return "UTC";
  }
};

sandbox.archiveSheet_(archiveSpreadsheet, {
  source: "alarm_events",
  target: "alarm_events_db",
  keyHeaders: ["event_ts", "sorter_id", "code", "full_name", "duration"],
  backfillEventStart: true
});
assert.equal(archiveTarget.rows.length, 3);
assert.equal(archiveTarget.rows[0][5], "event_start_ts");
assert.equal(archiveTarget.rows[1][5], "2026-02-19 21:55:21");
assert.equal(archiveTarget.rows[2][5], "2026-02-19 21:59:50");

const cleanupSheet = new FakeSheet("alarm_events_db", [
  sourceHeaders,
  ["2099-01-01 00:00:10", "20", 35, "future", "00:00:10", "2099-01-01 00:00:00"],
  ["2099-01-01 00:00:10", "20", 35, "old by start", "00:00:10", "2000-01-01 00:00:00"]
]);
const deletedRows = sandbox.deleteRowsOlderThan_(
  cleanupSheet,
  ["event_start_ts", "event_ts"],
  90
);
assert.equal(deletedRows, 1);
assert.equal(cleanupSheet.rows.length, 2);
assert.equal(cleanupSheet.rows[1][3], "future");

const parsedDate = sandbox.parseDateFromSheetValue_("2026-03-23 08:22:36");
assert.equal(parsedDate.getFullYear(), 2026);
assert.equal(parsedDate.getMonth(), 2);
assert.equal(parsedDate.getDate(), 23);

console.log("Google Sheets scripts: all tests passed");
