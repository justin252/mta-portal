# Branch: show-the-g

## Summary

Add G train support with button toggling. Standardize display to single train line indicator (one circle on left, not dual stacked circles).

## Changes

### Core Features

**Button Toggle System**
- UP button → L train (Graham Av, stop L11)
- DOWN button → G train (Metropolitan Av, stop G29)
- State persists to `/train_state.txt` (survives reboots)
- 1s fade animation on switch
- Requires `boot.py` for filesystem write access

**Train Line Display Standardization**
- Single circle design on left side (x=8, y=16)
- Circle radius: 7px, no text overlap with labels at x=18
- L train: gray circle (#444444) with white 'L'
- G train: MTA official green (#6CBE45) with white 'G'
- Removed old dual-circle vertical layout

### Files Changed

**New Files**
- `boot.py` - enable filesystem writes
- `g-dashboard.bmp` - G train bitmap (green circle + white G)
- `generate_g_bitmap.py` - bitmap generation script
- `CHANGES.md` - this file

**Modified**
- `code.py`
  - Added `STATIONS` config for L/G trains
  - Implemented button debouncing with `adafruit_debouncer`
  - Added `switch_line()` with fade animation
  - Dynamic bitmap reloading on toggle
  - Persistent state via `/train_state.txt`

- `l-dashboard.bmp` - updated to single-circle design

- `test_bitmap.py`
  - Rewrote tests for single-circle layout
  - Added G train bitmap tests
  - Verify circle position, colors, no text overlap

- `CLAUDE.md` - updated docs for button controls, G train support

- `README.md` - added usage instructions

### Dependencies

**New**: `adafruit_debouncer` (required in `/lib` on device)

### Testing

All tests pass (25/25):
- 10 bitmap tests (dimensions, positioning, colors, letters)
- 15 logic tests (arrival parsing, filtering, formatting)

Run: `cd /tmp && python3 -m pytest /path/to/mta-portal/test_*.py -v`

### Design Specs

**Single Circle Layout**
- Position: x=8, y=16 (left side, vertically centered)
- Radius: 7px
- Colors:
  - G: #6CBE45 (108, 190, 69) - MTA official green
  - L: #444444 (68, 68, 68) - gray
- Letter: 14pt Helvetica, bold (drawn 9x for thickness), white

**Previous Design Issues**
- Had two stacked circles (top/bottom halves)
- Wrong green color for G (#6DCD39 vs #6CBE45)
- Circle centered at x=32 (screen center) instead of left side

## Deployment

```bash
# Generate bitmaps
python3 generate_g_bitmap.py

# Deploy to device
cp boot.py code.py {l,g}-dashboard.bmp /Volumes/CIRCUITPY/
cp -r fonts /Volumes/CIRCUITPY/

# Ensure adafruit_debouncer in /Volumes/CIRCUITPY/lib/
```

Device auto-reloads on file save.
