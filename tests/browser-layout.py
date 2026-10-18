"""Check the laptop scene and in-screen loading at different viewport sizes.

Requires Python Playwright and Chromium, with the website running. Downloads are
held pending so the real boot cover can be inspected without starting a guest.
Viewport emulation is not validation of mobile browsers or touch input.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", default="http://127.0.0.1:4173")
parser.add_argument("--chromium")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True)
    page = browser.new_page()
    errors = []
    requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/assets/thunderden.img", lambda route: requests.append(route))
    page.route("**/emulator/qemu-system-x86_64.wasm", lambda route: requests.append(route))
    results = []

    def fits(rect, width, height):
        return rect["x"] >= -1 and rect["y"] >= -1 and rect["right"] <= width + 1 and rect["bottom"] <= height + 1

    try:
        for width, height in [(1920, 1080), (1440, 900), (1366, 768), (1280, 720),
                              (1024, 768), (800, 600), (390, 844), (360, 640), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            if not results:
                page.goto(args.url)
                page.wait_for_function("document.querySelector('#startup-image').dataset.state === 'active'")
                page.wait_for_function("document.querySelector('#startup-wasm').dataset.state === 'active'")
                initial = page.locator('#image-progress').evaluate("bar => ({determinate:bar.hasAttribute('value'), value:bar.value})")
                assert initial == {'determinate':True, 'value':0}, f'Image bar must stay empty while connecting: {initial}'
                page.evaluate("""() => {
                    document.querySelector('#startup-wasm .asset-size').textContent = ' · 11.3 MiB';
                    for (const [name,value] of [['image',.54],['wasm',.72]]) {
                        document.querySelector(`#${name}-progress`).value = value;
                        document.querySelector(`#startup-${name} small`).textContent = `${Math.round(value*100)}%`;
                    }
                }""")
            state = page.evaluate("""() => {
                const rect = selector => {
                    const r = document.querySelector(selector).getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom};
                };
                const card = document.querySelector('.boot-card');
                return {screen: rect('#screen'), device: rect('#device'), cover: rect('#boot-cover'),
                    title: rect('#boot-title'), imageProgress: rect('#image-progress'), wasmProgress: rect('#wasm-progress'),
                    titleFont: parseFloat(getComputedStyle(document.querySelector('#boot-title')).fontSize),
                    statsFont: parseFloat(getComputedStyle(document.querySelector('#startup small')).fontSize),
                    cardScroll: card.scrollHeight - card.clientHeight,
                    pageWidth: document.documentElement.scrollWidth,
                    art: getComputedStyle(document.querySelector('.laptop-art')).display};
            }""")
            assert fits(state["screen"], width, height), state
            assert state["screen"]["width"] >= 250 and state["screen"]["height"] >= 180, state
            assert state["pageWidth"] <= width, state
            assert state["titleFont"] >= 20, state
            assert page.locator('.boot-spinner').count() == 0
            if state["screen"]["height"] > 340:
                assert state["statsFont"] >= 14, state
            assert page.evaluate("window.scrollY") == 0
            assert page.locator("#boot-cover").is_visible()
            assert page.locator("#keyboard-prompt").is_hidden()
            assert page.locator("#boot-cover #keyboard-instructions").count() == 0
            assert page.locator(".hint").is_hidden()
            assert page.locator(".warning").is_visible()
            for name in ["title", "imageProgress", "wasmProgress"]:
                assert fits(state[name], width, height), state
                assert state[name]["bottom"] <= state["cover"]["bottom"], state
            if width > 700 and height > 560:
                assert fits(state["device"], width, height), state
                assert state["art"] != "none", state
                assert state["cardScroll"] <= 1, state
            page.screenshot(path=str(out / f"loading-{width}x{height}.png"))
            results.append({"viewport": [width, height], **state})

        assert len(requests) == 2, requests  # No click and no duplicate boot on resize.
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        assert page.locator("#camera-led").get_attribute("data-active") == "false"
        assert page.locator("#startup li").count() == 2
        assert page.title() == 'Thunder Den Demo'
        assert page.locator('.boot-mark').count() == 0
        assert page.locator('#boot-title').inner_text() == 'Loading Thunder Den…'
        assert page.locator('#startup-image label').inner_text() == 'Thunder Den image · 64 MiB'
        assert page.locator('#startup-wasm label').inner_text() == 'Browser x86-64 emulator · 11.3 MiB'
        # Boot copy must remain readable, with sentence-level adaptive wrapping.
        page.evaluate("""() => {
            document.querySelector('#startup').hidden = true;
            document.querySelector('#boot-title').textContent = 'Booting Thunder Den…';
            document.querySelector('#boot-estimate').hidden = false;
            document.querySelector('#boot-progress').hidden = false;
            document.querySelector('#boot-progress-bar').value = .6;
        }""")
        booting = []
        for loading in results:
            width, height = loading['viewport']
            page.set_viewport_size({'width':width, 'height':height})
            state = page.evaluate("""() => {
                const rect = selector => {
                    const r = document.querySelector(selector).getBoundingClientRect();
                    return {x:r.x, y:r.y, width:r.width, height:r.height, right:r.right, bottom:r.bottom};
                };
                const card = document.querySelector('.boot-card');
                return {device:rect('#device'), card:rect('.boot-card'), estimate:rect('#boot-estimate'),
                    progress:rect('#boot-progress-bar'),
                    first:rect('#boot-estimate span:first-child'), second:rect('#boot-estimate span:last-child'),
                    horizontalOverflow:card.scrollWidth-card.clientWidth,
                    messageFont:parseFloat(getComputedStyle(document.querySelector('#boot-message')).fontSize)};
            }""")
            for field in ['x','y','width','height']:
                assert abs(state['device'][field]-loading['device'][field]) < .5, state
            assert fits(state['card'], width, height), state
            assert state['horizontalOverflow'] <= 1 and state['messageFont'] >= 14, state
            assert page.locator('#boot-message').is_visible()
            assert page.locator('.boot-spinner').count() == 0
            assert page.locator('#boot-progress').is_visible()
            assert page.locator('#boot-progress').inner_text() == ''
            assert page.locator('#boot-progress-label').count() == 0
            assert page.locator('#boot-elapsed').count() == 0
            assert '%' not in page.locator('#boot-progress').inner_text()
            assert 'Bitcoin Core’s cryptography' in page.locator('#boot-message').inner_text()
            combined = state['first']['width'] + state['second']['width']
            if combined + 8 <= state['estimate']['width']:
                assert abs(state['first']['y']-state['second']['y']) < 1, state
            elif combined > state['estimate']['width']:
                assert state['second']['y'] >= state['first']['bottom']-1, state
            assert page.locator('#boot-estimate br').count() == 0
            page.screenshot(path=str(out/f'booting-{width}x{height}.png'))
            booting.append({'viewport':[width,height], **state})
        assert any(abs(row['first']['y']-row['second']['y']) < 1 for row in booting)
        assert any(row['second']['y'] >= row['first']['bottom']-1 for row in booting)
        # Exercise ready-card sizing without loading or starting a guest.
        page.evaluate("""() => {
            document.querySelector('#boot-cover').hidden = true;
            document.querySelector('#screen').dataset.ready = 'true';
            document.querySelector('#keyboard-prompt').hidden = false;
        }""")
        guides = []
        for width, height in [(1920, 1080), (1440, 900), (1366, 768), (1280, 720),
                              (1024, 768), (800, 600), (390, 844), (360, 640), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            state = page.evaluate("""() => {
                const rect = selector => {
                    const r = document.querySelector(selector).getBoundingClientRect();
                    return {x:r.x, y:r.y, width:r.width, height:r.height, right:r.right, bottom:r.bottom};
                };
                const prompt = document.querySelector('#keyboard-prompt');
                return {prompt:rect('#keyboard-prompt'), card:rect('#keyboard-guide'), device:rect('#device'), screen:rect('#screen'),
                    instructions:rect('#keyboard-instructions'), shortcuts:rect('#keyboard-shortcuts'),
                    overflow:prompt.scrollHeight - prompt.clientHeight,
                    guideFont:parseFloat(getComputedStyle(document.querySelector('#keyboard-instructions')).fontSize)};
            }""")
            for name in ["prompt", "card", "instructions", "shortcuts"]:
                assert fits(state[name], width, height), state
                assert state[name]["bottom"] <= state["prompt"]["bottom"], state
                assert state[name]["y"] >= state["prompt"]["y"], state
            assert state["overflow"] <= 1 and state["guideFont"] >= 13, state
            loading = next(row for row in results if row['viewport'] == [width, height])
            for name in ['device', 'screen']:
                for field in ['x', 'y', 'width', 'height']:
                    assert abs(state[name][field] - loading[name][field]) < .5, (name, field, loading[name], state[name])
            assert "Click outside" in page.locator("#keyboard-prompt").inner_text()
            assert 'capture keyboard input' in page.locator('#keyboard-prompt').inner_text()
            assert page.locator("#keyboard-shortcuts").is_visible()
            assert page.locator(".warning").is_visible()
            page.screenshot(path=str(out / f"keyboard-guide-{width}x{height}.png"))
            guides.append({"viewport":[width,height], **state})
        # Camera guidance and its actions must remain reachable on small screens.
        page.evaluate("""() => {
            document.querySelector('#keyboard-prompt').hidden = true;
            document.querySelector('#camera-request').hidden = false;
        }""")
        cameras = []
        for problem in [False, True]:
            page.evaluate("""problem => {
                document.querySelector('#camera-request-title').textContent = problem ? 'Camera unavailable' : 'Camera access is needed';
                document.querySelector('#camera-request-message').textContent = problem
                    ? 'Camera permission denied. Allow access in your browser and system settings, then try again.'
                    : 'The virtual device needs your camera.';
                document.querySelector('#camera-fallback').hidden = !problem;
            }""", problem)
            for width, height in [(1920, 1080), (1440, 900), (1366, 768), (1280, 720),
                                  (1024, 768), (800, 600), (390, 844), (360, 640), (844, 390)]:
                page.set_viewport_size({"width": width, "height": height})
                page.locator('#camera-cancel').focus()
                page.locator('#camera-cancel').scroll_into_view_if_needed()
                state = page.evaluate("""() => {
                    const rect = selector => {
                        const r = document.querySelector(selector).getBoundingClientRect();
                        return {x:r.x, y:r.y, width:r.width, height:r.height, right:r.right, bottom:r.bottom};
                    };
                    const card = document.querySelector('.camera-card');
                    return {prompt:rect('#camera-request'), card:rect('.camera-card'), device:rect('#device'), screen:rect('#screen'),
                        enable:rect('#camera-enable'), cancel:rect('#camera-cancel'),
                        horizontalOverflow:card.scrollWidth - card.clientWidth,
                        pageWidth:document.documentElement.scrollWidth};
                }""")
                for name in ['prompt', 'card', 'enable', 'cancel']:
                    assert fits(state[name], width, height), state
                    assert state[name]['bottom'] <= state['prompt']['bottom'], state
                    assert state[name]['y'] >= state['prompt']['y'], state
                assert state['horizontalOverflow'] <= 1 and state['pageWidth'] <= width, state
                loading = next(row for row in results if row['viewport'] == [width, height])
                for name in ['device', 'screen']:
                    for field in ['x', 'y', 'width', 'height']:
                        assert abs(state[name][field] - loading[name][field]) < .5, (name, field, loading[name], state[name])
                assert page.locator('.hint').is_hidden()
                assert page.evaluate('window.scrollY') == 0
                page.screenshot(path=str(out / f"camera-{'error' if problem else 'needed'}-{width}x{height}.png"))
                cameras.append({'viewport':[width,height], 'error':problem, **state})
        page.evaluate("document.querySelector('#camera-request').hidden = true")
        # Inspect live SVG text metrics: every legend must fit its own keycap.
        artwork = page.evaluate("""async () => {
            const source = await (await fetch('./laptop.svg')).text();
            const svg = new DOMParser().parseFromString(source, 'image/svg+xml').documentElement;
            const brandSource = await (await fetch('./brand/thunderden-horizontal-paper.svg')).text();
            const brand = new DOMParser().parseFromString(brandSource, 'image/svg+xml');
            svg.style.cssText = 'position:fixed;left:-2000px;width:1120px;height:830px;opacity:0;pointer-events:none';
            document.body.append(svg);
            try {
                const keys = [...svg.querySelectorAll('.key')];
                const overflow = keys.filter(key => {
                    const cap = key.querySelector('use');
                    const box = cap.getBBox();
                    const matrix = cap.transform.baseVal.consolidate().matrix;
                    const left = new DOMPoint(box.x, box.y).matrixTransform(matrix);
                    const right = new DOMPoint(box.x + box.width, box.y + box.height).matrixTransform(matrix);
                    const text = key.querySelector('text').getBBox();
                    return text.x < left.x || text.x + text.width > right.x
                        || text.y < left.y || text.y + text.height > right.y;
                }).map(key => key.textContent);
                const power = svg.querySelector('#power-button').getBoundingClientRect();
                const quad = selector => {
                    const path = svg.querySelector(selector);
                    const coordinates = path.getAttribute('d').match(/-?[\\d.]+/g).map(Number);
                    return coordinates.flatMap((value,index) => {
                        if (index % 2) return [];
                        const point = new DOMPoint(value,coordinates[index+1]).matrixTransform(path.getCTM());
                        return [point.x,point.y];
                    });
                };
                const pad = quad('#trackpad-surface');
                const well = quad('#keyboard-well');
                const vanishingPoint = points => {
                    const [x,y,qx,qy,fx,fy,lx,ly] = points;
                    const rx=lx-x, ry=ly-y, sx=fx-qx, sy=fy-qy;
                    const t=((qx-x)*sy-(qy-y)*sx)/(rx*sy-ry*sx);
                    return [x+t*rx,y+t*ry];
                };
                const deckPath = svg.querySelector('#laptop-deck');
                const outline = deckPath.getAttribute('d').match(/-?[\\d.]+/g).map(Number);
                const [x,y,width,dx,dy] = outline;
                const chassis = [x,y,x+width,y,x+width+dx,y+dy,
                    x-outline.at(-2),y-outline.at(-1)];
                const chassisPoint = vanishingPoint(chassis);
                const maxKeyAxisError = Math.max(...keys.map(key => {
                    const matrix = key.getCTM();
                    return Math.abs(matrix.e+(chassisPoint[1]-matrix.f)*matrix.c/matrix.d-chassisPoint[0]);
                }));
                const chassisWidthAt = y => width + (dx+outline.at(-2))*(y-chassis[1])/dy;
                const buttons = svg.querySelector('#trackpad-buttons').getBBox();
                const deck = deckPath.getBBox();
                const hingeBar = svg.querySelector('#hinge-bar');
                const hinge = hingeBar.getBBox();
                const lid = svg.querySelector('rect[fill="url(#lid)"]').getBBox();
                const hingeBehindDeck = Boolean(svg.querySelector('#hinge').compareDocumentPosition(
                    deckPath) & Node.DOCUMENT_POSITION_FOLLOWING);
                const logo = svg.querySelector('#usb-logo');
                const logoMatrix = logo.transform.baseVal.consolidate().matrix;
                const connector = quad('#usb-connector-top');
                const port = quad('#usb-port');
                const portRecessed = port.every((value,index) => index % 2
                    || value < chassis[2]+dx*(port[index+1]-chassis[3])/dy-.3);
                const usbBehindDeck = Boolean(svg.querySelector('#usb-drive').compareDocumentPosition(
                    svg.querySelector('#laptop-deck')) & Node.DOCUMENT_POSITION_FOLLOWING);
                const url = URL.createObjectURL(new Blob([source], {type: 'image/svg+xml'}));
                try {
                    const image = new Image();
                    image.src = url;
                    await image.decode();
                    const canvas = document.createElement('canvas');
                    canvas.width = 1120; canvas.height = 830;
                    const context = canvas.getContext('2d');
                    context.drawImage(image, 0, 0);
                    const pixel = (x, y) => [...context.getImageData(x, y, 1, 1).data].slice(0, 3);
                    let logoInk = 0;
                    for (let y=662; y<673; y++) for (let x=1040; x<1081; x++) {
                        if (pixel(x,y).every(channel => channel > 210)) logoInk++;
                    }
                    return {keys: keys.length, overflow, maxKeyAxisError, power: {width: power.width, height: power.height},
                        hinge: {top:hinge.y-Number(hingeBar.getAttribute('stroke-width'))/2,
                            height:hinge.height, bottom:hinge.y+hinge.height, lidBottom:lid.y+lid.height,
                            visibleHeight:chassis[1]-hinge.y, deckTop:chassis[1], behindDeck:hingeBehindDeck,
                            formerBezelOverlap:pixel(238,610), seam:pixel(500,615)},
                        trackpad: {height:pad[5]-pad[1], width:pad[4]-pad[6],
                            widthFraction:(pad[2]-pad[0])/chassisWidthAt(pad[1]),
                            vanishingPoint:vanishingPoint(pad), keyboardVanishingPoint:vanishingPoint(well),
                            chassisVanishingPoint:vanishingPoint(chassis),
                            buttonVanishingPoints:[...svg.querySelectorAll('#trackpad-buttons path')].map(
                                (_,index) => vanishingPoint(quad(`#trackpad-buttons path:nth-child(${index+1})`))),
                            topGap:buttons.y-well[5], frontGap:deck.y+deck.height-pad[5],
                            buttonGap:pad[1]-buttons.y-buttons.height},
                        usbBehindDeck, coveredConnector: pixel(1021, 666), exposedConnector: pixel(1028, 670),
                        portRecessed, portProtrusionAlpha:context.getImageData(1023,658,1,1).data[3],
                        connectorHoles:[pixel(1025,665),pixel(1029,673)],
                        connectorSide:pixel(1031, 680), connectorTopLength:connector[2]-connector[0],
                        connectorSideHeight:svg.querySelector('#usb-connector-side').getBBox().height,
                        logo: {officialPath:svg.querySelector('#thunderden-mark').getAttribute('d') === brand.querySelector('path').getAttribute('d'),
                            bounds:logo.getBoundingClientRect().toJSON(), badge:svg.querySelector('#usb-badge').getBoundingClientRect().toJSON(),
                            skew:logoMatrix.c/logoMatrix.d, foreshortening:logoMatrix.d/logoMatrix.a,
                            inkPixels:logoInk, textLabels:svg.querySelectorAll('#usb-drive text').length}};
                } finally { URL.revokeObjectURL(url); }
            } finally { svg.remove(); }
        }""")
        assert artwork["keys"] == 78 and not artwork["overflow"], artwork
        assert artwork['maxKeyAxisError'] < .5, artwork
        assert 0 < artwork["power"]["height"] < artwork["power"]["width"] * .55, artwork
        hinge = artwork['hinge']
        assert hinge['top'] >= hinge['lidBottom'] and hinge['height'] <= 8, hinge
        assert hinge['behindDeck'] and 0 < hinge['visibleHeight'] <= 4 and hinge['bottom'] > hinge['deckTop'], hinge
        assert max(hinge['formerBezelOverlap']) < 40 and max(hinge['seam']) < 30, hinge
        assert artwork["usbBehindDeck"] and max(artwork["coveredConnector"]) < 90, artwork
        assert min(artwork["exposedConnector"]) > 100, artwork
        pad = artwork['trackpad']
        assert .32 < pad['widthFraction'] < .35 and pad['height'] >= 37, pad
        for point in [pad['vanishingPoint'], pad['keyboardVanishingPoint'], *pad['buttonVanishingPoints']]:
            assert all(abs(actual-expected) < .75 for actual,expected in zip(point,pad['chassisVanishingPoint'])), pad
        assert .8 < pad['topGap']/pad['frontGap'] < 1.2 and 2 <= pad['buttonGap'] <= 5, pad
        assert artwork['connectorTopLength'] < 15 and artwork['connectorSideHeight'] >= 3.5, artwork
        assert max(artwork['connectorSide']) < min(artwork['exposedConnector'])-25, artwork
        assert artwork['portRecessed'] and artwork['portProtrusionAlpha'] == 0, artwork
        assert all(min(hole) > 90 for hole in artwork['connectorHoles']), artwork
        logo = artwork['logo']
        assert logo['officialPath'] and logo['textLabels'] == 0 and logo['inkPixels'] > 60, logo
        assert .3 < logo['skew'] < .45 and .35 < logo['foreshortening'] < .5, logo
        assert logo['bounds']['x'] > logo['badge']['x'] and logo['bounds']['right'] < logo['badge']['right'], logo
        assert logo['bounds']['y'] > logo['badge']['y'] and logo['bounds']['bottom'] < logo['badge']['bottom'], logo
        page.locator("#about").click()
        assert page.locator("#about-dialog").is_visible()
        page.keyboard.press("Escape")
        assert page.locator("#about-dialog").is_hidden()
        assert not errors, errors
        (out / "layout.json").write_text(json.dumps(results, indent=2))
        (out / "booting.json").write_text(json.dumps(booting, indent=2))
        (out / "keyboard-guide.json").write_text(json.dumps(guides, indent=2))
        (out / "camera-guide.json").write_text(json.dumps(cameras, indent=2))
        (out / 'artwork.json').write_text(json.dumps(artwork, indent=2))
        print("PASS: readable loading UI and initial screen/laptop fit across nine Chromium viewports; all 78 key legends fit their keycaps")
        print("PASS: power button follows the deck plane; chassis covers the inserted connector while exposed metal remains visible")
        print('PASS: slim dark hinge sits below the lid bezel and behind the deck, without a raised bar on the bezel')
        print('PASS: chassis, keyboard, buttons and one-third-width trackpad share a vanishing point; USB socket stays recessed with subtle connector details and the exact official icon')
        print("PASS: keyboard guidance is absent during loading; full ready card and shortcuts fit all nine viewports")
        print("PASS: camera guidance/error cards stay within the display; Enable/Cancel remain reachable across nine viewports")
        print("PASS: laptop and screen geometry stay unchanged between loading, ready and camera guidance")
        print("PASS: revised loading/boot copy is readable; time-hint sentences share a line when they fit and wrap when needed")
    finally:
        for route in requests:
            route.abort()
        browser.close()
