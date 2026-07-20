import { Link } from "react-router-dom";
import { Building2, FlaskConical, Radar, User } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function Landing() {
  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-4 py-10">
      <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
        <Radar className="size-7 text-primary" />
        ClaimGuard
      </h1>
      <p className="mt-2 max-w-xl leading-relaxed text-foreground/70">
        Appeals grounded in your <em className="font-serif text-lg">actual</em> policy
        clauses — and an honest refusal when the policy doesn&apos;t support one.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Link to="/hospital/login" className="group">
          <Card className="h-full transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg">
            <CardContent className="pt-2">
              <Building2 className="size-6 text-primary" />
              <div className="mt-2 text-base font-medium">Hospital staff</div>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                Compliance Radar — where claim time is lost across all records, against
                the IRDAI SLA.
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link to="/patient/login" className="group">
          <Card className="h-full transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg">
            <CardContent className="pt-2">
              <User className="size-6 text-primary" />
              <div className="mt-2 text-base font-medium">Patient</div>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                Your claim, in plain language, in your language. Sign in with your ABHA
                id or policy number.
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <p className="mt-8 inline-flex items-start gap-1.5 text-xs leading-relaxed text-foreground/50">
        <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-primary" />
        <span>
          Synthetic data and a <strong>simulated</strong> login throughout. Real ABHA
          authentication runs through ABDM and requires organisation-level registration —
          never enter a real ABHA id or policy number here.
        </span>
      </p>
    </div>
  );
}
