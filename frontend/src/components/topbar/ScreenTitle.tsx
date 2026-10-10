import { Link, useLocation } from "react-router";
import { screenName } from "./screenName";

/** The name of the screen, big, with the screen it sits inside (if any) small above it as a way back. */
export function ScreenTitle() {
  const { pathname } = useLocation();
  const { title, parent } = screenName(pathname);
  return (
    <div className="min-w-0 flex-1 leading-tight">
      {parent && (
        <Link
          to={parent.to}
          aria-label={`Back to ${parent.label}`}
          className="block truncate text-[11.5px] font-medium text-ink-3 hover:text-ink"
        >
          {parent.label}
        </Link>
      )}
      <p title={title} data-screen-name="" className="truncate text-[16px] font-semibold tracking-tight text-ink">
        {title}
      </p>
    </div>
  );
}
