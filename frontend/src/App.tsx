import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import DotField from "./components/DotField";
import { Landing } from "@/components/Landing";
import { PatientLogin } from "@/components/PatientLogin";
import { PatientView } from "@/components/PatientView";
import { RadarDashboard } from "@/components/RadarDashboard";
import { RequireAuth } from "@/components/RequireAuth";
import { StaffLogin } from "@/components/StaffLogin";

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

      {/* Two separate surfaces. The guards below are UX only — every rule they express
          is enforced independently server-side in auth/deps.py. */}
      <div className="relative">
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />

            <Route path="/hospital/login" element={<StaffLogin />} />
            <Route
              path="/hospital"
              element={
                <RequireAuth kind="staff" loginPath="/hospital/login">
                  <RadarDashboard />
                </RequireAuth>
              }
            />

            <Route path="/patient/login" element={<PatientLogin />} />
            <Route
              path="/patient"
              element={
                <RequireAuth kind="patient" loginPath="/patient/login">
                  <PatientView />
                </RequireAuth>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </div>
    </div>
  );
}
