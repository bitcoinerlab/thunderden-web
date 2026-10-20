"""Phone walkthrough layout, cancellation and late camera grants; no emulator.

Requires Python Playwright and Chromium. Uses synthetic MediaStreams only.
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
parser.add_argument('--url',default='http://127.0.0.1:4173/site/wallet-mockup/')
parser.add_argument('--chromium')
args=parser.parse_args()
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.chromium,headless=True)
    for width,height in [(375,667),(375,547),(390,844),(360,640),(320,568),(320,460),(844,390)]:
        page=browser.new_page(viewport={'width':width,'height':height})
        errors=[]
        requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(request.url))
        page.add_init_script("""(() => {
          window.cameraCalls=0;window.cameraTracks=[];window.delayCamera=false;
          navigator.mediaDevices.getUserMedia=async () => {
            cameraCalls++;
            if(delayCamera) await new Promise(resolve=>window.grantCamera=resolve);
            const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;
            const stream=canvas.captureStream(10);cameraTracks.push(...stream.getTracks());return stream;
          };
        })();""")
        try:
            page.goto(args.url)
            page.wait_for_function("document.body.dataset.step==='seed'")
            assert page.evaluate('cameraCalls')==0
            assert page.locator('#seed-title').inner_text()=='Scan a seed QR'
            assert page.locator('#seed-next').inner_text()=="I've scanned the seed QR"
            assert "This QR gives Thunder Den the demo wallet's recovery words." in page.locator('#seed-step > .step-note').inner_text()
            assert 'Keep real backups' not in page.locator('#seed-step').inner_text()
            instructions=page.locator('#seed-step > p:not(.eyebrow):not(.step-note)')
            assert '1: Bitcoin mainnet' in instructions.inner_text()
            assert 'Leave the passphrase blank.' in instructions.inner_text()
            assert instructions.bounding_box()['y']<page.locator('.paper-backup').bounding_box()['y']
            assert 'Enable the camera' not in page.locator('#seed-step').inner_text()
            assert 'No printing' not in page.locator('#seed-step').inner_text()
            assert page.locator('.paper-sheet').evaluate("el=>getComputedStyle(el).clipPath!=='none'")
            assert page.locator('#seed-qr').evaluate("el=>getComputedStyle(el).backgroundColor==='rgba(0, 0, 0, 0)'")
            assert page.locator('#seed-qr svg > rect').evaluate("el=>getComputedStyle(el).fill==='none'")
            page.evaluate('document.fonts.ready')
            if height>=460:
                qr=page.locator('#seed-qr').bounding_box()
                button=page.locator('#seed-next').bounding_box()
                assert qr['width']>=180,qr
                assert qr['y']>=0 and qr['y']+qr['height']<=height,(qr,height)
                assert button['height']>=44,button
                assert button['y']+button['height']<=height-8,(button,height)
                assert page.evaluate('scrollY')==0
            assert page.locator('#seed-words').get_attribute('open') is None
            assert page.locator('#demo-words').is_hidden()
            page.screenshot(path=str(out/f'seed-visible-{width}x{height}.png'))
            page.locator('#seed-words summary').click()
            assert page.locator('#seed-words p').inner_text()=='The QR above contains the recovery words below.'
            assert page.locator('#seed-words p').bounding_box()['y']<page.locator('#demo-words').bounding_box()['y']
            assert page.locator('#demo-words').is_visible()
            assert page.locator('#demo-words span').count()==12
            assert page.evaluate('document.documentElement.scrollWidth')<=width
            page.locator('#seed-words summary').click()
            page.evaluate('scrollTo(0,0)')
            for step in ['seed','payment']:
                if step=='payment': page.locator('#seed-next').click()
                if step=='payment':
                    assert page.locator('#payment-qr svg > rect').evaluate("el=>getComputedStyle(el).fill==='rgb(255, 255, 255)'")
                assert page.evaluate('document.documentElement.scrollWidth')<=width
                assert page.locator(f'#{step}-step').is_visible()
                assert page.locator('#done-step').is_hidden()
                page.screenshot(path=str(out/f'{step}-{width}x{height}.png'),full_page=True)
                if step=='payment':
                    label=page.locator('.payment-address dt').bounding_box()
                    address=page.locator('#payment-address').bounding_box()
                    assert abs(label['y']-address['y'])<4,(label,address)
                    assert page.locator('#payment-address').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
                    if height>=460:
                        qr=page.locator('#payment-qr').bounding_box()
                        button=page.locator('#scan-next').bounding_box()
                        assert qr['width']>=180,qr
                        assert qr['y']>=0 and qr['y']+qr['height']<=height,(qr,height)
                        assert button['height']>=44,button
                        assert button['y']+button['height']<=height-8,(button,height)
                        assert page.evaluate('scrollY')==0
                    page.screenshot(path=str(out/f'payment-visible-{width}x{height}.png'))
            assert page.evaluate('cameraCalls')==0
            # Cancelling a permission wait must stop a subsequently granted stream.
            page.evaluate('delayCamera=true')
            page.locator('#scan-next').click()
            page.wait_for_function("typeof grantCamera==='function'")
            page.locator('#scan-step [data-back]').click()
            page.evaluate('grantCamera()')
            page.wait_for_function("cameraTracks.length>0 && cameraTracks.every(track=>track.readyState==='ended')")
            assert page.locator('#payment-step').is_visible()
            assert page.locator('#done-step').is_hidden()
            assert page.locator('#reply-video').evaluate('video=>video.srcObject===null')
            # An active scan also stops immediately when Back is chosen.
            page.evaluate('delayCamera=false')
            page.locator('#scan-next').click()
            page.wait_for_function("document.querySelector('#reply-video').srcObject!==null")
            assert page.evaluate('document.documentElement.scrollWidth')<=width
            page.screenshot(path=str(out/f'scan-{width}x{height}.png'),full_page=True)
            page.locator('#scan-step [data-back]').click()
            assert page.evaluate("cameraTracks.every(track=>track.readyState==='ended')")
            assert page.locator('#reply-video').evaluate('video=>video.srcObject===null')
            assert not page.locator('input,textarea').count()
            assert page.evaluate('localStorage.length===0 && sessionStorage.length===0')
            assert not any('/emulator/' in request for request in requests)
            assert not errors,errors
        finally:
            page.close()
    browser.close()
    print('PASS: seed/payment QRs and next buttons visible without scrolling at iPhone SE-sized and reduced browser viewports')
    print('PASS: full payment address stays beside To without wrapping or clipping')
    print('PASS: collapsible recovery words and seven phone layouts without horizontal overflow')
    print('PASS: no early camera requests, no wallet inputs/storage or emulator downloads; cancelling stops active and late-granted capture')
