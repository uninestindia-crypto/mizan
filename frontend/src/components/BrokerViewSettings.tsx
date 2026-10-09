import { Check, Copy, ExternalLink, Eye, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { errorMessage } from "../lib/api";
import { dateTime } from "../lib/format";
import {
  useBrokerAssistantAccess,
  useBrokerCancel,
  useBrokerConnect,
  useBrokerDisconnect,
  useBrokerRefresh,
  useBrokerSnapshot,
  useBrokerStatus,
} from "../lib/queries";
import { Badge, Button, Callout, Card, CardHeader, Skeleton, Switch } from "./ui";

const UPSTOX_APPS = "https://service.upstox.com/developer/apps";

/**
 * Settings, Broker view: look at the account at Upstox without being able to touch it.
 *
 * Nothing on this screen can buy, sell, move money or change anything at the broker, and the screen never asks for a
 * password or a trading PIN: signing in happens on Upstox's own page.
 */
export function BrokerViewSettings() {
  const status = useBrokerStatus();
  const connect = useBrokerConnect();
  const cancel = useBrokerCancel();
  const refresh = useBrokerRefresh();
  const disconnect = useBrokerDisconnect();
  const access = useBrokerAssistantAccess();
  const snapshot = useBrokerSnapshot();
  const [copied, setCopied] = useState(false);

  // The first figures are fetched just after the sign-in completes, so read them again a moment after it does.
  const signedIn = status.data?.brokers.some((b) => b.connected) ?? false;
  const { refetch: readFigures } = snapshot;
  useEffect(() => {
    if (!signedIn) return;
    const timer = window.setTimeout(() => void readFigures(), 2_000);
    return () => window.clearTimeout(timer);
  }, [signedIn, readFigures]);

  if (status.isPending) return <Skeleton className="h-64" />;
  if (status.isError) {
    return (
      <Callout tone="danger" title="The broker view could not load">
        {errorMessage(status.error)}
      </Callout>
    );
  }

  const data = status.data;
  const upstox = data.brokers.find((b) => b.id === "upstox");

  const copyAddress = async (address: string) => {
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2_000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <>
      <Callout tone="info" title="View only">
        QuantOS can show what is in your broker account: your holdings, open positions and cash. It can only look. It cannot buy, sell, move money or change anything, and it never asks for your trading PIN or password.
      </Callout>

      {!data.available || !upstox ? (
        <Callout tone="warn" title="Not available on this computer">
          The broker view is not available on this computer, because Windows Credential Manager is not available to keep your sign-in safe.
        </Callout>
      ) : (
        <Card>
          <CardHeader
            title="Upstox"
            subtitle="Free. You sign in on Upstox's own page once a day, and QuantOS never sees your password."
            action={
              upstox.connected ? (
                <Badge tone="up">Connected</Badge>
              ) : upstox.waiting_for_sign_in ? (
                <Badge tone="brand">Waiting for you to sign in</Badge>
              ) : (
                <Badge>Not connected</Badge>
              )
            }
          />

          {upstox.message && (
            <Callout tone="warn" className="mb-4">
              {upstox.message}
            </Callout>
          )}
          {connect.isError && (
            <Callout tone="warn" className="mb-4">
              {errorMessage(connect.error)}
            </Callout>
          )}

          {upstox.connected ? (
            <div className="space-y-4">
              <p className="text-sm text-ink-2">
                Connected to Upstox.
                {snapshot.data?.fetched_at ? ` Updated ${dateTime(snapshot.data.fetched_at)}.` : ""}{" "}
                {upstox.key_ends_at
                  ? `Upstox ends this sign-in at ${dateTime(upstox.key_ends_at)}. After that, click Connect Upstox again (about 20 seconds).`
                  : "Upstox ends this sign-in at 3:30 am. After that, click Connect Upstox again (about 20 seconds)."}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  icon={<RefreshCw className="size-4" aria-hidden />}
                  loading={refresh.isPending}
                  onClick={() => refresh.mutate()}
                >
                  Refresh now
                </Button>
                <Button variant="ghost" loading={disconnect.isPending} onClick={() => disconnect.mutate()}>
                  Disconnect
                </Button>
                <Link to="/portfolio" className="text-sm font-medium text-brand hover:underline">
                  See it on Portfolio
                </Link>
              </div>
            </div>
          ) : upstox.waiting_for_sign_in ? (
            <div className="space-y-4">
              <p className="text-sm text-ink-2">
                Sign in on the Upstox page that just opened in your browser. QuantOS never sees your password.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="secondary" loading={cancel.isPending} onClick={() => cancel.mutate()}>
                  Cancel
                </Button>
                {connect.data?.login_address && (
                  <a
                    href={connect.data.login_address}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
                  >
                    If no page opened, click here <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {!upstox.set_up && (
                <ol className="list-decimal space-y-3 pl-5 text-sm text-ink-2">
                  <li>
                    <a
                      href={UPSTOX_APPS}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-brand hover:underline"
                    >
                      Open your Upstox app page <ExternalLink className="size-3.5" aria-hidden />
                    </a>
                  </li>
                  <li>
                    <p>
                      Create an app, or open the one you have. Set "Redirect URL" to exactly this address, and leave "Static IP" empty. Upstox asks for one before it accepts orders, so an app without it is not set up for trading.
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <code className="rounded-md border border-line bg-surface-2 px-2 py-1 text-[13px] text-ink">{upstox.callback_address}</code>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
                        onClick={() => void copyAddress(upstox.callback_address)}
                      >
                        {copied ? "Copied" : "Copy"}
                      </Button>
                    </div>
                  </li>
                  <li>
                    Copy your app's key and secret from that page into the two matching boxes in{" "}
                    <Link to="/settings/accounts" className="font-medium text-brand hover:underline">
                      Settings, then Accounts and keys
                    </Link>
                    .
                  </li>
                </ol>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  icon={<Eye className="size-4" aria-hidden />}
                  disabled={!upstox.set_up}
                  loading={connect.isPending}
                  onClick={() => connect.mutate()}
                >
                  Connect Upstox
                </Button>
                {!upstox.set_up && <span className="text-[13px] text-ink-3">Save your Upstox app key and secret first.</span>}
              </div>
            </div>
          )}
        </Card>
      )}

      <Card>
        <CardHeader
          title="The assistant"
          subtitle="Off until you turn it on. You can turn it off again at any time."
        />
        <div className="space-y-3">
          <Switch
            checked={data.assistant_access}
            onChange={(allowed) => access.mutate(allowed)}
            label="Let the assistant read my broker account"
          />
          <p className="text-[13px] text-ink-3">
            When you ask the assistant something and it uses an AI service, a summary of your holdings (names, quantities, values and cash) is sent to that AI company with your question. Your key and your account details are never sent. Without an AI key, the assistant answers from QuantOS itself and nothing is sent anywhere.
          </p>
          {access.isError && <p className="text-[13px] text-down">{errorMessage(access.error)}</p>}
        </div>
      </Card>
    </>
  );
}
