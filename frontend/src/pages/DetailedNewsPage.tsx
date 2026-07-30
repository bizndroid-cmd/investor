import { NewsFeed } from "@/components/news/NewsFeed";

export function DetailedNewsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Detailed News</h2>
      <NewsFeed />
    </div>
  );
}
