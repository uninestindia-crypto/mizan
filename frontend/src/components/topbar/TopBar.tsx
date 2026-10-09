import { useRef } from "react";
import { CopilotButton } from "../copilot/CopilotButton";
import { SecondOpinionReady } from "../copilot/SecondOpinionReady";
import { ModeSwitch } from "../mode/ModeSwitch";
import { ScreenTitle } from "./ScreenTitle";
import { SearchField } from "./SearchField";
import { StatusArea } from "./StatusArea";
import { useBarLayout } from "./useBarLayout";

// The bar measures itself (a container). The mode switch, the Copilot button and the search field each decide from the
// bar's own width how much to say; the chips are one row of words on a wide bar, one "Status" button on a narrow one.
const BAR =
  "@container relative z-20 hidden h-14 shrink-0 items-center gap-3 border-b border-line bg-surface/90 px-4 lg:px-6 " +
  "backdrop-blur-[6px] md:flex";

/** The strip across the top of every screen: where you are, search, the mode, what QuantOS knows, and the Copilot. */
export function TopBar({ onSearch }: { onSearch: () => void }) {
  const bar = useRef<HTMLElement>(null);
  const layout = useBarLayout(bar);
  return (
    <header ref={bar} className={BAR}>
      <ScreenTitle />
      <SearchField onSearch={onSearch} />
      <ModeSwitch />
      <StatusArea layout={layout} />
      <SecondOpinionReady />
      <CopilotButton />
    </header>
  );
}
