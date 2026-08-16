export type DataMode = "live" | "fixture"

export function configuredDataMode(value = process.env.NEXT_PUBLIC_EXOSWARM_DATA_MODE): DataMode {
  return value === "fixture" ? "fixture" : "live"
}
