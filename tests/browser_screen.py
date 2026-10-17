"""Capture original guest pixels for OCR, independently of the scene's CSS scale."""

import base64


def capture_guest(page, path):
    image = page.locator("#screen").evaluate("""screen => {
        const canvas = document.createElement('canvas');
        canvas.width = screen.width * 2;
        canvas.height = screen.height * 2;
        const context = canvas.getContext('2d');
        context.imageSmoothingEnabled = false;
        context.drawImage(screen, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/png').split(',')[1];
    }""")
    path.write_bytes(base64.b64decode(image))
