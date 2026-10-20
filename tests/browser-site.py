"""Check the local website layout and companion without starting an emulator.

Requires Python Playwright and Chromium. All emulator downloads are held pending.
This checks viewport layout, not physical phones or cameras.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--url', default='http://127.0.0.1:4173/site/')
parser.add_argument('--chromium')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.chromium, headless=True)
    results = []
    cases = [(1280,640,False),(1920,1080,False),(1440,1200,False),(1440,900,False),(1366,768,False),
        (1280,800,False),(1280,720,False),(1280,600,False),(1024,768,False),
        (1024,600,False),(960,640,False),(800,600,False),(768,501,False),
        (844,390,False),(390,844,False),(360,640,False),(767,768,False),(768,500,False),
        (375,667,True),(375,547,True),(390,844,True),(360,640,True),(844,390,True),
        (768,1024,True),(1024,768,True),(820,1180,True)]
    for width,height,touch in cases:
        page = browser.new_page(viewport={'width':width,'height':height},screen={'width':width,'height':height},is_mobile=touch,has_touch=touch)
        errors, pending, requests = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url))
        page.route('**/assets/site/thunderden.img', lambda route: pending.append(route))
        page.route('**/emulator/qemu-system-x86_64.wasm', lambda route: pending.append(route))
        try:
            page.goto(args.url)
            page.wait_for_function('document.body.dataset.demoState')
            page.evaluate('document.fonts.ready')
            page.wait_for_function("document.querySelector('#companion-qr svg')")
            assert page.locator('.demo-footer, .website .warning, #about').count()==0
            assert page.locator('#device #restart').get_attribute('aria-label')=='Restart demo'
            assert page.locator('#camera-panel #camera').count()==1
            narrow=width<=767 or (width<=999 and height<=500)
            if narrow:
                assert page.locator('body').get_attribute('data-demo-state')=='narrow'
                assert page.locator('#phone-demo').is_visible()
                assert page.locator('.demo-stage').is_hidden()
                assert page.locator('.demo-heading').is_hidden()
                assert page.locator('#expand-demo').is_hidden()
                assert page.locator('.demo-note').is_hidden()
                assert page.locator('#device').is_hidden()
                assert page.locator('.companion-card').is_hidden()
                assert page.locator('#phone-demo-title').inner_text()=='Try it before preparing a USB drive'
                assert 'live browser demo. No USB drive needed.' in page.locator('#phone-demo').inner_text()
                assert not page.locator('#phone-demo a, #phone-demo button').count()
                assert page.locator('#status').inner_text()=='Live demo available on a computer.'
                assert page.locator('#details-title').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth')<=width
                assert not pending and not any('/emulator/' in request or request.endswith('/app.js') for request in requests),requests
                assert not errors,errors
                page.screenshot(path=str(out/f'product-home-{width}x{height}-{"touch" if touch else "mouse"}.png'),full_page=True)
                page.screenshot(path=str(out/f'product-home-visible-{width}x{height}-{"touch" if touch else "mouse"}.png'))
                results.append({'viewport':[width,height],'touch':touch,'mode':'narrow'})
                if width==390 and not touch:
                    page.set_viewport_size({'width':1280,'height':720})
                    page.wait_for_function("document.querySelector('#startup-wasm').dataset.state==='active'")
                    assert page.locator('#device').is_visible()
                    assert len(pending)==2
                    page.set_viewport_size({'width':width,'height':height})
                    assert page.locator('#device').is_hidden()
                    page.set_viewport_size({'width':1280,'height':720})
                    assert page.locator('#device').is_visible()
                    assert len(pending)==2,'Expanding a product-only view must start the demo only once'
                if width==375 and height==667 and touch:
                    page.set_viewport_size({'width':768,'height':1024})
                    page.wait_for_function("document.querySelector('#startup-wasm').dataset.state==='active'")
                    assert page.locator('body').get_attribute('data-demo-state')=='running'
                    assert page.locator('#device').is_visible()
                    assert len(pending)==2,'Widening a touch layout must start the demo automatically'
                    page.set_viewport_size({'width':width,'height':height})
                    assert page.locator('#device').is_hidden()
                    page.set_viewport_size({'width':768,'height':1024})
                    assert page.locator('#device').is_visible()
                    assert len(pending)==2,'Returning to a wide touch layout must not restart the demo'
                continue
            assert page.locator('#device').is_visible(), 'The laptop must not disappear at a breakpoint'
            assert page.locator('#demo-title').inner_text()=='TRY THUNDER DEN IN YOUR BROWSER'
            assert page.locator('.demo-heading p').inner_text()=='The real USB image, running locally on a virtual computer.'
            assert page.locator('.scene #expand-demo').is_visible()
            assert page.locator('.laptop-art').is_visible()
            illustration=page.locator('.companion-illustration')
            assert illustration.is_visible()
            assert illustration.locator('img').evaluate('image=>image.complete && image.naturalWidth>0')
            assert illustration.locator('figcaption').all_text_contents()==['Demo walletThunder Den']
            assert illustration.bounding_box()['y']>=page.locator('#companion-title').bounding_box()['y']
            assert illustration.bounding_box()['y']+illustration.bounding_box()['height']<=page.locator('#companion-qr').bounding_box()['y']
            assert page.locator('#device').bounding_box()['width'] > 0
            assert page.locator('body').get_attribute('data-demo-state') == 'running', 'Every visible demo must start automatically'
            page.wait_for_function("document.querySelector('#startup-image').dataset.state === 'active'")
            page.wait_for_function("document.querySelector('#startup-wasm').dataset.state === 'active'")
            state = page.evaluate("""() => {
                const rect = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
                return {intro:rect('.site-intro'), card:rect('.companion-card'), laptop:rect('#device'),
                    note:rect('.demo-note'), details:rect('#details'), stage:rect('.demo-stage'),
                    power:rect('#restart'), screen:rect('#screen-wrapper'),
                    pageWidth:document.documentElement.scrollWidth, firstScreen:rect('.first-screen'),
                    font:getComputedStyle(document.body).fontFamily,
                    imageRendering:getComputedStyle(document.querySelector('#screen')).imageRendering};
            }""")
            page.screenshot(path=str(out/f'site-{width}x{height}-{"touch" if touch else "mouse"}.png'), full_page=False)
            assert state['pageWidth'] <= width, state
            assert state['font'].startswith('Inter'), state
            assert not errors, errors
            card = page.locator('.companion-card').inner_text()
            assert 'Use your phone as a demo wallet' in card, card
            assert 'Scan this QR with your phone to open a fake wallet web page.' in card and 'Use it with the virtual laptop to try Thunder Den.' in card, card
            assert page.locator('.companion-card > p strong').all_text_contents()==['with your phone']
            assert 'Show and scan QR codes' not in card, card
            assert 'No app to install.' in card, card
            assert 'Or type this on your phone:' in card and 'Open the demo wallet' not in card, card
            assert 'Sparrow' not in card and 'Local preview' not in card, card
            assert page.locator('#companion-link').get_attribute('href') == urljoin(args.url,'wallet-mockup/')
            companion=urlsplit(urljoin(args.url,'wallet-mockup/'))
            assert page.locator('#companion-link').inner_text()==companion.netloc+companion.path.rstrip('/')
            assert all(urlsplit(request).netloc == urlsplit(args.url).netloc for request in requests), requests
            for name in ['card','laptop','screen','note','power']:
                box=state[name]
                assert box['width'] > 0 and box['height'] > 0 and box['x'] >= 0 and box['right'] <= width+1, (name,state)
            assert state['laptop']['y'] >= state['intro']['bottom'], state
            assert state['note']['y'] >= state['laptop']['bottom'], state
            assert state['details']['y'] >= state['stage']['bottom'], state
            assert state['details']['y']-state['stage']['bottom'] <= 40, state
            assert 'QR scanning and display are significantly better on a real laptop.'==page.locator('.demo-note').inner_text()
            assert state['power']['width']>=44 and state['power']['height']>=44,state
            assert state['power']['y']>state['screen']['bottom'],state
            assert state['power']['right']<=state['laptop']['right'],state
            expand=page.locator('#expand-demo').bounding_box()
            frame_right=state['laptop']['x']+1000/1120*state['laptop']['width']
            frame_top=state['laptop']['y']+18/830*state['laptop']['height']
            assert abs(expand['x']+expand['width']-frame_right)<1,(expand,state)
            assert 8<=frame_top-expand['y']-expand['height']<=24,(expand,state)
            # The visible power face sits inside the deck's right-hand band,
            # clear of its top lip and the keyboard, at every supported size.
            face=page.locator('#restart circle').bounding_box()
            deck_top=state['laptop']['y']+617/830*state['laptop']['height']
            assert face['y']>=deck_top+1,(face,deck_top)
            assert page.locator('#restart svg').bounding_box()['width']==44
            margins=page.locator('#restart circle').evaluate("""circle => {
                const matrix=circle.getScreenCTM(), laptop=document.querySelector('#device').getBoundingClientRect();
                const gaps=[Infinity,Infinity,Infinity];
                for(let i=0;i<72;i++) {
                    const point=new DOMPoint(19.6*Math.cos(i*Math.PI/36),19.6*Math.sin(i*Math.PI/36)).matrixTransform(matrix);
                    const x=(point.x-laptop.x)/laptop.width*1120, y=(point.y-laptop.y)/laptop.height*830;
                    const deckRight=1005+(y-617)*66/174, keyboardRight=950.55+(y-637.36)*.329;
                    gaps[0]=Math.min(gaps[0],y-617);
                    gaps[1]=Math.min(gaps[1],(x-keyboardRight)/Math.hypot(1,.329));
                    gaps[2]=Math.min(gaps[2],(deckRight-x)/Math.hypot(1,66/174));
                }
                return gaps.map(gap=>gap*laptop.width/1120);
            }""")
            assert min(margins)>0 and max(margins)-min(margins)<2,margins
            if not touch and width==1366:
                page.locator('#restart').hover()
                assert page.locator('#power-label').is_visible()
                page.screenshot(path=str(out/'power-hover.png'))
            assert state['imageRendering'] == 'pixelated', state
            if width >= 1000 and height >= 900:
                # Keep the usable display and companion in view. The decorative
                # deck can extend below the viewport in the natural page flow.
                for name in ['intro','card','screen']:
                    box = state[name]
                    assert box['x'] >= 0 and box['right'] <= width+1 and box['y'] >= 0 and box['bottom'] <= height+1, (name,state)
                assert state['card']['right'] < state['laptop']['x'], state
            if width>=1000 and height>=1000:
                assert page.locator('#details-title').bounding_box()['y']<height-50,state
                assert state['firstScreen']['height']<height-100,state
            if width >= 1000:
                assert state['card']['right'] < state['laptop']['x'], state
            else:
                assert state['laptop']['bottom'] <= state['card']['y'], state
            if (width,height) in [(1280,720),(1366,768),(1024,600),(800,600),(768,1024),(820,1180)]:
                before_downloads=len(pending)
                page.locator('#expand-demo').scroll_into_view_if_needed()
                before_scroll=page.evaluate('scrollY')
                page.locator('#expand-demo').click()
                assert page.locator('body').get_attribute('data-demo-expanded')=='true'
                assert page.locator('.scene').get_attribute('role')=='dialog'
                assert page.locator('.scene').get_attribute('aria-modal')=='true'
                assert page.locator('#demo-exit').is_visible()
                assert page.locator('#demo-exit').evaluate('button=>document.activeElement===button')
                page.keyboard.press('Shift+Tab')
                assert page.evaluate("document.activeElement.closest('.scene, #camera-panel')!==null")
                page.locator('#demo-exit').focus()
                assert page.locator('.laptop-art').is_hidden()
                assert page.locator('.site-header').evaluate('header=>header.inert')
                assert page.evaluate('document.fullscreenElement===null')
                assert page.locator('#screen').evaluate('screen=>[screen.width,screen.height]')==[640,400]
                assert len(pending)==before_downloads,'Expanding must not boot or restart the guest'
                bounds=page.locator('#screen-wrapper').bounding_box()
                exit_bounds=page.locator('#demo-exit').bounding_box()
                assert bounds['x']>=0 and bounds['x']+bounds['width']<=width
                assert bounds['y']>=exit_bounds['y']+exit_bounds['height']
                assert bounds['y']+bounds['height']<=height
                page.keyboard.press('Escape')
                assert page.locator('body').get_attribute('data-demo-expanded')=='true','Esc belongs to Thunder Den'
                page.screenshot(path=str(out/f'expanded-{width}x{height}.png'))
                page.locator('#demo-exit').click()
                assert page.locator('body').get_attribute('data-demo-expanded')=='false'
                assert page.locator('.laptop-art').is_visible()
                assert page.locator('#expand-demo').evaluate('button=>document.activeElement===button')
                assert not page.locator('.site-header').evaluate('header=>header.inert')
                assert abs(page.evaluate('scrollY')-before_scroll)<1
                page.locator('#expand-demo').click()
                page.keyboard.press('F8')
                assert page.locator('body').get_attribute('data-demo-expanded')=='false'
                assert len(pending)==before_downloads
            assert len(pending) == 2, len(pending)
            if touch and width == 768:
                page.locator('#expand-demo').click()
                page.set_viewport_size({'width':390,'height':844})
                assert page.locator('#device').is_hidden()
                assert page.locator('#phone-demo').is_visible()
                assert page.locator('body').get_attribute('data-demo-state') == 'running'
                assert page.locator('body').get_attribute('data-demo-expanded')=='false'
                assert len(pending) == 2, 'Resizing restarted the emulator'
                page.set_viewport_size({'width':width,'height':height})
                assert page.locator('#device').is_visible()
                assert page.locator('#phone-demo').is_hidden()
                assert len(pending) == 2, 'Returning to a wide layout restarted the emulator'
            if not touch and width>=800:
                # Layout-only preview of the ready prompt; no fabricated guest pixels.
                page.evaluate("document.querySelector('#boot-cover').hidden=true; document.querySelector('#keyboard-prompt').hidden=false")
                assert page.locator('#keyboard-wallet-hint').count()==0
                assert 'wallet' not in page.locator('#keyboard-guide').inner_text().lower()
                screen=page.locator('#screen-wrapper').bounding_box()
                guide=page.locator('#keyboard-guide').bounding_box()
                assert guide['x']>=screen['x'] and guide['y']>=screen['y'],(screen,guide)
                assert guide['x']+guide['width']<=screen['x']+screen['width'],(screen,guide)
                assert guide['y']+guide['height']<=screen['y']+screen['height'],(screen,guide)
                page.screenshot(path=str(out/f'ready-{width}x{height}.png'))
                page.evaluate("document.querySelector('#boot-cover').hidden=false; document.querySelector('#keyboard-prompt').hidden=true")
            if not touch and width == 1366:
                page.locator('.site-header nav a').filter(has_text='How it works').click()
                page.wait_for_function('window.scrollY > 100')
                assert page.locator('#details-title').evaluate('el => el.getBoundingClientRect().top >= 0 && el.getBoundingClientRect().top < innerHeight')
                page.screenshot(path=str(out/'details.png'))
            results.append({'viewport':[width,height], 'touch':touch, **state})
        finally:
            for route in pending:
                route.abort()
            page.close()
    # Removing the About button must not remove error diagnostics or recovery.
    for status,message in [(200,'image checksum mismatch'),(404,'Cannot load')]:
        page=browser.new_page(viewport={'width':1280,'height':720})
        pending=[]
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/assets/site/thunderden.img',lambda route:route.fulfill(
            status=status,body='Invalid public image fixture',content_type='application/octet-stream'))
        page.route('**/emulator/qemu-system-x86_64.wasm',lambda route:pending.append(route))
        try:
            page.goto(args.url)
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Stopped:')")
            assert message in page.locator('#boot-error').inner_text()
            assert page.locator('#retry').is_visible()
            assert page.locator('#restart').is_enabled()
            assert page.locator('#camera').is_disabled()
            page.locator('#boot-diagnostics').click()
            assert page.locator('#about-dialog').is_visible()
            assert message in page.locator('#log').inner_text()
            page.keyboard.press('Escape')
            assert page.locator('#about-dialog').is_hidden()
            assert not errors,errors
            page.screenshot(path=str(out/f'error-{status}.png'))
        finally:
            for route in pending: route.abort()
            page.close()
    page = browser.new_page(viewport={'width':390,'height':844})
    requests = []
    page.on('request', lambda request: requests.append(request.url))
    page.goto(urljoin(args.url,'wallet-mockup/'))
    page.wait_for_function("document.querySelector('#seed-qr svg')")
    assert page.locator('#seed-title').inner_text() == 'Scan a seed QR'
    assert page.locator('.companion-illustration').count()==0, 'Do not add illustration height to the phone walkthrough'
    assert page.locator('#demo-words span').all_text_contents() == [f'{index:02d}abandon' for index in range(1,12)] + ['12about']
    assert not page.locator('input, textarea').count()
    assert page.locator('#reply-video').is_hidden()
    assert not any('/emulator/' in request for request in requests), requests
    page.screenshot(path=str(out/'phone.png'), full_page=True)
    page.locator('#seed-qr').screenshot(path=str(out/'public-seed-qr.png'))
    (out/'layout.json').write_text(json.dumps(results, indent=2))
    print('PASS: compact laptop layouts including 1024x600 and 1280x720 keep the full demo')
    print('PASS: narrow layouts show product information only, with no emulator downloads or wallet/start buttons')
    print('PASS: visible laptop/tablet demos start automatically; resizing hides/restores without restarting')
    print('PASS: details anchor and phone companion with public SeedQR/manual words; no real-wallet inputs or camera request')
    print('PASS: phone/laptop illustration fits the entry card; ready prompt stays focused on keyboard control')
    print('PASS: natural page flow reveals details on tall screens; power button replaces the demo toolbar')
    print('PASS: expanded display fits laptop/tablet layouts; Back/F8 exits, Esc does not and no guest is restarted')
    print('PASS: image failures retain in-screen diagnostics and recovery without a permanent About button')
    browser.close()
