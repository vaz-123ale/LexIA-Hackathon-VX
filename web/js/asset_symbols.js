// Pictogramas vetoriais próprios: mapa, legenda e lista usam a mesma imagem.
const drawings = {
  quadrado: '<path d="M3 19 8 7l4 5 3-8 6 15M3 19h18M7 15h4m3 0h5"/>',
  triangulo: '<path d="M3 19h18M5 19 8 5h8l3 14M10 6v12m4-12v12M2 11h4m12 0h4M2 15h3m14 0h3"/>',
  circulo: '<path d="m9 3 1 3h4l1-3 3 2-1 3 2 3h3v4h-3l-2 3 1 3-3 1-1-3h-4l-1 3-3-1 1-3-2-3H2v-4h3l2-3-1-3Z"/><circle cx="12" cy="12" r="3"/>',
  estrela: '<path d="M4 16v-3a8 8 0 0 1 16 0v3M9 5v7m6-7v7M2 16h20v4H2Z"/>',
  radiacao: '<circle cx="12" cy="12" r="2"/><path d="m10 8-3-5a10 10 0 0 1 10 0l-3 5M8 12H2a10 10 0 0 0 5 9l3-5m6-4h6a10 10 0 0 1-5 9l-3-5"/>',
  gota: '<path d="M12 2S4 11 4 15a8 8 0 0 0 16 0c0-4-8-13-8-13ZM8 15a4 4 0 0 0 4 4"/>',
  losango: '<path d="m14 2-9 12h6l-1 8 9-13h-6Z"/>',
  hexagono: '<path d="M3 21V9l6 3V7l6 3V3h5v18ZM7 16h1m4 0h1m4 0h1"/>'
};
export function assetSymbol(sym, x, y, r, color) {
  return '<g class="asset-symbol" transform="translate(' + x + ',' + y + ') scale(' + r / 12 + ')"><rect style="stroke:' + color + '" class="asset-symbol-bg" x="-14" y="-14" width="28" height="28" rx="8" fill="#fffdf8" stroke="' + color + '" stroke-width="2.2"/><g transform="translate(-10,-10) scale(.8333)" fill="none" stroke="' + color + '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + (drawings[sym] || drawings.circulo) + '</g></g>';
}
