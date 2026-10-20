"""Real guest signing round trip with public demo data and synthetic camera video.

Requires Python Playwright, Chromium and tesseract. Uses no physical camera.
The phone scans original guest pixels, not a fabricated signed-response fixture.
"""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
parser.add_argument('--url',default='http://127.0.0.1:4173/site/')
parser.add_argument('--chromium')
parser.add_argument('--expanded',action='store_true',help='Run the guest walkthrough in the expanded display')
parser.add_argument('--check-animation',action='store_true',help='Capture eight seconds of signed QR animation and check every displayed frame')
args=parser.parse_args()
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=True)

# Feed test frames through an actual MediaStream. Production camera/decoder code
# remains unchanged. The browser-side hooks exist only in this test context.
camera_script="""(() => {
  const canvas=document.createElement('canvas'); canvas.width=640; canvas.height=480;
  const context=canvas.getContext('2d');
  context.fillStyle='white';context.fillRect(0,0,640,480);
  window.cameraCalls=0; window.cameraTracks=[]; window.cameraMode='allow';
  navigator.mediaDevices.getUserMedia=async () => {
    cameraCalls++;
    if(cameraMode==='deny') throw new DOMException('Denied','NotAllowedError');
    const stream=canvas.captureStream(10);
    cameraTracks.push(...stream.getTracks());
    return stream;
  };
  window.setCameraImage=async source=>{
    const image=new Image();image.src=source;await image.decode();
    context.fillStyle='white';context.fillRect(0,0,640,480);
    context.imageSmoothingEnabled=false;
    context.drawImage(image,(640-image.width)/2,(480-image.height)/2);
  };
  let animation;
  window.setCameraQr=async ({texts,size})=>{
    clearInterval(animation);
    const {renderQr}=await import(new URL('./site/qr.js',document.baseURI));
    const images=[];
    for(const text of texts){
      const element=document.createElement('div');renderQr(element,text,'Public test QR');
      const image=new Image();
      image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(element.innerHTML);
      await image.decode();images.push(image);
    }
    let index=0;
    const draw=()=>{
      context.fillStyle='white';context.fillRect(0,0,640,480);
      context.imageSmoothingEnabled=false;
      context.drawImage(images[index++%images.length],(640-size)/2,(480-size)/2,size,size);
    };
    draw();animation=setInterval(draw,250);
  };
})();"""

