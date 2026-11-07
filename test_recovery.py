"""Desktop proof of the network guard: app.py runs every fetch through recovery.attempt()."""
import pytest

from recovery import Recovery, attempt

# Exceptions the board's network stack is known to raise (CircuitPython 10 frozen libraries).
# HttpError and OutOfRetries subclass plain Exception, which the old code didn't catch: the
# board halted at "Code done running" until someone pressed reset.


class HttpError(Exception):  # adafruit_portalbase.network.HttpError
    pass


class OutOfRetries(Exception):  # adafruit_requests.OutOfRetries
    pass


NETWORK_ERRORS = [
    HttpError('Code 503: Service Unavailable'),
    OutOfRetries('Repeated socket failures'),
    TimeoutError('ESP32 not responding'),
    ConnectionError('Failed to connect to ssid'),
    BrokenPipeError('Expected 01 but got 00'),
    OSError(23, 'Only one open SSL connection allowed'),
    RuntimeError('Sending request failed'),
    MemoryError('memory allocation failed, allocating 4097 bytes'),
    ValueError('no UTC offset'),
    KeyError('data'),
    IndexError('list index out of range'),
    TypeError("'NoneType' object is not subscriptable"),
]


class Clock:
    def __init__(self, t=0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.mark.parametrize('error', NETWORK_ERRORS, ids=lambda e: type(e).__name__)
def test_any_failure_is_counted_never_raised(error):
    policy = Recovery(30, now=0)

    def fetch():
        raise error

    result, err = attempt(fetch, policy, Clock(0))
    assert result is None and err is error
    assert policy.failures == 1 and not policy.due(0)


def test_ctrl_c_still_reaches_the_repl():
    def fetch():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        attempt(fetch, Recovery(30, now=0), Clock(0))


def test_success_returns_result_and_resets():
    policy = Recovery(30, now=0)
    policy.failed(0)
    result, err = attempt(lambda: 'arrivals', policy, Clock(5))
    assert (result, err) == ('arrivals', None)
    assert policy.failures == 0 and policy.next_at == 35 and policy.age(40) == 35


def test_fetches_immediately_at_boot():
    assert Recovery(30, now=100).due(100)


def test_backoff_grows_then_caps():
    policy = Recovery(30, backoff=(5, 15, 30), now=0)
    waits = []
    for _ in range(5):
        policy.failed(0)
        waits.append(policy.next_at)
    assert waits == [5, 15, 30, 30, 30]


def simulate(outcomes, *, step_cost=1, policy=None):
    """Drive the policy like app.py does. outcomes(t) -> True for a successful fetch.
    Returns the time the policy first asked for a reboot, or None within 30 minutes."""
    policy = policy or Recovery(30, now=0)
    t = 0
    while t < 1800:
        if policy.due(t):
            t += step_cost  # a fetch attempt takes time
            if outcomes(t):
                policy.succeeded(t)
            else:
                policy.failed(t)
                if policy.should_reboot(t):
                    return t
        t += 1
    return None


@pytest.mark.parametrize('name,outcomes,reboot_window', [
    ('healthy', lambda t: True, None),
    ('one blip', lambda t: not 100 <= t < 102, None),
    ('2 minute outage', lambda t: not 100 <= t < 220, None),
    ('outage from boot', lambda t: False, (180, 215)),
    ('outage after 10 minutes up', lambda t: t < 600, (780, 815)),
    ('flapping every other fetch', lambda t: (t // 30) % 2 == 0, None),
])
def test_scenarios(name, outcomes, reboot_window):
    rebooted_at = simulate(outcomes)
    if reboot_window is None:
        assert rebooted_at is None, '%s: should ride it out, rebooted at %s' % (name, rebooted_at)
    else:
        lo, hi = reboot_window
        assert rebooted_at is not None and lo <= rebooted_at <= hi, \
            '%s: expected reboot in [%d, %d], got %s' % (name, lo, hi, rebooted_at)


def test_slow_failures_still_reboot_on_time():
    # Each failing attempt burns 13s (timeouts); the reboot decision uses wall time, not counts
    rebooted_at = simulate(lambda t: False, step_cost=13)
    assert rebooted_at is not None and 180 <= rebooted_at <= 240


def test_needs_three_failures_even_after_long_quiet():
    # e.g. the loop was busy for 5 minutes with the train art shown: one failure is not an outage
    policy = Recovery(30, now=0)
    policy.failed(300)
    assert not policy.should_reboot(300)
