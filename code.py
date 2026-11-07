"""Bootstrap: run the sign (app.py) and never stay halted.

An uncaught exception normally leaves CircuitPython stopped at "Code done running"
until someone presses reset. Here it is logged, recorded in NVM for the next boot's
[BOOT] line, and the board soft-reloads after a pause.
"""

import time
import supervisor

try:
    import app  # noqa: F401  runs the main loop; only returns by raising
except Exception as e:  # Ctrl-C raises KeyboardInterrupt, not Exception, so the REPL still works
    try:
        import diag
        diag.on_crash(e)
    except Exception as e2:  # diag itself is broken: still log and reload
        print('[CRASH] %r (diag failed: %r)' % (e, e2))
    time.sleep(10)  # time to read the serial log; avoids a tight crash loop hammering the APIs
    supervisor.reload()
