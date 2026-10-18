"""Diagnose virtual webcam unplug/replug in an unchanged SeedQR-enabled image.

Uses Chromium's synthetic webcam, no recovery words or physical camera. Captures
native guest failures and whether USB replug restores frame delivery without
sending Esc. Requires Playwright, Chromium and tesseract. Run one VM at a time.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--url', required=True, help='Bundle with a SeedQR-enabled image and USB device id camera')
parser.add_argument('--chromium')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
results = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.chromium, headless=True,
        args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
    page = browser.new_page(viewport={'width':1366,'height':768})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def text():
        assert not errors, errors
        assert not page.locator('#status').inner_text().startswith('Stopped:'), page.locator('#status').inner_text()
        capture_guest(page, out/'screen.png')
        raw = subprocess.run(['tesseract', str(out/'screen.png'), 'stdout', '--psm', '11'], text=True, capture_output=True, check=True).stdout
        (out/'screen.txt').write_text(raw)
        return re.sub(r'\s+', ' ', raw).casefold()

    def wait(label, timeout=70):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            current = text()
            if label.casefold() in current: return current
            page.wait_for_timeout(400)
        raise TimeoutError(label)

    def qmp(name, arguments=None):
        return page.evaluate('([name,args]) => cameraQmp.command(name,args)', [name, arguments or {}])

    def enable():
        page.locator('#camera').click()
        page.wait_for_function("document.querySelector('#camera').textContent === 'Stop camera'")
        page.locator('#screen').focus()

    def frame_count():
        return page.evaluate("cameraEvents.filter(e=>e.event==='VIDEO_FRAME').length")

    try:
        for case in ['qr-opening','qr-streaming','randomness-opening','randomness-streaming']:
            # Start a fresh signer so the original camera device has its normal
            # startup permissions, independently of earlier hotplug experiments.
            page.goto(args.url)
            page.wait_for_function("document.querySelector('#screen').dataset.ready === 'true'", timeout=90000)
            page.evaluate("""async () => {
                const {Qmp} = await import('./qmp.js');
                const command = Qmp.prototype.command;
                window.inputEvents=[];
                Qmp.prototype.command = function(name,args,...rest) {
                    window.cameraQmp=this;
                    if(name==='input-send-event') inputEvents.push(...args.events);
                    return command.call(this,name,args,...rest);
                };
            }""")
            page.locator('#keyboard-prompt').click()
            page.keyboard.press('4')
            wait('Start a session')
            page.evaluate("""() => {
                window.cameraEvents=[];
                const receive=cameraQmp.onEvent;
                cameraQmp.onEvent=event=>{cameraEvents.push(event);receive(event);};
            }""")
            streaming = case.endswith('streaming')
            randomness = case.startswith('randomness')
            if streaming: enable()
            if randomness:
                for key, label in [('3','How many recovery words'),('1','How your recovery words are created'),
                                   ('Enter','Add randomness from your camera'),('1','Add coin tosses or dice rolls'),
                                   ('1','Collect camera randomness')]:
                    page.keyboard.press(key)
                    wait(label)
                page.keyboard.press('Enter')
            else:
                page.keyboard.press('1')
            if streaming:
                page.wait_for_function("cameraEvents.some(e=>e.event==='VIDEO_FRAME')")
                wait('collecting images' if randomness else 'Point this device')
            else:
                page.wait_for_function("!document.querySelector('#camera-request').hidden")
                assert not page.evaluate("document.querySelector('#camera-video').srcObject")

            started = time.monotonic()
            qmp('device_del', {'id':'camera'})
            page.wait_for_function("document.querySelector('#camera-request').hidden")
            assert 'QEMU USB Video Interface' not in qmp('human-monitor-command', {'command-line':'info usb'})
            # Match the recovery choice: this console font's "cannot" can be
            # read as "cammot" by OCR even when the guest title is correct.
            error_title = 'Try camera again' if randomness else 'Could not load recovery words'
            outcome = wait(error_title)
            capture_guest(page, out/f'{case}-unplug.png')
            result = {'case':case, 'seconds_to_guest_error':time.monotonic()-started, 'unplug_guest':outcome}
            print(f'PASS: {case}: unplug produced native guest error in {result["seconds_to_guest_error"]:.1f}s', flush=True)

            qmp('device_add', {'driver':'usb-video','id':'camera','bus':'ehci.0','videodev':'cam0'})
            page.wait_for_function("cameraQmp.command('human-monitor-command',{'command-line':'info usb'}).then(info => /Device \\d+\\.[1-9]\\d*,.*ID: camera/.test(info))")
            if not streaming: enable()
            page.locator('#screen').focus()
            if randomness:
                page.keyboard.press('2')  # Guest's Try camera again option.
                wait('Collect camera randomness')
                count = frame_count()
                page.keyboard.press('Enter')
            else:
                page.keyboard.press('Enter')
                wait('Start a session')
                count = frame_count()
                page.keyboard.press('1')

            end = time.monotonic()+70
            while time.monotonic()<end:
                outcome = text()
                assert 'write down your recovery words' not in outcome
                if frame_count()>count:
                    result['replug_delivered_frame'] = True
                    break
                if error_title.casefold() in outcome:
                    result['replug_delivered_frame'] = False
                    break
                page.wait_for_timeout(400)
            else:
                raise TimeoutError(f'{case}: no native result after replug')
            result['replug_guest'] = outcome
            result['escape_events'] = page.evaluate("inputEvents.filter(e=>e.data.key.data==='esc').length")
            assert result['escape_events'] == 0, result
            capture_guest(page, out/f'{case}-replug.png')
            results.append(result)
            (out/'results.json').write_text(json.dumps(results,indent=2))
            (out/f'{case}-events.json').write_text(json.dumps(page.evaluate('cameraEvents'),indent=2))
            print(f'FINDING: {case}: replug delivery={result["replug_delivered_frame"]}; no Esc events', flush=True)
        print('PASS: all USB probes completed without guest helpers, synthetic Esc or recovery-word generation', flush=True)
    except Exception:
        page.screenshot(path=str(out/'failure.png'))
        print(json.dumps({'status':page.locator('#status').inner_text(),'camera':page.locator('#camera-status').inner_text(),'errors':errors,'results':results},indent=2))
        raise
    finally:
        browser.close()
