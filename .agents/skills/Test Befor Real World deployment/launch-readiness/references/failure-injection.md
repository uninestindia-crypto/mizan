# Failure Injection Recipes

The exact mechanics for G7. Every recipe assumes a non-production environment you own.

**The universal method:** break one thing, observe four answers, restore, record.

| # | Question | Where you look |
|---|---|---|
| 1 | What does the **user** see? | The screen or the API response |
| 2 | What does the **operator** see? | Logs, metrics, alerts |
| 3 | Is the **data** safe? | Query for half-written state afterwards |
| 4 | Does it **recover by itself**? | Restore the dependency; wait; do not restart anything |

If any answer is "I don't know", the dependency is untested.

---

## Killing a dependency completely

```bash
# Docker Compose — the cleanest method
docker compose stop db
docker compose stop redis
docker compose start db          # restore

# Point a third-party base URL at a dead port
export STRIPE_API_BASE=http://127.0.0.1:1
export SENDGRID_API_BASE=http://127.0.0.1:1

# Block a hostname at the DNS level (inside the container)
echo "0.0.0.0 api.stripe.com" >> /etc/hosts

# Block by port with a firewall rule
sudo iptables -A OUTPUT -p tcp --dport 5432 -j DROP
sudo iptables -D OUTPUT -p tcp --dport 5432 -j DROP   # restore

# Revoke the credential instead of the network — a different and realistic failure
export DATABASE_URL="postgres://wrong:wrong@localhost:5432/app"
```

```bash
LRK run G7.01 --title "postgres stopped: login, list, checkout" -- bash -c '
  docker compose stop db
  echo "--- login ---";    curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/api/login" -d "$CREDS"
  echo "--- list ---";     curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/orders"
  echo "--- health ---";   curl -s "$BASE/health"; echo
  echo "--- ready ---";    curl -s "$BASE/ready"; echo
  docker compose start db
  sleep 10
  echo "--- after recovery ---"; curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/orders"'
```

**What you are looking for:** does `/ready` go red? (It must.) Does the app recover without a
restart? (It must.) Is the error shown to the user honest, or a white screen?

---

## Making a dependency slow — more dangerous than killing it

Dead fails fast. **Slow exhausts your resources**, and that is how one dependency takes down a whole
service.

```bash
# Inside a Linux container: add 5 seconds of latency to everything
tc qdisc add dev eth0 root netem delay 5000ms
tc qdisc del dev eth0 root                      # restore

# Add latency plus 10% packet loss
tc qdisc add dev eth0 root netem delay 2000ms loss 10%
```

**Toxiproxy** is the purpose-built tool and is worth the five minutes to set up:

```bash
docker run -d --name toxiproxy -p 8474:8474 -p 15432:15432 ghcr.io/shopify/toxiproxy
curl -X POST http://localhost:8474/proxies -d '{"name":"pg","listen":"0.0.0.0:15432","upstream":"db:5432"}'
# then point your app at port 15432 and inject:
curl -X POST http://localhost:8474/proxies/pg/toxics -d '{"type":"latency","attributes":{"latency":5000,"jitter":1000}}'
curl -X POST http://localhost:8474/proxies/pg/toxics -d '{"type":"bandwidth","attributes":{"rate":10}}'
curl -X POST http://localhost:8474/proxies/pg/toxics -d '{"type":"timeout","attributes":{"timeout":0}}'
```

**A ten-line sleep server** works for any HTTP dependency and needs nothing installed:

```python
# slow_stub.py -- python slow_stub.py 8099 30
import sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
DELAY = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
class H(BaseHTTPRequestHandler):
    def do_GET(self):  self._slow()
    def do_POST(self): self._slow()
    def _slow(self):
        time.sleep(DELAY)
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}')
    def log_message(self, *a): pass
HTTPServer(("", int(sys.argv[1])), H).serve_forever()
```

**What you are looking for:** does the request time out at the layer you configured (G6.15), or does
it hang until the client gives up? Do **other** endpoints — ones that never touch this dependency —
also become slow? That is pool exhaustion, and it is the mechanism behind most total outages.

