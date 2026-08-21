import { useState, useEffect } from "react";
import { Compass, ArrowRight, X, Sparkles } from "lucide-react";

interface TourStep {
  title: string;
  description: string;
  target?: string; // CSS selector to highlight (optional)
  position: "center" | "left" | "right";
}

const TOUR_STEPS: TourStep[] = [
  {
    title: "Welcome to RuDo",
    description: "Your cross-border financial dashboard. Track wealth in Rupees and Dollars from one place. Let us show you around.",
    position: "center",
  },
  {
    title: "📐 Blueprint — Your Financial Goals",
    description: "Set targets like Retirement, Emergency Fund, or a Dream Home. Track progress as your wealth grows across stocks, ETFs, and savings.",
    position: "center",
  },
  {
    title: "📊 The Market — Your Portfolio",
    description: "Connect your broker (Groww, Robinhood) and see all holdings in one place. Live prices, sector allocation, and daily P&L.",
    position: "center",
  },
  {
    title: "💰 Earnings — Passive Income",
    description: "Track dividends, yield analysis, and income projections. Upload trade history from Telegram for accurate calculations.",
    position: "center",
  },
  {
    title: "🪙 ETFs — Track Your Funds",
    description: "Add ETFs from India or US markets. Compare performance, see historical growth, and simulate 'what-if' scenarios.",
    position: "center",
  },
  {
    title: "🤖 AI Copilot — Smart Insights",
    description: "Daily AI-powered market briefings, prediction tracking, and news analysis. Your personal financial analyst.",
    position: "center",
  },
  {
    title: "🔔 Alerts — Never Miss a Move",
    description: "Set price alerts for any stock. Get notified via Telegram when targets are hit.",
    position: "center",
  },
  {
    title: "🔗 Brokers — Connect Your Account",
    description: "Start by connecting your broker. Go to Brokers page, paste your access token, and your portfolio syncs automatically.",
    position: "center",
  },
  {
    title: "You're all set! 🚀",
    description: "Start by creating a goal in Blueprint, or connect your broker to see your portfolio. You can always access Settings to manage your account.",
    position: "center",
  },
];

const STORAGE_KEY = "rudo_tour_completed";

export function ProductTour() {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const completed = localStorage.getItem(STORAGE_KEY);
    if (!completed) {
      // Small delay so page renders first
      setTimeout(() => setVisible(true), 800);
    }
  }, []);

  if (!visible) return null;

  const currentStep = TOUR_STEPS[step];
  const isFirst = step === 0;
  const isLast = step === TOUR_STEPS.length - 1;
  const progress = ((step + 1) / TOUR_STEPS.length) * 100;

  const handleNext = () => {
    if (isLast) {
      handleDismiss();
    } else {
      setStep(step + 1);
    }
  };

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEY, "true");
    setVisible(false);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center animate-fade-in">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleDismiss} />

      {/* Tour card */}
      <div className="relative w-full max-w-md mx-4 rounded-3xl bg-card border shadow-2xl shadow-primary/10 overflow-hidden animate-scale-in">
        {/* Progress bar */}
        <div className="h-1 bg-muted">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Content */}
        <div className="p-8">
          {/* Close button */}
          <button
            onClick={handleDismiss}
            className="absolute top-4 right-4 btn-icon h-8 w-8"
            aria-label="Skip tour"
          >
            <X className="h-4 w-4" />
          </button>

          {/* Icon for first/last step */}
          {(isFirst || isLast) && (
            <div className="flex justify-center mb-5">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                {isFirst ? (
                  <Compass className="h-8 w-8 text-white" />
                ) : (
                  <Sparkles className="h-8 w-8 text-white" />
                )}
              </div>
            </div>
          )}

          <h2 className="text-lg font-bold text-center">{currentStep.title}</h2>
          <p className="text-sm text-muted-foreground text-center mt-3 leading-relaxed">
            {currentStep.description}
          </p>

          {/* Step indicator */}
          <div className="flex justify-center gap-1.5 mt-6">
            {TOUR_STEPS.map((_, i) => (
              <div
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  i === step ? "w-6 bg-primary" : i < step ? "w-1.5 bg-primary/40" : "w-1.5 bg-muted"
                }`}
              />
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between mt-6">
            <button
              onClick={handleDismiss}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Skip tour
            </button>
            <button onClick={handleNext} className="btn-primary text-xs">
              {isLast ? "Get Started" : "Next"}
              {!isLast && <ArrowRight className="h-3.5 w-3.5 ml-1.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