with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.chromium,headless=True)
    context=browser.new_context(viewport={'width':1280,'height':800})
    context.add_init_script(camera_script)
    if args.check_animation:
        context.add_init_script("""(() => {
            const put=CanvasRenderingContext2D.prototype.putImageData;
            window.qrFrames=[];window.recordQrFrames=false;
            CanvasRenderingContext2D.prototype.putImageData=function(image,...args) {
                const result=put.call(this,image,...args);
                if(this.canvas.id!=='screen' || !recordQrFrames) return result;
                let white=0,black=0,background=0,caption=2166136261;
                for(let i=0;i<image.data.length;i+=4) {
                    const r=image.data[i],g=image.data[i+1],b=image.data[i+2];
                    if(r===255 && g===255 && b===255) white++;
                    if(r===0 && g===0 && b===0) black++;
                    if(r===25 && g===26 && b===24) background++;
                    if(i>=image.width*(image.height-56)*4) {
                        caption=Math.imul(caption^r,16777619);
                        caption=Math.imul(caption^g,16777619);
                        caption=Math.imul(caption^b,16777619);
                    }
                }
                qrFrames.push({t:performance.now(),white,black,background,caption:caption>>>0,
                    png:this.canvas.toDataURL('image/png').split(',')[1]});
                return result;
            };
        })();""")
    page=context.new_page()
    phone=context.new_page()
    phone.set_viewport_size({'width':320,'height':460})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    phone.on('pageerror',lambda error:errors.append(str(error)))

    def guest_text():
        capture_guest(page,out/'guest.png')
        text=subprocess.run(['tesseract',str(out/'guest.png'),'stdout','--psm','11'],capture_output=True,text=True,check=True).stdout
        (out/'guest.txt').write_text(text)
        return re.sub(r'\s+',' ',text).casefold()

    def wait_guest(label,timeout=60):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            assert not errors,errors
            assert not page.locator('#status').inner_text().startswith('Stopped:'),page.locator('#status').inner_text()
            if page.locator('#camera-enable').is_visible(): page.locator('#camera-enable').click()
            if label.casefold() in guest_text(): return
            page.wait_for_timeout(300)
        raise TimeoutError(label)

    try:
        phone.goto(urljoin(args.url,'wallet-mockup/'))
        phone.wait_for_function("document.body.dataset.step==='seed'")
        assert phone.evaluate('cameraCalls')==0
        phone.screenshot(path=str(out/'phone-paper.png'),full_page=True)
        seed=phone.evaluate("import(new URL('./site/wallet-mockup/fixture.js',document.baseURI)).then(m=>m.FIXTURE.seedQr)")
        seed_size=phone.locator('#seed-qr').bounding_box()['width']
        page.goto(args.url)
        page.wait_for_function("document.querySelector('#screen').dataset.ready==='true'",timeout=90000)
        if args.expanded:
            page.locator('#expand-demo').click()
            assert page.locator('body').get_attribute('data-demo-expanded')=='true'
        page.evaluate('setCameraQr',{'texts':[seed],'size':seed_size})
        assert page.evaluate('cameraCalls')==0
        page.locator('#keyboard-prompt').click()
        page.keyboard.press('1')
        wait_guest('Start a session')
        page.keyboard.press('1')
        wait_guest('Recovery words scanned')
        page.locator('#screen').click()
        page.keyboard.press('Enter')
        wait_guest('Wallet passphrase')
        page.keyboard.press('Enter')
        wait_guest('What would you like to do?')

        phone.locator('#seed-next').click()
        assert phone.locator('#payment-amount').inner_text()=='20,000 sats'
        assert phone.evaluate('cameraCalls')==0
        phone.screenshot(path=str(out/'phone-payment.png'),full_page=True)
        frames=phone.evaluate("import(new URL('./site/wallet-mockup/exchange.js',document.baseURI)).then(m=>m.paymentFrames())")
        payment_size=phone.locator('#payment-qr').bounding_box()['width']
        page.evaluate('setCameraQr',{'texts':frames,'size':payment_size})
        page.locator('#screen').click()
        page.keyboard.press('1')
        wait_guest('Review transaction')
        for _ in range(6):
            if 'type sign then enter' in guest_text(): break
            page.keyboard.press('Enter')
            page.wait_for_timeout(300)
        else: raise AssertionError('No signing confirmation')
        for letter in 'SIGN': page.keyboard.press('Shift+'+letter)
        page.keyboard.press('Enter')
        wait_guest('Esc: Finish')
        page.screenshot(path=str(out/'thunderden-signed-qr.png'))
        animation=None
        if args.check_animation:
            page.evaluate('recordQrFrames=true')
            page.wait_for_timeout(8000)
            page.evaluate('recordQrFrames=false')
            animation=page.evaluate(r"""async () => {
                const {decodeQr}=await import(new URL('./vendor/wallet.js',document.baseURI));
                const canvas=document.createElement('canvas');canvas.width=640;canvas.height=400;
                const context=canvas.getContext('2d',{willReadFrequently:true});
                const codes=[];
                for(const frame of qrFrames) {
                    const image=new Image();image.src='data:image/png;base64,'+frame.png;await image.decode();
                    context.drawImage(image,0,0);
                    const code=decodeQr(context.getImageData(0,0,640,400).data,640,400,{inversionAttempts:'dontInvert'});
                    if(code && /^ur:crypto-psbt\//i.test(code.data)) codes.push(code.data);
                }
                return {samples:qrFrames.length,decoded:codes.length,distinctQrPayloads:new Set(codes).size};
            }""")
            observed=page.evaluate('qrFrames')
            for index,frame in enumerate(observed):
                (out/f'qr-frame-{index:03}.png').write_bytes(base64.b64decode(frame.pop('png')))
            (out/'qr-frames.json').write_text(json.dumps(observed,indent=2))
            (out/'animation.json').write_text(json.dumps(animation,indent=2))
            assert observed and all(frame['white']>0 and frame['black']>0 for frame in observed),'Blank/white QR redraw frame'
            assert len({frame['background'] for frame in observed})==1,'Background changed between QR frames'
            assert len({frame['white']+frame['black'] for frame in observed})==1,'Incomplete QR rectangle'
            assert len({frame['caption'] for frame in observed})==1,'Captions changed between QR frames'
            assert animation['decoded']==animation['samples'],animation
            assert animation['distinctQrPayloads']>=2,animation

        # Permission failure is recoverable and never marks the payment verified.
        phone.evaluate("cameraMode='deny'")
        phone.locator('#scan-next').click()
        phone.wait_for_function("!document.querySelector('#scan-retry').hidden")
        assert phone.locator('#done-step').is_hidden()
        assert 'Allow camera' in phone.locator('#scan-status').inner_text()
        phone.evaluate("cameraMode='allow'")
        phone.locator('#scan-retry').click()
        end=time.monotonic()+30
        while time.monotonic()<end and phone.locator('#done-step').is_hidden():
            source=page.locator('#screen').evaluate("screen=>screen.toDataURL('image/png')")
            phone.evaluate('setCameraImage',source)
            phone.wait_for_timeout(150)
        assert phone.locator('#done-step').is_visible(),phone.locator('#scan-status').inner_text()
        phone.wait_for_function("document.querySelector('#reply-video').srcObject===null")
        assert phone.evaluate("cameraTracks.every(track=>track.readyState==='ended')")
        assert phone.locator('#done-title').inner_text()=='Signature verified'
        phone.screenshot(path=str(out/'phone-verified.png'),full_page=True)
        assert not errors,errors
        (out/'checks.json').write_text(json.dumps({'real_guest_signing':True,'network':'Bitcoin mainnet',
            'phone_viewport':[320,460],'displayed_qr_sizes':[seed_size,payment_size],
            'expanded':args.expanded,'animation':animation,
            'phone_verified_actual_guest_qr':True,'phone_camera_stopped':True,'physical_devices_tested':False},indent=2))
        print('PASS: public paper SeedQR -> unchanged mainnet guest -> synthetic demo payment -> real signature')
        print('PASS: phone camera decodes the actual guest framebuffer and verifies the signed payment')
        print('PASS: guest scans the seed and payment at their compact phone display sizes')
        print('PASS: no early camera requests; recoverable denial, no premature success and capture stopped after verification')
        if animation:
            print(f"PASS: {animation['samples']} displayed QR frames decode, with no blank/white stages or caption changes; {animation['distinctQrPayloads']} distinct payloads")
    except Exception:
        page.screenshot(path=str(out/'guest-failure.png'))
        phone.screenshot(path=str(out/'phone-failure.png'),full_page=True)
        print(json.dumps({'guest':page.locator('#status').inner_text(),'errors':errors},indent=2))
        raise
    finally:
        browser.close()
