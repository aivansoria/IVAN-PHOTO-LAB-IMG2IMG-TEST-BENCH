# IVAN PHOTO LAB — IMG2IMG TEST BENCH

Minimal Perchance test bench for auditing the official `text-to-image-plugin` `referenceImage` contract.

## Source files

- `01_PERCHANCE_LEFT_PANEL.txt`: Perchance data/code panel.
- `02_PERCHANCE_HTML_PANEL.html`: complete HTML, CSS and JavaScript application.

## Current deployment

- Generator: https://perchance.org/waa87xzs7p
- Edit URL: https://perchance.org/waa87xzs7p#edit
- Current ownership: anonymous generator created before the Perchance account session was active.
- Privacy: not yet private because the anonymous generator does not appear in the authenticated account's generator list.

## Test protocol

Use only a synthetic image or an adult image with consent. Keep prompt, negative prompt, seed, resolution and guidance scale fixed. Run the matrix sequentially with:

- blur `0`
- blur `0.15`
- blur `0.50`
- blur `1.00`

Do not commit generated images or exported metadata containing image data URLs.

## Safety

The reference image is converted to a data URL in browser memory and sent to Perchance only when generation is explicitly started. No test generation has been executed as part of repository setup.
