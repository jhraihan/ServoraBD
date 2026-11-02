import { describe, expect, it } from "vitest";

import {
  dhakaLocalToIso, formatDuration, formatMoney, formatPercent, formatPeriod, formatTime, plural,
  toTimeInputValue,
} from "./format";

describe("formatMoney", () => {
  it("uses the taka sign and South Asian digit grouping", () => {
    expect(formatMoney("150000.00")).toBe("৳1,50,000");
    expect(formatMoney("2000.00")).toBe("৳2,000");
  });

  it("keeps paisa when present", () => {
    expect(formatMoney("1234.56")).toBe("৳1,234.56");
  });

  it("renders negative ledger amounts with a true minus sign", () => {
    expect(formatMoney("-240.00")).toBe("−৳240");
  });

  it("shows a dash for missing or unparsable values", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney(undefined)).toBe("—");
    expect(formatMoney("")).toBe("—");
    expect(formatMoney("abc")).toBe("—");
  });
});

describe("formatDuration", () => {
  it.each([
    [null, "Not enough data"],
    [45, "45 sec"],
    [480, "8 min"],
    [6 * 3600, "6 hr"],
    [3 * 86400, "3 days"],
  ])("formats %s seconds as %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });
});

describe("formatPercent", () => {
  it("rounds and handles missing rates", () => {
    expect(formatPercent(94.3)).toBe("94%");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatTime", () => {
  it.each([
    ["09:00", "9am"],
    ["12:00", "12pm"],
    ["15:30", "3:30pm"],
    ["00:00", "12am"],
  ])("formats %s as %s", (value, expected) => {
    expect(formatTime(value)).toBe(expected);
  });
});

describe("dhakaLocalToIso", () => {
  it("treats the date and time as Dhaka local time regardless of the browser zone", () => {
    expect(dhakaLocalToIso("2026-10-01", "09:00")).toBe("2026-10-01T03:00:00.000Z");
  });
});

describe("plural", () => {
  it("never says 1 jobs", () => {
    expect(plural(1, "job")).toBe("1 job");
    expect(plural(0, "job")).toBe("0 jobs");
    expect(plural(2, "completed job")).toBe("2 completed jobs");
  });
});

describe("toTimeInputValue", () => {
  it("reads the wall clock in Dhaka on a 24-hour clock", () => {
    expect(toTimeInputValue(new Date("2026-09-01T03:05:00Z"))).toBe("09:05");
    expect(toTimeInputValue(new Date("2026-09-01T18:30:00Z"))).toBe("00:30");
  });
});

describe("formatPeriod", () => {
  it("names months instead of showing their first day", () => {
    expect(formatPeriod("2026-09-01", "month")).toBe("September 2026");
  });

  it("labels weeks and days", () => {
    expect(formatPeriod("2026-09-21", "week")).toBe("Week of 21 Sept 2026");
    expect(formatPeriod("2026-09-25", "day")).toBe("25 Sept 2026");
  });
});
