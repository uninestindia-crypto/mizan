import type { ShariahBasket } from "../../lib/types";
import { Card, CardHeader } from "../ui";
import { BasketPerformance } from "./BasketPerformance";
import { BasketStocks } from "./BasketStocks";
import { OrderSheetNote } from "./OrderSheetNote";

function BasketCard({ basket }: { basket: ShariahBasket }) {
  return (
    <Card className="flex flex-col justify-between">
      <div>
        <CardHeader title={basket.name} subtitle={basket.category} />
        <p className="text-[13.5px] leading-relaxed text-ink-2">{basket.thesis}</p>
        <BasketPerformance basket={basket} />
        <BasketStocks stocks={basket.constituents ?? []} basketName={basket.name} />
      </div>
      <OrderSheetNote />
    </Card>
  );
}

export function BasketsTab({ baskets }: { baskets: ShariahBasket[] }) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {baskets.map((basket) => (
        <BasketCard key={basket.id} basket={basket} />
      ))}
    </div>
  );
}
