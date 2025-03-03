import vectoros
import keyboardcb
import keyleds
import asyncio
import screennorm
import math
import gc
import keyboardio
from vos_state import vos_state

# get the screen
screen = screennorm.ScreenNorm()

GRAPH_WIDTH = 240
GRAPH_HEIGHT = 240
GRAPH_CENTER_Y = GRAPH_HEIGHT // 2
GRAPH_SCALE = 100

_waves_lookup = {0: "sine", 1: "square", 2: "triangle", 3: "sawtooth"}

# initial waveform parameters
frequency = 1.0 
current_amplitude = 0.0
phase = 0.0
current_waveform = 0

# LED bitmask mapping for waveforms 
_waves_leds = {0: 1 << 5, 1: 1 << 4, 2: 1 << 3, 3: 1 << 2}

# colours for gradient
NEWEST = 0xFFFFFF
MIDDLE_AGED = 0x00FF00
OLDEST = 0x90EE90

exit_flag = False

# DSP: low-pass filter parameters
alpha = 0.1  # smoothing factor
filtered_waveform = [0.0] * GRAPH_WIDTH

def toggle_waveform(key):
    global current_waveform
    # turn off selected waveform LED
    keyboardio.KeyboardIO.leds &= ~(0b00111100)
    # cycle to the next waveform
    current_waveform = (current_waveform + 1) % 4
    # turn on new selected waveform LED
    keyboardio.KeyboardIO.leds |= _waves_leds[current_waveform]
    keyboardio.KeyboardIO.scan()
    print(f"Waveform changed to: {_waves_lookup[current_waveform]}")

def calculate_waveform(x, wave_type, wave_phase):
    normalized_x = x / GRAPH_WIDTH
    if wave_type == "sine":
        return math.sin(2 * math.pi * frequency * normalized_x + wave_phase)
    elif wave_type == "square":
        return 1.0 if math.sin(2 * math.pi * frequency * normalized_x + wave_phase) >= 0 else -1.0
    elif wave_type == "triangle":
        return (2 / math.pi) * math.asin(math.sin(2 * math.pi * frequency * normalized_x + wave_phase))
    elif wave_type == "sawtooth":
        return (2 / math.pi) * math.atan(math.tan(2 * math.pi * frequency * normalized_x + wave_phase / 2))
    return 0.0

def adjust_amplitude(key):
    global current_amplitude
    if key == keyleds.JOY_UP:
        current_amplitude = min(1.0, current_amplitude + 0.1)
        print(f"Amplitude increased to {current_amplitude}")
    elif key == keyleds.JOY_DN:
        current_amplitude = max(0.0, current_amplitude - 0.1)
        print(f"Amplitude decreased to {current_amplitude}")

def adjust_frequency(key):
    global frequency
    if key == keyleds.JOY_RT:
        frequency = min(5.0, frequency + 0.1)
        print(f"Frequency increased to {frequency}")
    elif key == keyleds.JOY_LF:
        frequency = max(0.1, frequency - 0.1)
        print(f"Frequency decreased to {frequency}")

def menu_button(key):
    global exit_flag
    exit_flag = True 

def interpolate_colour(colour1, colour2, factor):
    r1 = (colour1 >> 16) & 0xFF
    g1 = (colour1 >> 8) & 0xFF
    b1 = colour1 & 0xFF
    r2 = (colour2 >> 16) & 0xFF
    g2 = (colour2 >> 8) & 0xFF
    b2 = colour2 & 0xFF
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return (r << 16) | (g << 8) | b

def low_pass_filter(new_value, prev_value, alpha):
    return alpha * new_value + (1 - alpha) * prev_value

# main animation loop
async def waveform_visualizer():
    global exit_flag, phase, current_amplitude, filtered_waveform
    exit_flag = False 
    vos_state.show_menu = False
    
    # set up keyboard callbacks
    keys = keyboardcb.KeyboardCB({
        keyleds.JOY_UP: adjust_amplitude, 
        keyleds.JOY_DN: adjust_amplitude,
        keyleds.JOY_RT: adjust_frequency, 
        keyleds.JOY_LF: adjust_frequency,  
        keyleds.KEY_MENU: menu_button,  
        keyleds.KEY_WAVE: toggle_waveform,  
    })

    screen.clear(0)
    
    keyboardio.KeyboardIO.leds |= _waves_leds[current_waveform] 
    keyboardio.KeyboardIO.scan()
    
    # store the last 12 waveforms
    wave_history = []
    for _ in range(12):
        wave_history.append([])
    
    vertical_lines = []
    for i in range(12):
        factor = i / 11.0
        if factor < 0.5:
            colour = interpolate_colour(NEWEST, MIDDLE_AGED, factor * 2)
        else:
            colour = interpolate_colour(MIDDLE_AGED, OLDEST, (factor - 0.5) * 2)
        vertical_lines.append(colour)
    
    while not exit_flag:
        # calculate the new waveform points
        new_wave_points = []
        for x in range(0, GRAPH_WIDTH, 1):
            wave_value = calculate_waveform(x, _waves_lookup[current_waveform], phase)
            # apply low-pass filter
            filtered_waveform[x] = low_pass_filter(wave_value, filtered_waveform[x], alpha)
            y = GRAPH_CENTER_Y - int(current_amplitude * GRAPH_SCALE * filtered_waveform[x])
            if 0 <= y < GRAPH_HEIGHT:
                new_wave_points.append((x, y))
        
        # remove the oldest waveform
        oldest_wave_points = wave_history.pop(0)
        for x, y in oldest_wave_points:
            screen.tft.pixel(x, y, 0)
        
        # append the new waveform to the history
        wave_history.append(new_wave_points)
        
        # draw all waveforms in history
        for i, wave_points in enumerate(wave_history):
            for x, y in wave_points:
                screen.tft.pixel(x, y, vertical_lines[i])

        phase += 0.05

        gc.collect()

        await asyncio.sleep_ms(100)

    keyboardio.KeyboardIO.leds &= ~(0b00111100)
    keyboardio.KeyboardIO.scan()
    keys.detach()

    vos_state.show_menu = True

async def vos_main():
    await waveform_visualizer()

if __name__ == "__main__":
    vectoros.run()
