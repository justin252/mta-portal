"""Retry and reboot policy for the train fetch. Pure: callers pass the time in.

Ladder: retry with backoff (app.py also rejoins WiFi when the link is down), then
reboot once nothing has worked for REBOOT_AFTER seconds. A reboot is the only reset
that reliably clears ESP32 and socket state, and the board is back in ~15s.
"""

BACKOFF = (5, 15, 30)  # seconds before each retry; most blips are one stale socket
REBOOT_AFTER = 180      # seconds without good data, with at least 3 failures in a row


class Recovery:
    def __init__(self, interval, backoff=BACKOFF, reboot_after=REBOOT_AFTER, now=0):
        self.interval = interval
        self.backoff = backoff
        self.reboot_after = reboot_after
        self.failures = 0
        self.last_ok = now  # boot counts as fresh, so a dead network still reboots on time
        self.next_at = now  # fetch right away

    def due(self, now):
        return now >= self.next_at

    def succeeded(self, now):
        self.failures = 0
        self.last_ok = now
        self.next_at = now + self.interval

    def failed(self, now):
        self.failures += 1
        self.next_at = now + self.backoff[min(self.failures, len(self.backoff)) - 1]

    def should_reboot(self, now):
        return self.failures >= 3 and now - self.last_ok >= self.reboot_after

    def age(self, now):
        """Seconds since the last good data (or boot)."""
        return now - self.last_ok


def attempt(fetch, policy, clock):
    """Run fetch() under the policy. Returns (result, None) or (None, error); never raises.

    Catches Exception, not a list of types: the network stack raises plain-Exception
    subclasses (HttpError, OutOfRetries) that a type list misses, halting the board.
    KeyboardInterrupt is a BaseException, so Ctrl-C still reaches the REPL.
    """
    try:
        result = fetch()
    except Exception as e:
        policy.failed(clock())
        return None, e
    policy.succeeded(clock())
    return result, None
