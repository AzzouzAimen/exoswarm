import { LockClosedIcon } from "@heroicons/react/24/outline";

export function TargetStatus() {
  return (
    <header className="panel flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="eyebrow">Unknown target</p>
        <h1 className="m-0 text-xl font-semibold tracking-tight">No investigation selected</h1>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <LockClosedIcon className="h-4 w-4 text-cyan-300" />
        Ground truth locked
      </div>
    </header>
  );
}

