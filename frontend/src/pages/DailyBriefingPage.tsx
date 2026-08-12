import { useState } from "react";
import { FileText, Brain, Lightbulb, Newspaper } from "lucide-react";
import { BriefingPage } from "./BriefingPage";
import { PredictionsPage } from "./PredictionsPage";
import { InsightsPage } from "./InsightsPage";
import { DetailedNewsPage } from "./DetailedNewsPage";

type Tab = "briefing" | "predictions" | "insights" | "news";

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: "briefing", label: "News", icon: FileText },
  { id: "predictions", label: "AI Predictions", icon: Brain },
  { id: "insights", label: "Insights", icon: Lightbulb },
  { id: "news", label: "News Feed", icon: Newspaper },
];

export function DailyBriefingPage() {
  const [activeTab, setActiveTab] = useState<Tab>("briefing");

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border pb-0">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-t-lg transition-colors border-b-2 ${
                isActive
                  ? "border-primary text-primary bg-primary/5"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary/30"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "briefing" && <BriefingPage />}
        {activeTab === "predictions" && <PredictionsPage />}
        {activeTab === "insights" && <InsightsPage />}
        {activeTab === "news" && <DetailedNewsPage />}
      </div>
    </div>
  );
}