---

## Making a dependency return garbage

```python
# bad_stub.py -- python bad_stub.py 8099 <mode>
# modes: 500 503 429 429-noretry 401 malformed empty html slow-then-500 wrong-shape
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
MODE = sys.argv[2] if len(sys.argv) > 2 else "500"
BODIES = {
    "500":        (500, b'{"error":"internal"}', "application/json"),
    "503":        (503, b'Service Unavailable', "text/plain"),
    "429":        (429, b'{"error":"rate limited"}', "application/json"),
    "429-noretry":(429, b'', "application/json"),
    "401":        (401, b'{"error":"expired credentials"}', "application/json"),
    "malformed":  (200, b'{"id": 1, "name": "unterminated', "application/json"),
    "empty":      (200, b'', "application/json"),
    "html":       (200, b'<html><body><h1>502 Bad Gateway</h1></body></html>', "text/html"),
    "wrong-shape":(200, b'{"data":{"items":null},"total":"not-a-number"}', "application/json"),
}
class H(BaseHTTPRequestHandler):
    def do_GET(self):  self._r()
    def do_POST(self): self._r()
    def _r(self):
        code, body, ct = BODIES[MODE]
        self.send_response(code)
        self.send_header("Content-Type", ct)
        if MODE == "429": self.send_header("Retry-After", "30")
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
HTTPServer(("", int(sys.argv[1])), H).serve_forever()
```

Run through every mode, one record each:

```bash
for mode in 500 503 429 429-noretry 401 malformed empty html wrong-shape; do
  python bad_stub.py 8099 "$mode" & STUB=$!
  LRK run G7.03 --title "payment API returns: $mode" -- bash -c '<probe the critical path>'
  kill $STUB
done
```

**The three that break real systems:**
- **`html`** — a `200 OK` with an HTML error page. Cloud edges return this during incidents. `JSON.parse("<html>")` throws somewhere nobody wrote a handler.
- **`429-noretry`** — rate-limited with no `Retry-After`. Naive clients retry immediately and make it worse.
- **`wrong-shape`** — valid JSON, wrong contents. `items` is `null` instead of `[]`, so `.map()` throws three functions deeper.

---

## Killing the process mid-write

```bash
LRK run G7.06 --title "SIGKILL during a multi-table write" -- bash -c '
  curl -s -X POST "$BASE/api/orders" -d "$BIG_ORDER" &
  sleep 0.4
  docker compose kill -s SIGKILL app     # SIGKILL, not SIGTERM — no cleanup at all
  docker compose start app
  sleep 8
  echo "--- orphaned order rows ---"
  psql "$DATABASE_URL" -c "SELECT id, status FROM orders WHERE status NOT IN (\"complete\",\"failed\",\"cancelled\");"
  echo "--- jobs stuck in processing ---"
  psql "$DATABASE_URL" -c "SELECT id, state, updated_at FROM jobs WHERE state=\"processing\" AND updated_at < now() - interval \"5 minutes\";"'
```

**Looking for:** a row in a limbo state that no code path will ever move out of. A job marked
`processing` before the crash and never reclaimed sits there forever while a user waits for
something that will never happen.

---

## Graceful shutdown

```bash
LRK run G7.11 --title "SIGTERM with 20 requests in flight" -- bash -c '
  for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code} " "$BASE/api/slow-endpoint" & done
  sleep 0.5
  docker compose stop app        # sends SIGTERM, then SIGKILL after the grace period
  wait
  echo'
```

**Pass:** every one of the twenty returns 200. **Fail:** any connection reset or 502.

Also confirm the ordering — readiness must go red *before* the process stops accepting work, or the
load balancer keeps routing traffic into a dying instance.

---

## Queue failures

