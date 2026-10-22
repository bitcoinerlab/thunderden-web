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

def check_notice_close(page,selector):
    notice=page.locator(selector)
    close=notice.locator('.notice-close')
    assert close.count()==1 and close.inner_text()=='×'
    assert close.get_attribute('aria-hidden')=='true'
    assert close.evaluate('element=>getComputedStyle(element).color')=='rgb(247, 147, 26)'
    card=notice.bounding_box()
    bounds=close.bounding_box()
    label=notice.locator(':scope > strong').bounding_box()
    assert bounds['width']>=24 and bounds['height']>=24,(card,bounds)
    assert bounds['x']>=label['x']+label['width'],(label,bounds)
    assert bounds['x']+bounds['width']<=card['x']+card['width'],(card,bounds)
    assert card['y']<=bounds['y']<=card['y']+4,(card,bounds)
    assert bounds['y']+bounds['height']<=card['y']+card['height'],(card,bounds)

def check_demo_modal(page,selector):
    modal=page.locator(selector)
    style=modal.evaluate('''element => {
        const style=getComputedStyle(element);
        return {font:style.fontFamily,background:style.backgroundColor,border:style.borderTopColor,
            radius:style.borderRadius,filter:style.filter,backdrop:style.backdropFilter};
    }''')
    assert 'Terminus' in style.pop('font'),style
    assert style=={'background':'rgb(43, 46, 38)','border':'rgb(247, 147, 26)',
        'radius':'2px','filter':'none','backdrop':'none'},style
    assert modal.locator('h2').evaluate('element=>getComputedStyle(element).fontSize')=='18px'
    assert modal.locator('p, summary, pre, button').evaluate_all('''elements=>elements.every(element=>{
        const style=getComputedStyle(element);
        return style.fontFamily.includes('Terminus') && style.fontSize==='16px';
    })''')

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
            warning=page.locator('#demo-warning')
            assert warning.count()==1
            assert warning.inner_text()=="LIVE DEMO: DON'T USE REAL FUNDS"
            sections=page.locator('.details-grid > article')
            assert sections.locator('h3').all_text_contents()==[
                'Bring your own laptop','Review the code with AI. Build it yourself.',
                'A fresh start, every time','Take security further']
            assert sections.locator('.section-number').all_text_contents()==['01','02','03','04']
            assert sections.nth(2).locator('p').all_text_contents()==[
                "Boot your laptop from USB, then enter or scan your recovery words to load your Bitcoin keys into RAM. Thunder Den never saves them to the USB or the laptop's drive.",
                'The system is built without support for disk storage, Wi-Fi, Bluetooth or Ethernet. You load your keys again each session, so keep your recovery-word backup safe.']
            fresh=sections.nth(2).bounding_box()
            security=sections.nth(3).bounding_box()
            if width>600:
                assert abs(fresh['y']-security['y'])<1 and fresh['x']+fresh['width']<security['x'],(fresh,security)
            else:
                assert fresh['y']+fresh['height']<=security['y'],(fresh,security)
            narrow=width<=767 or (width<=999 and height<=500)
            if narrow:
                assert page.locator('body').get_attribute('data-demo-state')=='narrow'
                assert page.locator('#phone-demo').is_visible()
                assert page.locator('.demo-stage').is_hidden()
                assert page.locator('.demo-heading').is_hidden()
                assert page.locator('#expand-demo').is_hidden()
                assert warning.is_hidden()
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
            image=illustration.locator('img').bounding_box()
            for label,center in zip(illustration.locator('figcaption span').all(),[35/200,145/200]):
                caption=label.bounding_box()
                assert abs(caption['x']+caption['width']/2-image['x']-image['width']*center)<.5,(image,caption,center)
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
            if width>=1200 and height>=700:
                previous_width=min(860,state['stage']['width']-244,max(520,height-220)*1120/830)
                assert state['laptop']['width']>=previous_width*1.1,state
                assert state['screen']['bottom']<=height-16,state
            if width>=1200 and height<=640:
                assert abs(state['laptop']['width']-520*1120/830)<1,state
            assert state['note']['y'] >= state['laptop']['bottom'], state
            assert state['details']['y'] >= state['stage']['bottom'], state
            assert state['details']['y']-state['stage']['bottom'] <= 40, state
            assert 'QR scanning and display are significantly better on a real laptop.'==page.locator('.demo-note').inner_text()
            assert state['power']['width']>=44 and state['power']['height']>=44,state
            assert state['power']['y']>state['screen']['bottom'],state
            assert state['power']['right']<=state['laptop']['right'],state
            expand=page.locator('#expand-demo').bounding_box()
            assert expand['height']>=44
            assert page.locator('#expand-demo').evaluate('button=>getComputedStyle(button).fontSize')=='13px'
            assert page.locator('#expand-demo svg').bounding_box()['width']==18
            if not touch and width==1366:
                for mode in ['normal','hover','focus']:
                    if mode=='hover': page.locator('#expand-demo').hover()
                    if mode=='focus':
                        page.mouse.move(0,0)
                        page.locator('#companion-link').focus()
                        page.keyboard.press('Tab')
                        assert page.locator('#expand-demo').evaluate('button=>button.matches(":focus-visible")')
                    style=page.locator('#expand-demo').evaluate('''button=>{
                        const style=getComputedStyle(button);
                        return {font:style.fontFamily,border:style.borderTopColor,text:style.color,
                            icon:getComputedStyle(button.querySelector('svg')).color,
                            background:style.backgroundColor,shadow:style.boxShadow};
                    }''')
                    assert style.pop('font').startswith('Inter'),style
                    assert style=={'border':'rgb(222, 223, 216)' if mode=='normal' else 'rgb(247, 147, 26)',
                        'text':'rgb(34, 35, 32)','icon':'rgb(34, 35, 32)' if mode=='normal' else 'rgb(247, 147, 26)',
                        'background':'rgb(255, 255, 255)','shadow':'none'},(mode,style)
                    page.screenshot(path=str(out/f'expand-button-{mode}.png'))
            assert page.locator('#device > #demo-warning').is_visible()
            warning_bounds=warning.bounding_box()
            subtitle=page.locator('.demo-heading p').bounding_box()
            assert warning_bounds['y']>=subtitle['y']+subtitle['height']+8,(warning_bounds,subtitle)
            frame_left=state['laptop']['x']+120/1120*state['laptop']['width']
            assert abs(warning_bounds['x']-frame_left)<1,(warning_bounds,state)
            assert warning_bounds['x']+warning_bounds['width']<=expand['x']-12,(warning_bounds,expand)
            assert warning.evaluate('element=>element.scrollWidth<=element.clientWidth')
            assert float(warning.evaluate('element=>getComputedStyle(element).fontSize').removesuffix('px'))>=11
            assert 'demo-warning' in page.locator('#screen').get_attribute('aria-describedby').split()
            frame_right=state['laptop']['x']+1000/1120*state['laptop']['width']
            frame_top=state['laptop']['y']+18/830*state['laptop']['height']
            assert abs(frame_top-warning_bounds['y']-warning_bounds['height']-2)<.5,(warning_bounds,state)
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
            clearance_tolerance=3 if state['laptop']['width']>860 else 2
            assert min(margins)>0 and max(margins)-min(margins)<clearance_tolerance,margins
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
                assert state['firstScreen']['height']<height,state
                if height>=1200:
                    assert page.locator('#details-title').bounding_box()['y']<height-50,state
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
                page.evaluate("document.querySelector('#keyboard-reminder').hidden=false")
                reminder=page.locator('#keyboard-reminder').bounding_box()
                assert reminder['x']>=bounds['x'] and reminder['y']>=bounds['y'],(bounds,reminder)
                assert reminder['x']+reminder['width']<=bounds['x']+bounds['width'],(bounds,reminder)
                assert reminder['y']+reminder['height']<=bounds['y']+bounds['height'],(bounds,reminder)
                assert abs(reminder['x']+reminder['width']/2-bounds['x']-bounds['width']/2)<.5,(bounds,reminder)
                assert abs(reminder['y']+reminder['height']/2-bounds['y']-bounds['height']/2)<.5,(bounds,reminder)
                check_notice_close(page,'#keyboard-reminder')
                page.evaluate("document.querySelector('#keyboard-reminder').hidden=true")
                exit_bounds=page.locator('#demo-exit').bounding_box()
                assert page.locator('.expanded-controls #demo-warning').is_visible()
                assert warning.count()==1
                warning_bounds=warning.bounding_box()
                assert warning_bounds['x']>=16 and warning_bounds['x']+warning_bounds['width']<=exit_bounds['x']-12,(warning_bounds,exit_bounds)
                assert warning_bounds['y']>=exit_bounds['y'] and warning_bounds['y']+warning_bounds['height']<=exit_bounds['y']+exit_bounds['height'],(warning_bounds,exit_bounds)
                assert warning_bounds['y']+warning_bounds['height']<=bounds['y'],(warning_bounds,bounds)
                assert bounds['x']>=0 and bounds['x']+bounds['width']<=width
                assert bounds['y']>=exit_bounds['y']+exit_bounds['height']
                assert bounds['y']+bounds['height']<=height
                page.keyboard.press('Escape')
                assert page.locator('body').get_attribute('data-demo-expanded')=='true','Esc belongs to Thunder Den'
                page.screenshot(path=str(out/f'expanded-{width}x{height}.png'))
                page.evaluate("document.querySelector('#boot-cover').hidden=true; document.querySelector('#keyboard-prompt').hidden=false")
                guide=page.locator('#keyboard-guide').bounding_box()
                assert guide['width']<=440,guide
                assert guide['x']>=bounds['x'] and guide['x']+guide['width']<=bounds['x']+bounds['width'],(bounds,guide)
                assert abs(guide['x']+guide['width']/2-bounds['x']-bounds['width']/2)<.5,(bounds,guide)
                assert abs(guide['y']+guide['height']/2-bounds['y']-bounds['height']/2)<.5,(bounds,guide)
                assert page.locator('#keyboard-guide .notice-close').count()==0
                page.screenshot(path=str(out/f'expanded-ready-{width}x{height}.png'))
                page.evaluate("document.querySelector('#boot-cover').hidden=false; document.querySelector('#keyboard-prompt').hidden=true")
                page.locator('#demo-exit').click()
                assert page.locator('body').get_attribute('data-demo-expanded')=='false'
                assert page.locator('.laptop-art').is_visible()
                assert page.locator('#device > #demo-warning').is_visible()
                assert warning.count()==1
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
                page.wait_for_function("document.body.dataset.demoExpanded==='false'")
                assert page.locator('#device').is_hidden()
                assert page.locator('#phone-demo').is_visible()
                assert page.locator('body').get_attribute('data-demo-state') == 'running'
                assert page.locator('body').get_attribute('data-demo-expanded')=='false'
                assert len(pending) == 2, 'Resizing restarted the emulator'
                page.set_viewport_size({'width':width,'height':height})
                assert page.locator('#device').is_visible()
                assert page.locator('#phone-demo').is_hidden()
                assert len(pending) == 2, 'Returning to a wide layout restarted the emulator'
            if width>=768:
                # Layout-only preview of the ready prompt; no fabricated guest pixels.
                page.evaluate("document.querySelector('#boot-cover').hidden=true; document.querySelector('#keyboard-prompt').hidden=false")
                assert page.locator('#keyboard-wallet-hint').count()==0
                assert 'wallet' not in page.locator('#keyboard-guide').inner_text().lower()
                assert page.locator('.keyboard-ready').count()==0
                assert page.locator('#keyboard-instructions').inner_text()=='Click the screen to enable keyboard control'
                assert page.locator('#keyboard-navigation').inner_text()=='Use your keyboard, not the mouse.'
                assert page.locator('#keyboard-release').inner_text()=='Click outside the screen to release your keyboard.'
                assert page.locator('#keyboard-prompt').get_attribute('aria-label')=='Click the screen to enable keyboard control'
                for selector in ['#keyboard-prompt','#screen']:
                    assert 'keyboard-navigation' in page.locator(selector).get_attribute('aria-describedby').split()
                assert page.locator('#keyboard-guide kbd, #keyboard-reminder kbd').evaluate_all('''keys=>
                    keys.length===7 && keys.every(key=>getComputedStyle(key).color==='rgb(247, 147, 26)')''')
                assert page.locator('#keyboard-navigation, #keyboard-shortcuts, #keyboard-release, #keyboard-reminder > span').evaluate_all('''elements=>elements.every(element=>{
                    const style=getComputedStyle(element);
                    return style.color==='rgb(210, 213, 201)' && style.fontSize==='16px';
                })''')
                assert page.locator('#keyboard-prompt').evaluate('element=>getComputedStyle(element).backdropFilter')=='blur(1px)'
                assert page.locator('#keyboard-prompt').evaluate('element=>getComputedStyle(element).backgroundColor')=='rgba(0, 0, 0, 0.1)'
                assert 'monospace' in page.locator('#keyboard-guide').evaluate('element=>getComputedStyle(element).fontFamily')
                assert page.evaluate('''[...document.fonts].some(font=>font.family.includes('Terminus') && font.status==='loaded')''')
                notices=page.evaluate('''() => ['#keyboard-guide','#keyboard-reminder'].map(selector => {
                    const style=getComputedStyle(document.querySelector(selector));
                    return Object.fromEntries(['fontFamily','backgroundColor','borderTopColor','borderTopWidth','borderRadius','boxShadow','padding'].map(key=>[key,style[key]]));
                })''')
                assert notices[0].pop('padding')=='8px 14px',notices
                assert notices[1].pop('padding')=='8px 34px',notices
                assert notices[0]==notices[1],notices
                assert 'Terminus' in notices[0]['fontFamily'],notices
                assert notices[0]['backgroundColor']=='rgb(43, 46, 38)',notices
                assert notices[0]['borderTopColor']=='rgb(247, 147, 26)',notices
                assert notices[0]['borderRadius']=='2px',notices
                screen=page.locator('#screen-wrapper').bounding_box()
                guide=page.locator('#keyboard-guide').bounding_box()
                assert guide['width']<=440,guide
                assert page.locator('#keyboard-instructions').evaluate('element=>getComputedStyle(element).fontSize')=='18px'
                title=page.locator('#keyboard-instructions')
                assert title.bounding_box()['height']<=title.evaluate('element=>parseFloat(getComputedStyle(element).lineHeight)')+.5
                assert page.locator('#keyboard-shortcuts').evaluate('element=>getComputedStyle(element).fontSize')=='16px'
                navigation=page.locator('#keyboard-navigation').bounding_box()
                shortcuts=page.locator('#keyboard-shortcuts').bounding_box()
                assert title.bounding_box()['y']+title.bounding_box()['height']<=navigation['y']
                assert navigation['y']+navigation['height']<=shortcuts['y']
                release=page.locator('#keyboard-release')
                assert release.evaluate('element=>getComputedStyle(element).fontSize')=='16px'
                line_height=release.evaluate('element=>parseFloat(getComputedStyle(element).lineHeight)')
                assert line_height-.5<=release.bounding_box()['height']<=line_height*2+.5
                assert guide['x']>=screen['x'] and guide['y']>=screen['y'],(screen,guide)
                assert guide['x']+guide['width']<=screen['x']+screen['width'],(screen,guide)
                assert guide['y']+guide['height']<=screen['y']+screen['height'],(screen,guide)
                assert abs(guide['x']+guide['width']/2-screen['x']-screen['width']/2)<.5,(screen,guide)
                assert abs(guide['y']+guide['height']/2-screen['y']-screen['height']/2)<.5,(screen,guide)
                assert page.locator('#keyboard-guide').evaluate('element=>element.scrollWidth<=element.clientWidth')
                assert page.locator('#keyboard-guide .notice-close').count()==0
                page.screenshot(path=str(out/f'ready-{width}x{height}.png'))
                page.evaluate("document.querySelector('#keyboard-prompt').hidden=true; document.querySelector('#keyboard-reminder').hidden=false")
                reminder=page.locator('#keyboard-reminder').bounding_box()
                assert reminder['x']>=screen['x'] and reminder['y']>=screen['y'],(screen,reminder)
                assert reminder['x']+reminder['width']<=screen['x']+screen['width'],(screen,reminder)
                assert reminder['y']+reminder['height']<=screen['y']+screen['height'],(screen,reminder)
                assert abs(reminder['x']+reminder['width']/2-screen['x']-screen['width']/2)<.5,(screen,reminder)
                assert abs(reminder['y']+reminder['height']/2-screen['y']-screen['height']/2)<.5,(screen,reminder)
                assert page.locator('#keyboard-reminder').get_by_role('button',name='Dismiss keyboard reminder').count()==1
                assert page.locator('#keyboard-reminder > strong').inner_text()=='Use your keyboard, not the mouse'
                assert page.locator('#keyboard-reminder > strong').evaluate('element=>getComputedStyle(element).fontSize')=='18px'
                assert page.locator('#keyboard-reminder > span').evaluate_all('elements=>elements.every(element=>getComputedStyle(element).fontSize==="16px")')
                assert page.locator('#keyboard-reminder').evaluate('element=>element.scrollWidth<=element.clientWidth')
                check_notice_close(page,'#keyboard-reminder')
                veil=page.locator('#screen-wrapper').evaluate('''element => {
                    const style=getComputedStyle(element,'::after');
                    return {background:style.backgroundColor,pointerEvents:style.pointerEvents,
                        content:style.content,blur:style.backdropFilter};
                }''')
                assert veil=={'background':'rgba(0, 0, 0, 0.1)','pointerEvents':'none','content':'""','blur':'blur(1px)'},veil
                page.wait_for_timeout(200)
                page.screenshot(path=str(out/f'keyboard-reminder-{width}x{height}.png'))
                page.emulate_media(reduced_motion='reduce')
                assert page.locator('#keyboard-reminder').evaluate('element=>element.getAnimations().length')==0
                assert page.locator('#keyboard-reminder').evaluate('element=>getComputedStyle(element).transitionDuration')=='0s'
                page.emulate_media(reduced_motion='no-preference')
                page.evaluate("document.querySelector('#boot-cover').hidden=false; document.querySelector('#keyboard-reminder').hidden=true")
                assert page.locator('#screen-wrapper').evaluate("element=>getComputedStyle(element,'::after').content")=='none'
                # Preview only the browser-owned request card; never request a camera.
                page.evaluate("document.querySelector('#boot-cover').hidden=true; document.querySelector('#camera-request').hidden=false")
                check_demo_modal(page,'.camera-card')
                assert page.locator('#camera-request').evaluate('element=>getComputedStyle(element).backdropFilter')=='blur(1px)'
                assert page.locator('#camera-request').evaluate('element=>getComputedStyle(element).backgroundColor')=='rgba(0, 0, 0, 0.1)'
                camera=page.locator('.camera-card').bounding_box()
                assert camera['x']>=screen['x'] and camera['x']+camera['width']<=screen['x']+screen['width'],(screen,camera)
                assert camera['y']>=screen['y'] and camera['y']+camera['height']<=screen['y']+screen['height'],(screen,camera)
                assert page.locator('.camera-card').evaluate('element=>element.scrollHeight<=element.clientHeight && element.scrollWidth<=element.clientWidth')
                page.screenshot(path=str(out/f'camera-request-{width}x{height}.png'))
                if (width,height) in [(1366,768),(1024,600),(768,501)]:
                    page.evaluate('''() => {
                        document.querySelector('#camera-request-title').textContent='Camera unavailable';
                        document.querySelector('#camera-request-message').textContent='Camera permission denied. Allow access in your browser and system settings, then try again.';
                        document.querySelector('#camera-fallback').hidden=false;
                        document.querySelector('#camera-enable').textContent='Try again';
                    }''')
                    assert page.locator('.camera-card').evaluate('element=>element.scrollHeight<=element.clientHeight && element.scrollWidth<=element.clientWidth')
                    page.screenshot(path=str(out/f'camera-unavailable-{width}x{height}.png'))
                page.evaluate("document.querySelector('#camera-request').hidden=true; document.querySelector('#boot-cover').hidden=false")
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
            if status==404: page.locator('#expand-demo').click()
            page.locator('#boot-diagnostics').click()
            assert page.locator('#about-dialog').is_visible()
            assert message in page.locator('#log').inner_text()
            check_demo_modal(page,'#about-dialog')
            assert page.locator('#about-dialog').evaluate("element=>getComputedStyle(element,'::backdrop').backdropFilter")=='blur(1px)'
            assert page.locator('#about-dialog').evaluate("element=>getComputedStyle(element,'::backdrop').backgroundColor")=='rgba(0, 0, 0, 0.1)'
            assert page.locator('#about-dialog').evaluate('element=>element.scrollWidth<=element.clientWidth')
            page.screenshot(path=str(out/f'diagnostics-{status}.png'))
            page.keyboard.press('Escape')
            assert page.locator('#about-dialog').is_hidden()
            if status==404: page.keyboard.press('F8')
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
    print('PASS: keyboard, camera and diagnostics dialogs share terminal styling and a light 1px backdrop blur')
    print('PASS: natural page flow reveals details on tall screens; power button replaces the demo toolbar')
    print('PASS: expanded display fits laptop/tablet layouts; Back/F8 exits, Esc does not and no guest is restarted')
    print('PASS: image failures retain in-screen diagnostics and recovery without a permanent About button')
    print('PASS: dismissible keyboard reminder fits normal and expanded displays and respects reduced motion')
    print('PASS: four renumbered details blocks retain the USB/RAM explanation beside the security guide, stacking on phones')
    print('PASS: a single demo-funds warning aligns with the monitor, stays clear of controls and remains visible in expanded mode')
    browser.close()
