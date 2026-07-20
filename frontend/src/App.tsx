import DotField from "./components/DotField";
import { RadarDashboard } from "./components/RadarDashboard";

export default function App() {
  return (
    <div className="relative min-h-screen">
      {/* Full-page DotField background (design-system/claimguard/MASTER.md) */}
      <div className="fixed inset-0" aria-hidden>
        <DotField
          dotRadius={2.5}
          dotSpacing={20}
          cursorRadius={100}
          cursorForce={0}
          bulgeOnly
          bulgeStrength={0}
          glowRadius={50}
          sparkle={false}
          waveAmplitude={0}
          gradientFrom="rgba(240, 34, 95, 0.35)"
          gradientTo="rgba(240, 122, 158, 0.25)"
          glowColor="#F2B9C9"
        />
      </div>
      <div className="relative">
        <RadarDashboard />
      </div>
    </div>
  );
}