```bash
# Double delivery
LRK run G7.10 --title "same message delivered twice" -- bash -c '
  MSG="{\"id\":\"dedupe-test-1\",\"orderId\":42}"
  <publish "$MSG">; <publish "$MSG">; sleep 5
  psql "$DATABASE_URL" -c "SELECT count(*) FROM order_events WHERE order_id=42;"'
# expect: 1

# Poison message
LRK run G7.10 --title "poison message quarantines" -- bash -c '
  <publish a message that always throws>; sleep 30
  <check the dead-letter queue depth>; <check that later messages still processed>'

# Backlog drain rate
LRK run G7.10 --title "100k backlog drain rate" --timeout 3600 -- bash -c '
  <stop the consumer>
  for i in $(seq 1 100000); do <publish>; done
  <start the consumer>
  START=$(date +%s)
  while [ "$(<queue depth>)" -gt 0 ]; do sleep 10; echo "depth: $(<queue depth>) rss: $(ps -o rss= -p <PID>)"; done
  echo "drained in $(( $(date +%s) - START ))s"'
```

**Looking for:** memory climbing during the drain (the consumer is fetching everything into RAM),
and a drain rate slower than the arrival rate — which means the backlog can never clear.

---

## Disk full and out of memory

```bash
# Fill the disk
LRK run G7.07 --title "disk full" -- bash -c '
  fallocate -l 20G /tmp/filler || dd if=/dev/zero of=/tmp/filler bs=1M count=20000
  <exercise the app: write a file, log, run a migration>
  rm /tmp/filler'

# Constrain memory
docker run -m 256m --memory-swap 256m app:rc
LRK run G7.07 --title "OOM under 256MB" -- bash -c '<generate load until the OOM killer fires>'
```

**Looking for:** silently truncated writes, a corrupted upload, log rotation failing (which then
fills the disk faster), and whether the OOM kill leaves data consistent.

---

## Clock skew

```bash
LRK run G7.14 --title "clock +10 minutes" -- bash -c '
  docker compose exec app date -s "+10 minutes"
  echo "--- JWT still valid? ---";     curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" "$BASE/api/me"
  echo "--- webhook signature? ---";   <send a signed webhook>
  echo "--- TOTP? ---";                <verify a TOTP code>
  docker compose exec app ntpdate -s time.nist.gov || docker compose restart app'
```

**Looking for:** a skew tolerance that is either absent (everything breaks on a 30-second drift) or
unbounded (a replayed webhook from last week is accepted). Both are bugs.

---

## Chaos: everything at once, briefly

Only after every single-dependency test passes. Combined failures reveal interaction bugs that
individual ones cannot.

```bash
LRK run G7.15 --title "full outage and recovery, timed" -- bash -c '
  time (
    docker compose down
    sleep 30
    docker compose up -d
    until curl -sf "$BASE/health" > /dev/null; do sleep 2; done
  )
  <run the smoke suite>
  <query for inconsistent state>'
```

---

## The result table you must be able to fill in

G7 is passed when this table has no blank cells:

| Dependency | User sees | Operator sees | Data safe? | Self-heals? | Recovery time |
|---|---|---|---|---|---|
| Postgres down | "Temporarily unavailable", 503 | `/ready` red, alert in 40s | Yes, no partial writes | Yes, 12s after DB returns | 12s |
| Redis down | Slower, fully functional | WARN logged, no alert | Yes | Yes, immediate | 0s |
| Payment API down | "Payment unavailable, cart saved" | ERROR, alert in 30s | Yes, order stays `pending` | Yes | 5s |
| Payment API slow (5s) | Spinner then clear error at 10s | Timeout logged, breaker opens | Yes | Yes, breaker closes in 60s | 60s |
| Email provider down | Signup succeeds, mail queued | WARN, queue depth alert | Yes, retried | Yes | drains in ~2 min |
| Process SIGKILL | Request fails | Restart logged | Yes, transaction rolled back | Yes | 8s |
| Queue broker down | Actions accepted, delayed | ERROR, alert in 60s | Yes, buffered | Yes | drains in ~4 min |

**Any blank cell is an untested failure mode**, which is to say: an outage that has not happened
yet, whose behaviour you will be discovering live, at speed, in front of users.
