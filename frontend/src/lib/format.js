const DHAKA = "Asia/Dhaka";

const moneyFormatter = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatMoney(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return "—";
  }
  const sign = number < 0 ? "−" : "";
  return `${sign}৳${moneyFormatter.format(Math.abs(number))}`;
}

const dateFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: DHAKA,
  day: "numeric",
  month: "short",
  year: "numeric",
});

const dateTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: DHAKA,
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

export function formatDate(value) {
  if (!value) return "—";
  return dateFormatter.format(new Date(value));
}

export function formatDateTime(value) {
  if (!value) return "—";
  return dateTimeFormatter.format(new Date(value));
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "Not enough data";
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 6) / 10;
  if (hours < 24) return `${hours} hr`;
  return `${Math.round(hours / 24)} days`;
}

export function formatPercent(value) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(Number(value))}%`;
}

export function formatTime(value) {
  if (!value) return "";
  const [hour, minute] = value.split(":").map(Number);
  const suffix = hour >= 12 ? "pm" : "am";
  const twelve = hour % 12 === 0 ? 12 : hour % 12;
  return minute ? `${twelve}:${String(minute).padStart(2, "0")}${suffix}` : `${twelve}${suffix}`;
}

export function toDateInputValue(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: DHAKA,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
  return parts;
}

const clockFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: DHAKA,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function toTimeInputValue(date) {
  return clockFormatter.format(date);
}

export function dhakaLocalToIso(dateValue, timeValue) {
  return new Date(`${dateValue}T${timeValue}:00+06:00`).toISOString();
}

export function plural(count, singular, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

const monthFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: DHAKA,
  month: "long",
  year: "numeric",
});

export function formatPeriod(value, period) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00+06:00`);
  if (period === "month") return monthFormatter.format(date);
  if (period === "week") return `Week of ${dateFormatter.format(date)}`;
  return dateFormatter.format(date);
}
