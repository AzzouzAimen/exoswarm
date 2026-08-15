import { AdaptiveDecisionPanel } from "./AdaptiveDecisionPanel";
import { AgentActivity } from "./AgentActivity";
import { CentralOrbitScene } from "./CentralOrbitScene";
import { EvidenceLedger } from "./EvidenceLedger";
import { HypothesisPanel } from "./HypothesisPanel";
import { LockRevealPanel } from "./LockRevealPanel";
import { ScientificPlotPanel } from "./ScientificPlotPanel";
import { TargetStatus } from "./TargetStatus";

export function MissionControlShell() {
  return (
    <main className="mx-auto grid min-h-screen max-w-[1600px] gap-4 p-4 lg:p-6">
      <TargetStatus />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(20rem,0.8fr)]">
        <div className="grid gap-4">
          <CentralOrbitScene />
          <ScientificPlotPanel />
        </div>
        <aside className="grid content-start gap-4">
          <HypothesisPanel />
          <AgentActivity />
          <AdaptiveDecisionPanel />
          <EvidenceLedger />
          <LockRevealPanel />
        </aside>
      </div>
    </main>
  );
}

