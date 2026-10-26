import type { MarketRow, Snapshot } from "@/types/database";
import { date, isStale, price } from "@/lib/utils";

export function marketQuoteSummary(market: MarketRow): string {
  if (market.market_type !== "daily_max_temperature") {
    return "This market is outside the daily high temperature category this version monitors.";
  }
  const yes = market.market_tokens.find((token) => token.outcome === "YES")
    ?.market_snapshots[0];
  const no = market.market_tokens.find((token) => token.outcome === "NO")
    ?.market_snapshots[0];
  if (yes?.best_ask == null && no?.best_ask == null) {
    return "No buy offer was captured for either outcome.";
  }
  const offers = [
    yes?.best_ask == null ? null : `YES ${price(yes.best_ask)}`,
    no?.best_ask == null ? null : `NO ${price(no.best_ask)}`,
  ].filter(Boolean);
  const quotedBooks = [yes, no].filter(
    (book): book is Snapshot => book?.best_ask != null,
  );
  return `Last saved prices to buy: ${offers.join(" · ")} per share.${quotedBooks.some((book) => isStale(book.captured_at)) ? " These prices may have changed." : ""}`;
}

export function detailExplanation(
  marketType: string,
  resolutionStatus: string,
  yes: Snapshot | undefined,
  no: Snapshot | undefined,
  timeZone: string,
): string[] {
  const sentences: string[] = [];
  if (marketType !== "daily_max_temperature") {
    sentences.push(
      "This market is outside the daily high temperature category this version monitors. Its weather rule needs review.",
    );
  } else if (yes?.best_ask == null && no?.best_ask == null) {
    sentences.push(
      "We found this market, but we have not captured a price to buy YES or NO.",
    );
  } else {
    const offers = [
      yes?.best_ask == null ? null : `YES at ${price(yes.best_ask)}`,
      no?.best_ask == null ? null : `NO at ${price(no.best_ask)}`,
    ].filter(Boolean);
    sentences.push(
      `The latest saved prices to buy were ${offers.join(" and ")} per share.`,
    );
    sentences.push(
      "A share is designed to pay $1 if its outcome wins, before fees. These are market prices, not an independent weather forecast.",
    );
  }
  if (resolutionStatus === "needs_review") {
    sentences.push(
      "We have not independently verified the exact rule used to settle this market.",
    );
  }
  const capturedAt = [yes?.captured_at, no?.captured_at]
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(0);
  if (capturedAt && isStale(capturedAt)) {
    sentences.push(
      `At least one saved order book is from ${date(capturedAt, timeZone)}. Prices may have changed since then.`,
    );
  }
  return sentences;
}
