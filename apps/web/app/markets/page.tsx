import { MarketsTable } from "@/components/markets-table";
import { Card } from "@/components/ui/card";
import { getMarkets } from "@/lib/data";
export const dynamic = "force-dynamic";
export default async function Markets() {
  const markets = await getMarkets();
  const supported = markets.filter(
    (market) => market.market_type === "daily_max_temperature",
  ).length;
  const withOffer = markets.filter((market) =>
    market.market_tokens.some(
      (token) => token.market_snapshots[0]?.best_ask != null,
    ),
  ).length;
  return (
    <div className="space-y-5">
      <div>
        <p className="panel-title mb-2">Discovery universe</p>
        <h1 className="page-title">Weather markets</h1>
        <p className="muted mt-2 text-sm">
          Public contracts and executable top-of-book quotes from the latest
          stored snapshots.
        </p>
      </div>
      <Card className="p-5">
        <h2 className="panel-title mb-3">In plain English</h2>
        <p className="max-w-4xl text-sm leading-6">
          This list shows {markets.length} weather markets from your local
          scans. {supported} are daily high temperature markets we can monitor,
          and {withOffer} have at least one saved price to buy a share.
        </p>
        <p className="muted mt-2 max-w-4xl text-sm leading-6">
          A YES share is designed to pay $1 if the event happens; a NO share
          pays $1 if it does not, before fees. The prices below come from the
          market, not our weather forecast. We cannot yet say whether any price
          is a good deal.
        </p>
        <p className="muted mt-2 max-w-4xl text-sm leading-6">
          “Ask” means the lowest listed price to buy a share. The spread is the
          gap between what a buyer offers for YES and what a seller asks. The
          liquidity shown is the number of YES and NO shares listed for sale in
          the saved books.
        </p>
      </Card>
      <Card className="overflow-hidden">
        <MarketsTable markets={markets} />
      </Card>
    </div>
  );
}
