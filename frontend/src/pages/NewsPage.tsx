import { NewsFeed } from "@/components/news/NewsFeed";
import { PortfolioBriefing } from "@/components/news/PortfolioBriefing";

export function NewsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Market News</h2>
      <PortfolioBriefing />
      <NewsFeed />
    </div>
  );
}
