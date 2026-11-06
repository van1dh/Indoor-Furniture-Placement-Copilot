// Download a layout as JSON, or its floor plan as a PNG image.

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function layoutFilename(layout, extension) {
  return `layout-${layout.preset}-${layout.seed ?? 'edited'}.${extension}`;
}

export function downloadJson(layout) {
  const blob = new Blob([JSON.stringify(layout, null, 2)], { type: 'application/json' });
  download(blob, layoutFilename(layout, 'json'));
}

// The floor plan is styled from CSS, which an SVG drawn as an image cannot see, so copy the styles inline.
const STYLE_PROPERTIES = [
  'fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-linecap', 'opacity',
  'font-family', 'font-size', 'font-weight', 'text-anchor', 'dominant-baseline',
];

export function standaloneSvg(svg, pixelsPerFoot) {
  const copy = svg.cloneNode(true);
  const sources = [svg, ...svg.querySelectorAll('*')];
  const targets = [copy, ...copy.querySelectorAll('*')];
  sources.forEach((source, i) => {
    const style = getComputedStyle(source);
    const inline = STYLE_PROPERTIES.map((name) => [name, style.getPropertyValue(name)]).filter(([, v]) => v);
    targets[i].setAttribute('style', inline.map(([name, value]) => `${name}:${value}`).join(';'));
  });
  const { width, height } = svg.viewBox.baseVal;
  copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  copy.setAttribute('width', Math.round(width * pixelsPerFoot));
  copy.setAttribute('height', Math.round(height * pixelsPerFoot));
  return new XMLSerializer().serializeToString(copy);
}

export async function downloadPng(svg, layout, pixelsPerFoot = 48) {
  const markup = standaloneSvg(svg, pixelsPerFoot);
  const image = new Image();
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`;
  await image.decode();
  const canvas = document.createElement('canvas');
  canvas.width = image.width;
  canvas.height = image.height;
  const context = canvas.getContext('2d');
  context.fillStyle = '#fff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  download(blob, layoutFilename(layout, 'png'));
}
