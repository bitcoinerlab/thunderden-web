"""Boot the website and scan its companion's public SeedQR with synthetic video.

Requires Playwright, Chromium, ffmpeg and tesseract. No physical camera,
funded wallet, real recovery words or transaction broadcast is used.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--url', default='http://127.0.0.1:4173/site/')
parser.add_argument('--chromium')
parser.add_argument('--viewport', default='1366x768', help='Desktop browser viewport, for example 1280x640')
args = parser.parse_args()
width,height=map(int,args.viewport.split('x'))
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.chromium, headless=True)
    phone = browser.new_page(viewport={'width':375,'height':547})
    phone.goto(urljoin(args.url,'wallet-mockup/'))
    phone.wait_for_function("document.querySelector('#seed-qr svg')")
    # Capture the rendered QR over its actual paper and notebook rules, not a
    # freshly generated black/white substitute.
    phone.locator('#seed-qr').screenshot(path=str(out/'seed-qr.png'))
    browser.close()

    subprocess.run(['ffmpeg','-y','-loglevel','error','-loop','1','-framerate','10','-i',str(out/'seed-qr.png'),
        '-vf','pad=640:480:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p','-frames:v','10',
        '-f','yuv4mpegpipe',str(out/'camera.y4m')],check=True)
    browser = pw.chromium.launch(executable_path=args.chromium, headless=True,args=[
        '--use-fake-device-for-media-stream',f'--use-file-for-fake-video-capture={out / "camera.y4m"}'])
    context = browser.new_context(viewport={'width':width,'height':height})
    parsed = urlsplit(args.url)
    context.grant_permissions(['camera'],origin=f'{parsed.scheme}://{parsed.netloc}')
    page = context.new_page()
    errors = []
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("""(() => {
        const capture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
        window.cameraCalls=0;
        navigator.mediaDevices.getUserMedia=options=>{cameraCalls++;return capture(options);};
        window.loadingSamples=[];
        document.addEventListener('DOMContentLoaded',()=>{
            const startup=document.querySelector('#startup');
            const observer=new MutationObserver(()=>{
                for (const row of startup.querySelectorAll('li')) {
                    const progress=row.querySelector('progress');
                    loadingSamples.push({id:row.id,state:row.dataset.state,value:progress.value,
                        determinate:progress.hasAttribute('value'),
                        fill:parseFloat(row.style.getPropertyValue('--startup-progress')),
                        text:row.querySelector('small').textContent});
                }
                if (startup.hidden) observer.disconnect();
            });
            observer.observe(startup,{attributes:true,childList:true,subtree:true,characterData:true});
        });
    })();""")

    def wait_guest(label):
        end=time.monotonic()+60
        while time.monotonic()<end:
            assert not errors,errors
            assert not page.locator('#status').inner_text().startswith('Stopped:'),page.locator('#status').inner_text()
            capture_guest(page,out/'screen.png')
            text=subprocess.run(['tesseract',str(out/'screen.png'),'stdout','--psm','11'],
                capture_output=True,text=True,check=True).stdout
            (out/'screen.txt').write_text(text)
            if label.casefold() in re.sub(r'\s+',' ',text).casefold(): return
            page.wait_for_timeout(500)
        raise TimeoutError(label)

    try:
        page.goto(args.url)
        before=page.locator('#device').bounding_box()
        page.wait_for_function("document.querySelector('#screen').dataset.ready === 'true'",timeout=90000)
        after=page.locator('#device').bounding_box()
        assert all(abs(before[field]-after[field])<.5 for field in before),(before,after)
        assert page.locator('#screen').evaluate('screen=>[screen.width,screen.height]')==[640,400]
        assert page.locator('#screen').evaluate("screen=>getComputedStyle(screen).imageRendering")=='pixelated'
        assert page.locator('#keyboard-prompt').is_visible()
        assert page.locator('#startup li small').all_text_contents()==['✓ Ready','✓ Ready']
        assert page.locator('#startup [data-state="done"]').count()==2
        samples=page.evaluate('loadingSamples')
        assert samples and any(0<sample['value']<1 for sample in samples)
        for sample in samples:
            assert abs(sample['fill']-sample['value']*100)<.00001,sample
            if sample['id']=='startup-image': assert sample['determinate'],sample
            if sample['text'].endswith('%'):
                assert int(sample['text'][:-1])==int(sample['value']*100),sample
        assert page.locator('#boot-progress-bar').evaluate('bar=>getComputedStyle(bar).height')=='14px'
        assert page.locator('#keyboard-reminder').is_hidden()
        assert 'wallet' not in page.locator('#keyboard-guide').inner_text().lower()
        assert page.evaluate('cameraCalls')==0
        page.screenshot(path=str(out/'website-ready.png'))
        page.evaluate("""async () => {
            const {Qmp}=await import(new URL('./qmp.js',document.baseURI));
            const command=Qmp.prototype.command;
            window.siteInput=[];
            Qmp.prototype.command=function(name,args,...rest) {
                window.siteQmp=this;
                if(name==='input-send-event') siteInput.push(...args.events);
                return command.call(this,name,args,...rest);
            };
        }""")
        page.locator('#companion-link').focus()
        page.keyboard.press('Tab')
        assert page.locator('#expand-demo').evaluate('button=>document.activeElement===button')
        page.keyboard.press('Tab')
        assert page.locator('#keyboard-prompt').evaluate('prompt=>document.activeElement===prompt')
        page.keyboard.press('Enter')
        assert page.locator('#keyboard-prompt').is_hidden()
        assert page.evaluate('siteInput.length')==0,'Activation key reached the guest'
        reminder=page.locator('#keyboard-reminder')
        assert reminder.is_hidden(),'Activating the screen must not show the reminder'
        page.locator('#screen').click()
        assert reminder.is_visible()
        assert reminder.get_attribute('role')=='status'
        assert page.locator('#screen').evaluate('screen=>document.activeElement===screen')
        assert page.evaluate('siteInput.length')==0,'Mouse clicks must not inject guest input'
        assert page.evaluate("siteQmp.command('query-status').then(status=>status.running)"),'Reminder paused the guest'
        page.wait_for_timeout(200)
        page.screenshot(path=str(out/'keyboard-reminder.png'))
        page.wait_for_timeout(1400)
        page.locator('#screen').click(position={'x':20,'y':20})
        assert reminder.evaluate('element=>getComputedStyle(element).opacity')=='1','Repeat click made the reminder blink'
        page.wait_for_timeout(1800)
        assert reminder.is_visible(),'Repeat screen clicks must renew the timeout'
        assert reminder.evaluate('element=>getComputedStyle(element).opacity')=='1','Reminder faded relative to the first click'
        page.wait_for_function("document.querySelector('#keyboard-reminder').hidden",timeout=2000)
        page.locator('#screen').click()
        assert reminder.is_visible(),'A click after timeout must show the reminder immediately'
        reminder.get_by_role('button',name='Dismiss keyboard reminder').click()
        assert reminder.is_hidden(),'Clicking the reminder must close it without reopening it'
        assert page.locator('#screen').evaluate('screen=>document.activeElement===screen'),'Dismissing the reminder stole keyboard focus'
        assert page.locator('#screen').get_attribute('data-keyboard')=='active'
        assert page.evaluate('siteInput.length')==0,'Reminder dismissal injected guest input'
        page.locator('#screen').click()
        assert reminder.is_visible(),'A screen click after dismissal must show the reminder immediately'
        page.keyboard.press('ArrowDown')
        assert reminder.is_hidden(),'Guest keyboard input must immediately dismiss the reminder'
        page.wait_for_function('siteInput.some(event=>event.data.key.data==="down" && event.data.down)')
        page.locator('#screen').click()
        assert reminder.is_visible(),'A screen click after a key must show the reminder immediately'
        page.keyboard.press('1')
        wait_guest('Start a session')
        page.locator('#expand-demo').click()
        assert page.locator('body').get_attribute('data-demo-expanded')=='true'
        assert page.locator('#screen').get_attribute('data-ready')=='true'
        page.locator('#screen').click()
        assert reminder.is_hidden(),'A click to recapture keyboard control must not show the reminder'
        page.locator('#screen').click()
        assert reminder.is_visible(),'Reminder must work in the expanded display'
        page.wait_for_timeout(200)
        page.screenshot(path=str(out/'keyboard-reminder-expanded.png'))
        first_input=page.evaluate('siteInput.length')
        reminder.get_by_role('button',name='Dismiss keyboard reminder').click()
        assert reminder.is_hidden()
        assert page.locator('#screen').evaluate('screen=>document.activeElement===screen')
        assert page.evaluate('siteInput.length')==first_input
        page.locator('#screen').click()
        assert reminder.is_visible()
        page.keyboard.press('Escape')
        assert reminder.is_hidden()
        page.wait_for_function('index=>siteInput.slice(index).some(event=>event.data.key.data==="esc" && event.data.down)',arg=first_input)
        assert page.locator('body').get_attribute('data-demo-expanded')=='true'
        # F8 must exit even while the guest owns Tab and Esc.
        page.keyboard.press('F8')
        assert page.locator('body').get_attribute('data-demo-expanded')=='false'
        assert not page.evaluate('index=>siteInput.slice(index).some(event=>event.data.key.data==="f8")',first_input)
        assert page.locator('#screen').get_attribute('data-ready')=='true'
        wait_guest('Start a session')
        page.locator('#screen').click()
        page.keyboard.press('1')
        page.wait_for_function("!document.querySelector('#camera-request').hidden",timeout=20000)
        assert page.evaluate('cameraCalls')==0
        assert page.evaluate("siteQmp.command('query-status').then(status=>!status.running)")
        page.locator('#camera-enable').click()
        page.wait_for_function("document.querySelector('#camera-request').hidden && document.querySelector('#camera-led').dataset.active==='true'")
        wait_guest('Recovery words scanned')
        page.screenshot(path=str(out/'public-seed-import.png'))
        assert page.evaluate('cameraCalls')==1
        assert page.evaluate("siteQmp.command('query-status').then(status=>status.running)")
        page.locator('#expand-demo').click()
        assert page.locator('#camera-panel').is_visible()
        assert page.locator('#camera-led').get_attribute('data-active')=='true'
        assert page.evaluate('cameraCalls')==1
        assert page.locator('#camera-panel #camera').inner_text()=='Stop camera'
        assert page.locator('#camera-panel-title').inner_text()=='Camera on'
        page.locator('#camera-close').click()
        assert page.locator('#camera-panel').is_visible()
        assert page.locator('#camera-video').is_hidden()
        assert page.locator('#camera-close').inner_text()=='Show'
        assert page.locator('#camera-close').get_attribute('aria-expanded')=='false'
        assert page.locator('#camera').is_visible()
        assert page.locator('#camera-led').get_attribute('data-active')=='true'
        assert page.evaluate("document.querySelector('#camera-video').srcObject.getTracks().every(track=>track.readyState==='live')")
        page.screenshot(path=str(out/'camera-collapsed.png'))
        page.locator('#camera-close').click()
        assert page.locator('#camera-video').is_visible()
        assert page.locator('#camera-close').get_attribute('aria-expanded')=='true'
        assert page.evaluate('cameraCalls')==1,'Showing the preview must reuse capture'
        page.screenshot(path=str(out/'camera-expanded.png'))
        page.locator('#demo-exit').click()
        assert page.locator('#camera-led').get_attribute('data-active')=='true'
        assert page.evaluate('cameraCalls')==1
        page.locator('#camera-close').click()
        page.evaluate("window.stoppedCameraTracks=document.querySelector('#camera-video').srcObject.getTracks()")
        page.locator('#camera').click()
        page.wait_for_function("document.querySelector('#camera-led').dataset.active==='false'")
        assert page.locator('#camera-panel').is_hidden()
        assert page.locator('#keyboard-reminder').is_hidden()
        assert page.evaluate("stoppedCameraTracks.every(track=>track.readyState==='ended')")
        assert page.evaluate("document.querySelector('#camera-video').srcObject===null")
        # Reopen capture explicitly to check that hiding the entire demo also
        # releases an expanded preview, without restarting the guest.
        page.locator('#camera').evaluate('button=>button.click()')
        page.wait_for_function("document.querySelector('#camera-led').dataset.active==='true' && !document.querySelector('#camera-video').hidden && document.querySelector('#camera').textContent==='Stop camera'")
        assert page.locator('#camera-video').is_visible()
        assert page.evaluate('cameraCalls')==2
        page.evaluate("window.testCameraTracks=document.querySelector('#camera-video').srcObject.getTracks()")
        page.set_viewport_size({'width':375,'height':667})
        page.wait_for_function("document.querySelector('#camera-led').dataset.active==='false'")
        assert page.locator('#device').is_hidden()
        assert page.locator('#phone-demo').is_visible()
        assert page.evaluate("testCameraTracks.every(track=>track.readyState==='ended')")
        assert page.evaluate("document.querySelector('#camera-video').srcObject===null")
        page.set_viewport_size({'width':width,'height':height})
        assert page.locator('#device').is_visible()
        page.locator('#screen').click()
        page.keyboard.press('Escape')
        wait_guest('Start a session')
        frames=int(page.locator('#screen').get_attribute('data-frames'))
        page.set_viewport_size({'width':800,'height':600})
        assert page.locator('#device').is_visible()
        assert page.locator('#screen').get_attribute('data-ready')=='true'
        page.wait_for_function('previous=>Number(document.querySelector("#screen").dataset.frames)>previous',arg=frames)
        assert page.evaluate('siteInput.length')>0
        assert page.locator('body').get_attribute('data-demo-state')=='running'
        page.locator('#screen').scroll_into_view_if_needed()
        page.screenshot(path=str(out/'running-after-resize.png'))
        dialogs=[]
        page.on('dialog',lambda dialog:(dialogs.append(dialog.type),dialog.dismiss()))
        # Restart during active capture: cleanup must happen before navigation,
        # not only when the old document is eventually discarded.
        page.locator('#camera').evaluate('button=>button.click()')
        page.wait_for_function("document.querySelector('#camera-led').dataset.active==='true' && !document.querySelector('#camera-video').hidden && document.querySelector('#camera').textContent==='Stop camera'")
        page.evaluate("""() => {
            const tracks=document.querySelector('#camera-video').srcObject.getTracks();
            const input=document.querySelector('#restart');
            input.addEventListener('click',()=>sessionStorage.setItem('restartCameraStopped',
                String(tracks.every(track=>track.readyState==='ended') && document.querySelector('#camera-video').srcObject===null)));
        }""")
        with page.expect_navigation():
            page.locator('#restart').click()
        page.wait_for_function("document.querySelector('#screen').dataset.ready==='true'",timeout=90000)
        assert not dialogs,'The power button must restart without confirmation'
        assert page.evaluate("sessionStorage.getItem('restartCameraStopped')")=='true'
        page.evaluate("sessionStorage.removeItem('restartCameraStopped')")
        assert page.locator('#keyboard-prompt').is_visible()
        assert page.locator('#camera-panel').is_hidden()
        assert page.locator('#camera-led').get_attribute('data-active')=='false'
        assert page.evaluate('cameraCalls')==0
        wait_guest('Choose a Bitcoin network')
        page.screenshot(path=str(out/'restarted.png'))
        page.locator('#keyboard-prompt').click()
        assert reminder.is_hidden(),'Initial mouse activation must not show the reminder'
        page.locator('#screen').click()
        assert reminder.is_visible()
        page.locator('#intro-title').click()
        assert reminder.is_hidden(),'Clicking outside must immediately dismiss the reminder'
        assert not errors,errors
        (out/'checks.json').write_text(json.dumps({'display':[640,400],'pixelated':True,
            'laptop_geometry_stable':True,'activation_key_isolated':True,'companion_seedqr_decoded':True,
            'keyboard_reminder_does_not_inject_or_pause':True,'keyboard_reminder_timeout_renews':True,
            'keyboard_reminder_click_dismissal_preserves_focus':True,'keyboard_reminder_no_cooldown':True,
            'keyboard_reminder_clears_on_guest_key':True,
            'keyboard_reminder_expanded_and_blur':True,
            'rendered_paper_seedqr_decoded':True,
            'narrow_layout_stops_camera':True,
            'preview_collapses_without_stopping':True,'stop_available_when_collapsed':True,
            'power_restarts_without_confirmation':True,'restart_stops_camera_before_navigation':True,
            'expanded_esc_reaches_guest':True,'expanded_f8_exits_without_guest_input':True,
            'expanded_preserves_guest_and_capture':True,
            'phone_viewport':[375,547],
            'camera_calls':page.evaluate('cameraCalls'),'physical_camera_tested':False,
            'initial_viewport':[width,height],'running_after_resize':[800,600]},indent=2))
        print('PASS: real 640x400 website boot, stable laptop geometry and keyboard activation-key isolation')
        print('PASS: companion-generated public SeedQR decodes in the unchanged guest; permission is explicit and stopping releases capture')
        print('PASS: resizing the running demo to 800x600 keeps the same ready guest rendering')
        print('PASS: preview collapses without stopping capture; Show reuses it and Stop releases all tracks')
        print('PASS: laptop power button stops capture and restarts to the real network menu without confirmation')
        print('PASS: expanding preserves the guest/camera; Esc reaches Thunder Den and F8 exits without leaking a guest key')
        print('PASS: screen clicks renew the keyboard reminder without blinking; no cooldown, and clicking the reminder closes it without losing keyboard focus')
    except Exception:
        page.screenshot(path=str(out/'failure.png'))
        print(json.dumps({'status':page.locator('#status').inner_text(),
            'camera':page.locator('#camera-status').inner_text(),'errors':errors},indent=2))
        raise
    finally:
        browser.close()
