"""Check website loading-bar visuals with downloads held pending, without a VM.

Requires Python Playwright and Chromium. Sample progress is set only in this
test page; real download progress and readiness are checked by browser-site-boot.
"""
import argparse
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
parser.add_argument('--url',default='http://127.0.0.1:4173/site/')
parser.add_argument('--chromium')
args=parser.parse_args()
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.chromium,headless=True)
    page=browser.new_page(viewport={'width':1366,'height':768})
    errors,pending=[],[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/assets/site/thunderden.img',lambda route:pending.append(route))
    page.route('**/emulator/qemu-system-x86_64.wasm',lambda route:pending.append(route))

    def changing_pixels(scope,bar,fraction=1):
        shots=[]
        for timestamp in [300,1000]:
            page.locator(scope).evaluate('''(element,time) => {
                for (const animation of element.getAnimations({subtree:true})) {
                    animation.pause(); animation.currentTime=time;
                }
            }''',timestamp)
            shots.append(base64.b64encode(page.locator(bar).screenshot()).decode())
        return page.evaluate('''async ({shots,fraction}) => {
            const samples=[];
            for (const png of shots) {
                const image=new Image();image.src='data:image/png;base64,'+png;await image.decode();
                const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
                const context=canvas.getContext('2d');context.drawImage(image,0,0);
                samples.push(context.getImageData(0,0,image.width,image.height));
            }
            let fill=0,track=0;const [a,b]=samples;
            for (let x=3;x<a.width-3;x++) {
                const i=(Math.floor(a.height/2)*a.width+x)*4;
                if (a.data[i]!==b.data[i] || a.data[i+1]!==b.data[i+1] || a.data[i+2]!==b.data[i+2]) {
                    if (x<a.width*fraction-3) fill++;
                    else if (x>a.width*fraction+3) track++;
                }
            }
            return {fill,track};
        }''',{'shots':shots,'fraction':fraction})

    try:
        page.goto(args.url)
        page.wait_for_function("document.querySelector('#startup-wasm').dataset.state==='active'")
        page.evaluate('document.fonts.ready')
        assert page.locator('#startup li small').all_text_contents()==['Connecting…','Connecting…']
        assert page.locator('#image-progress').get_attribute('value')=='0'
        assert changing_pixels('#startup-image','#image-progress')['fill']>0
        page.screenshot(path=str(out/'connecting.png'))
        page.evaluate('''() => {
            for (const [name,value] of [['image',.6],['wasm',.72]]) {
                const row=document.querySelector('#startup-'+name);
                row.querySelector('progress').value=value;
                row.style.setProperty('--startup-progress',value*100+'%');
                row.querySelector('small').textContent=value*100+'%';
            }
        }''')
        changes=changing_pixels('#startup-image','#image-progress',.6)
        assert changes['fill']>0 and changes['track']==0,changes
        for width,height in [(1366,768),(1280,720),(1024,600),(800,600),(768,501)]:
            page.set_viewport_size({'width':width,'height':height})
            assert page.locator('.boot-card').evaluate('card=>card.scrollHeight<=card.clientHeight')
            for name in ['image','wasm']:
                bar=page.locator('#'+name+'-progress')
                assert bar.bounding_box()['height']==14
                label=page.locator('#startup-'+name+' label').bounding_box()
                detail=page.locator('#startup-'+name+' small').bounding_box()
                assert label['x']+label['width']<=detail['x']
            page.screenshot(path=str(out/f'progress-{width}x{height}.png'))
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('#startup-image').evaluate('row=>row.getAnimations({subtree:true}).length')==0
        assert changing_pixels('#startup-image','#image-progress',.6)=={'fill':0,'track':0}
        page.emulate_media(reduced_motion='no-preference')
        page.evaluate('''() => {
            for (const row of document.querySelectorAll('#startup li')) {
                row.dataset.state='done';row.querySelector('progress').value=1;
                row.style.setProperty('--startup-progress','100%');
                row.querySelector('small').textContent='✓ Ready';
            }
        }''')
        assert page.locator('#startup').evaluate('element=>element.getAnimations({subtree:true}).length')==0
        assert changing_pixels('#startup-image','#image-progress')=={'fill':0,'track':0}
        page.screenshot(path=str(out/'downloads-ready.png'))
        page.evaluate('''() => {
            document.querySelector('#startup').hidden=true;
            const boot=document.querySelector('#boot-progress');boot.hidden=false;
            boot.style.setProperty('--startup-progress','60%');
            document.querySelector('#boot-progress-bar').value=.6;
        }''')
        assert page.locator('#boot-progress-bar').bounding_box()['height']==14
        changes=changing_pixels('#boot-progress','#boot-progress-bar',.6)
        assert changes['fill']>0 and changes['track']==0,changes
        page.screenshot(path=str(out/'boot-estimate.png'))
        page.evaluate("document.querySelector('#boot-progress-bar').removeAttribute('value')")
        assert changing_pixels('#boot-progress','#boot-progress-bar')['fill']>0
        page.screenshot(path=str(out/'boot-waiting.png'))
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('#boot-progress').evaluate('element=>element.getAnimations({subtree:true}).length')==0
        assert changing_pixels('#boot-progress','#boot-progress-bar')=={'fill':0,'track':0}
        assert not errors,errors
        print('PASS: connecting activity, 14px bars and aligned percentages fit compact laptop and tablet layouts')
        print('PASS: shimmer changes only the measured fill; completed bars are solid and reduced motion is static')
        print('PASS: estimated boot and indeterminate waiting use the same thicker bars and motion preferences')
    finally:
        for route in pending:route.abort()
        page.unroute_all(behavior='wait')
        browser.close()
