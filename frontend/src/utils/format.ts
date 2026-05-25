import type { StageName } from "../types/api";

export function formatNumber(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const parsed = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return new Intl.NumberFormat("en-IN").format(parsed);
}

export function formatMeters(value: number | string | null | undefined): string {
  const formatted = formatNumber(value);
  return formatted === "-" ? formatted : `${formatted} m`;
}

export function formatCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const parsed = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(parsed);
}

export function formatDate(value: string | null | undefined): string {
  if (!value || value === "-") {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function stageShortName(stage: StageName): string {
  const labels: Record<StageName, string> = {
    fabric_ready: "Fabric",
    cutting: "Cutting",
    stitching: "Stitching",
    size_inspection: "Inspection",
    quality_check: "Quality",
    packing: "Packing",
    dispatch: "Dispatch",
  };
  return labels[stage];
}
