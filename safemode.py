"""Runs instead of code.py when CircuitPython enters safe mode.

A brownout (LED matrix and WiFi sharing one USB supply) or a core fault puts the board
in safe mode, where it waits for someone to press reset. Reset automatically instead,
every time: the sign should never need a hand. The pause keeps the CIRCUITPY drive
usable between attempts, so a bad deploy that faults on boot can still be fixed over USB.
Self-contained on purpose: an error here would leave the board in safe mode for good.
"""

import time
import microcontroller
import supervisor

AUTO_RESET = ('BROWNOUT', 'HARD_FAULT', 'STACK_OVERFLOW', 'NLR_JUMP_FAIL', 'GC_ALLOC_OUTSIDE_VM',
              'NO_HEAP', 'INTERRUPT_ERROR', 'WATCHDOG')
PAUSE_S = 20

reason = str(supervisor.runtime.safe_mode_reason).split('.')[-1]
# Same NVM record as diag.remember(): [1] length, [2:] text. Skip identical rewrites (flash wear)
event = ('safemode ' + reason).encode()
record = bytes([len(event)]) + event
nvm = microcontroller.nvm
if bytes(nvm[1:1 + len(record)]) != record:
    nvm[1:1 + len(record)] = record

if reason in AUTO_RESET:
    time.sleep(PAUSE_S)
    microcontroller.reset()
