import { LockClosedIcon } from "@heroicons/react/24/solid";

export function LockRevealPanel() {
  return (
    <section className="panel flex items-start gap-3">
      <LockClosedIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
      <div>
        <p className="eyebrow">Result lock</p>
        <p className="empty-state">A result must be eligible and SHA-256 locked before reveal.</p>
      </div>
    </section>
  );
}

