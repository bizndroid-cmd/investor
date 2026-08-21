import { useState } from "react";
import { apiFetch } from "@/api/client";
import {
  Compass, ArrowRight, ArrowLeft, Sparkles, Check, Eye, EyeOff,
  Target, PiggyBank, Home, Car, CreditCard, TrendingUp, Shield,
  Building, GraduationCap, Briefcase, Loader2,
} from "lucide-react";

interface OnboardingData {
  motivation: string;
  goals: string[];
  first_goal: string;
  email: string;
  password: string;
  about: string[];
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export function OnboardingPage({ onComplete }: { onComplete: () => void }) {
  const [frame, setFrame] = useState(0);
  const [data, setData] = useState<OnboardingData>({
    motivation: "",
    goals: [],
    first_goal: "",
    email: "",
    password: "",
    about: [],
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [direction, setDirection] = useState<"forward" | "back">("forward");

  const totalFrames = 7;

  const goNext = () => {
    setDirection("forward");
    setFrame((f) => Math.min(f + 1, totalFrames - 1));
    setError(null);
  };

  const goBack = () => {
    setDirection("back");
    setFrame((f) => Math.max(f - 1, 0));
    setError(null);
  };

  const handleCreateAccount = async () => {
    setLoading(true);
    setError(null);
    try {
      // Register
      await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email: data.email, password: data.password }),
      });
      goNext();
    } catch (err: any) {
      const msg = err?.body?.detail || err?.message || "Registration failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleFinish = async () => {
    setLoading(true);
    setError(null);
    try {
      // Login
      const tokens = await apiFetch<AuthTokens>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: data.email, password: data.password }),
      });
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);

      // Store onboarding profile
      try {
        await apiFetch("/user/onboarding-profile", {
          method: "POST",
          body: JSON.stringify({
            motivation: data.motivation,
            goals: data.goals,
            first_goal: data.first_goal,
            about: data.about,
          }),
        });
      } catch {
        // Non-critical — profile storage can fail silently
      }

      onComplete();
    } catch (err: any) {
      // If login fails (pending approval), show message
      const msg = err?.body?.detail || "Account pending approval. You'll be notified once approved.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="mb-8">
          <div className="h-1 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-700 ease-out"
              style={{ width: `${((frame + 1) / totalFrames) * 100}%` }}
            />
          </div>
          <p className="text-[10px] text-muted-foreground text-right mt-1.5">{frame + 1} of {totalFrames}</p>
        </div>

        {/* Frame container */}
        <div
          key={frame}
          className={`rounded-3xl border bg-card/95 backdrop-blur-sm p-8 shadow-2xl shadow-primary/5 ${
            direction === "forward" ? "animate-slide-in-right" : "animate-slide-in-left"
          }`}
        >
          {frame === 0 && <FrameMotivation value={data.motivation} onChange={(v) => setData({ ...data, motivation: v })} />}
          {frame === 1 && <FrameGoals value={data.goals} onChange={(v) => setData({ ...data, goals: v })} />}
          {frame === 2 && <FrameFirstGoal value={data.first_goal} onChange={(v) => setData({ ...data, first_goal: v })} />}
          {frame === 3 && <FrameEmail value={data.email} onChange={(v) => setData({ ...data, email: v })} />}
          {frame === 4 && (
            <FramePassword
              value={data.password}
              onChange={(v) => setData({ ...data, password: v })}
              showPassword={showPassword}
              onToggleShow={() => setShowPassword(!showPassword)}
            />
          )}
          {frame === 5 && <FrameAccountCreated />}
          {frame === 6 && <FrameAbout value={data.about} onChange={(v) => setData({ ...data, about: v })} />}

          {error && (
            <p className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2 mt-4">{error}</p>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8">
            {frame > 0 && frame !== 5 ? (
              <button onClick={goBack} className="btn-ghost text-xs">
                <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back
              </button>
            ) : (
              <div />
            )}

            {frame === 0 && (
              <button onClick={goNext} disabled={!data.motivation} className="btn-primary text-xs">
                Continue <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </button>
            )}
            {frame === 1 && (
              <button onClick={goNext} disabled={data.goals.length === 0} className="btn-primary text-xs">
                Continue <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </button>
            )}
            {frame === 2 && (
              <button onClick={goNext} disabled={!data.first_goal} className="btn-primary text-xs">
                Continue <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </button>
            )}
            {frame === 3 && (
              <button onClick={goNext} disabled={!data.email || !data.email.includes("@")} className="btn-primary text-xs">
                Continue <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </button>
            )}
            {frame === 4 && (
              <button onClick={handleCreateAccount} disabled={loading || data.password.length < 8} className="btn-primary text-xs">
                {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : null}
                Create Account
              </button>
            )}
            {frame === 5 && (
              <button onClick={goNext} className="btn-primary text-xs w-full justify-center">
                Continue <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </button>
            )}
            {frame === 6 && (
              <button onClick={handleFinish} disabled={loading} className="btn-primary text-xs">
                {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <Sparkles className="h-3.5 w-3.5 mr-1.5" />}
                Build My Blueprint
              </button>
            )}
          </div>
        </div>

        {/* Login link */}
        {frame < 4 && (
          <p className="text-center text-xs text-muted-foreground mt-6">
            Already have an account?{" "}
            <button onClick={onComplete} className="text-primary font-medium hover:underline">
              Sign in
            </button>
          </p>
        )}
      </div>
    </div>
  );
}

// ============================================================
// FRAMES
// ============================================================

function FrameMotivation({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const options = [
    { id: "net_worth", label: "Track my net worth", icon: TrendingUp },
    { id: "budget", label: "Create a financial plan", icon: Target },
    { id: "ai_assist", label: "Get AI-powered insights", icon: Sparkles },
    { id: "investments", label: "Monitor my investments", icon: Briefcase },
    { id: "goals", label: "Reach financial goals", icon: PiggyBank },
  ];

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Compass className="h-5 w-5 text-primary" />
        <span className="text-[10px] text-primary font-medium uppercase tracking-wider">RuDo</span>
      </div>
      <h2 className="text-xl font-bold mt-3">What brings you here?</h2>
      <p className="text-sm text-muted-foreground mt-1.5">Choose what resonates most with you.</p>

      <div className="space-y-2.5 mt-6">
        {options.map((opt) => {
          const Icon = opt.icon;
          const selected = value === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onChange(opt.id)}
              className={`w-full flex items-center gap-3 p-4 rounded-2xl border text-left transition-all duration-200 ${
                selected
                  ? "border-primary bg-primary/5 shadow-sm"
                  : "border-border hover:border-primary/30 hover:bg-secondary/30"
              }`}
            >
              <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${
                selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              }`}>
                <Icon className="h-4 w-4" />
              </div>
              <span className={`text-sm font-medium ${selected ? "text-primary" : ""}`}>{opt.label}</span>
              {selected && <Check className="h-4 w-4 text-primary ml-auto" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FrameGoals({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const options = [
    { id: "pay_debt", label: "Pay off my debt", icon: CreditCard },
    { id: "grow_savings", label: "Grow my savings", icon: TrendingUp },
    { id: "stay_on_top", label: "Stay on top of my finances", icon: Shield },
    { id: "invest_more", label: "Invest more wisely", icon: Briefcase },
    { id: "retire_early", label: "Plan for retirement", icon: PiggyBank },
    { id: "build_wealth", label: "Build long-term wealth", icon: Sparkles },
  ];

  const toggle = (id: string) => {
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  };

  return (
    <div>
      <h2 className="text-xl font-bold">What are your top financial goals?</h2>
      <p className="text-sm text-muted-foreground mt-1.5">Select all that apply.</p>

      <div className="grid grid-cols-2 gap-2.5 mt-6">
        {options.map((opt) => {
          const Icon = opt.icon;
          const selected = value.includes(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => toggle(opt.id)}
              className={`flex flex-col items-center gap-2 p-4 rounded-2xl border text-center transition-all duration-200 ${
                selected
                  ? "border-primary bg-primary/5 shadow-sm"
                  : "border-border hover:border-primary/30 hover:bg-secondary/30"
              }`}
            >
              <div className={`h-9 w-9 rounded-xl flex items-center justify-center ${
                selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              }`}>
                <Icon className="h-4 w-4" />
              </div>
              <span className={`text-xs font-medium leading-tight ${selected ? "text-primary" : ""}`}>{opt.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FrameFirstGoal({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const options = [
    { id: "emergency_fund", label: "Emergency fund", desc: "3-6 months of expenses", icon: Shield },
    { id: "house", label: "Buy a house", desc: "Save for down payment", icon: Home },
    { id: "car", label: "Buy a car", desc: "New or used vehicle fund", icon: Car },
    { id: "debt_free", label: "Become debt-free", desc: "Pay off all debts", icon: CreditCard },
    { id: "invest_1l", label: "First ₹1 Lakh invested", desc: "Building the habit", icon: TrendingUp },
    { id: "retire", label: "Retirement corpus", desc: "Long-term wealth", icon: PiggyBank },
  ];

  return (
    <div>
      <h2 className="text-xl font-bold">Let's turn one stone at a time</h2>
      <p className="text-sm text-muted-foreground mt-1.5">Pick your first savings goal. We'll build a plan around it.</p>

      <div className="space-y-2.5 mt-6">
        {options.map((opt) => {
          const Icon = opt.icon;
          const selected = value === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onChange(opt.id)}
              className={`w-full flex items-center gap-3 p-4 rounded-2xl border text-left transition-all duration-200 ${
                selected
                  ? "border-primary bg-primary/5 shadow-sm"
                  : "border-border hover:border-primary/30 hover:bg-secondary/30"
              }`}
            >
              <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${
                selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              }`}>
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <span className={`text-sm font-medium ${selected ? "text-primary" : ""}`}>{opt.label}</span>
                <p className="text-[10px] text-muted-foreground mt-0.5">{opt.desc}</p>
              </div>
              {selected && <Check className="h-4 w-4 text-primary ml-auto shrink-0" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FrameEmail({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <h2 className="text-xl font-bold">What's your email?</h2>
      <p className="text-sm text-muted-foreground mt-1.5">
        This will be your login to access RuDo.
      </p>

      <div className="mt-6">
        <input
          type="email"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="you@example.com"
          className="input-field text-base py-3.5"
          autoFocus
          autoComplete="email"
        />
        <p className="text-[10px] text-muted-foreground mt-2">We never share your email with anyone.</p>
      </div>
    </div>
  );
}

function FramePassword({
  value, onChange, showPassword, onToggleShow,
}: { value: string; onChange: (v: string) => void; showPassword: boolean; onToggleShow: () => void }) {
  const hasLower = /[a-z]/.test(value);
  const hasUpper = /[A-Z]/.test(value);
  const hasNumber = /\d/.test(value);
  const hasLength = value.length >= 8;

  return (
    <div>
      <h2 className="text-xl font-bold">Set your password</h2>
      <p className="text-sm text-muted-foreground mt-1.5">Create a secure password for your account.</p>

      <div className="mt-6 relative">
        <input
          type={showPassword ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Create password"
          className="input-field text-base py-3.5 pr-12"
          autoComplete="new-password"
        />
        <button
          type="button"
          onClick={onToggleShow}
          className="absolute right-3 top-1/2 -translate-y-1/2 btn-icon h-8 w-8"
        >
          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>

      {/* Requirements */}
      <div className="grid grid-cols-2 gap-2 mt-4">
        <Requirement met={hasLength} label="8+ characters" />
        <Requirement met={hasLower} label="1 lowercase" />
        <Requirement met={hasUpper} label="1 uppercase" />
        <Requirement met={hasNumber} label="1 number" />
      </div>
    </div>
  );
}

function Requirement({ met, label }: { met: boolean; label: string }) {
  return (
    <div className={`flex items-center gap-1.5 text-xs transition-colors ${met ? "text-emerald-500" : "text-muted-foreground"}`}>
      <div className={`h-4 w-4 rounded-full flex items-center justify-center transition-all ${
        met ? "bg-emerald-500/10" : "bg-muted"
      }`}>
        {met ? <Check className="h-2.5 w-2.5" /> : <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />}
      </div>
      {label}
    </div>
  );
}

function FrameAccountCreated() {
  return (
    <div className="text-center py-4">
      {/* Success animation */}
      <div className="relative mx-auto w-20 h-20 mb-6">
        <div className="absolute inset-0 rounded-full bg-emerald-500/10 animate-ping" />
        <div className="relative h-20 w-20 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30">
          <Check className="h-10 w-10 text-white animate-scale-in" />
        </div>
      </div>

      <h2 className="text-xl font-bold">Account created! 🎉</h2>
      <p className="text-sm text-muted-foreground mt-2 max-w-xs mx-auto">
        Your email and password have been set. One more step and we'll build your personalized financial blueprint.
      </p>
    </div>
  );
}

function FrameAbout({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const options = [
    { id: "rent", label: "I currently rent", icon: Building },
    { id: "own_home", label: "I own a home", icon: Home },
    { id: "student_loans", label: "I have student loans", icon: GraduationCap },
    { id: "credit_card_debt", label: "I have credit card debt", icon: CreditCard },
    { id: "retirement_account", label: "I have 401(k) or EPF/PPF", icon: PiggyBank },
    { id: "trading_india", label: "Active trading account (India)", icon: TrendingUp },
    { id: "trading_us", label: "Active trading account (US)", icon: TrendingUp },
    { id: "other_investments", label: "Other investments (Gold, Crypto, RE)", icon: Sparkles },
    { id: "car_loan", label: "I have a car loan", icon: Car },
    { id: "side_income", label: "I have side income", icon: Briefcase },
  ];

  const toggle = (id: string) => {
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  };

  return (
    <div>
      <h2 className="text-xl font-bold">One last thing — tell us about yourself</h2>
      <p className="text-sm text-muted-foreground mt-1.5">
        Select all that apply. This helps us prepare a personalized profile for you.
      </p>

      <div className="grid grid-cols-2 gap-2 mt-6 max-h-[320px] overflow-y-auto">
        {options.map((opt) => {
          const Icon = opt.icon;
          const selected = value.includes(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => toggle(opt.id)}
              className={`flex items-center gap-2 p-3 rounded-xl border text-left transition-all duration-200 ${
                selected
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/30 hover:bg-secondary/30"
              }`}
            >
              <Icon className={`h-3.5 w-3.5 shrink-0 ${selected ? "text-primary" : "text-muted-foreground"}`} />
              <span className={`text-[11px] font-medium leading-tight ${selected ? "text-primary" : ""}`}>{opt.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
