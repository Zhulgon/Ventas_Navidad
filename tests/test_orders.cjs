const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function storefront(clipboard) {
  const field = { value: 'Pedido de prueba', focused: false, selected: false,
    focus() { this.focused = true; }, select() { this.selected = true; } };
  const status = { textContent: '' };
  const elements = { '#app': {}, '#dialog': { open: true }, '#notice': {}, '#catalog-results': {}, '.skip': { addEventListener() {} },
    '#instagram-order-text': field, '#instagram-order-status': status };
  const context = vm.createContext({
    document: { querySelector: selector => elements[selector], addEventListener() {} },
    window: { addEventListener() {} }, location: { pathname: '/catalogo' },
    navigator: { clipboard }, localStorage: { getItem: () => null },
    fetch: () => new Promise(() => {}), setTimeout, clearTimeout,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
  return { context, field, status, elements };
}

const blue = { sku: 'TM-019', name: 'Conjunto de figuras de Papá Noel en azul y blanco',
  category: 'Figuras', price: 45000, pieces: 2, stock: 0, published: true,
  availability: { status: 'in_production', incoming: 3, expected_on: '2026-11-29' } };

test('los juegos en elaboración se consultan sin entrar en el carrito como disponibles', () => {
  const { context, elements } = storefront();
  context.blue = blue;
  vm.runInContext('data = { products: [blue] }; selection.set(blue.sku, 2); updateCatalog(); detail(blue)', context);
  assert.equal(vm.runInContext('selectedItems().length', context), 0);
  assert.match(elements['#catalog-results'].innerHTML, /En elaboración/);
  assert.match(elements['#catalog-results'].innerHTML, /3 juegos en elaboración/);
  assert.match(elements['#dialog'].innerHTML, /Sin existencias para entrega inmediata/);
  assert.match(elements['#dialog'].innerHTML, /Consultar por Instagram/);
  assert.doesNotMatch(elements['#dialog'].innerHTML, /data-act="select"/);
  const text = vm.runInContext('inquiryText(blue)', context);
  assert.match(text, /TM-019/);
  assert.match(text, /29 de noviembre de 2026/);
  assert.match(text, /confirmar la fecha de entrega/);
});

test('al recibir el producto se usa el stock real y se permite agregarlo a la selección', () => {
  const { context, elements } = storefront();
  context.blue = { ...blue, stock: 3 };
  vm.runInContext('data = { products: [blue] }; detail(blue)', context);
  assert.match(elements['#dialog'].innerHTML, /3 juegos disponibles/);
  assert.match(elements['#dialog'].innerHTML, /data-act="select"/);
  assert.doesNotMatch(elements['#dialog'].innerHTML, /En elaboración|data-act="instagram-inquiry"/);
});

test('el pedido identifica artículos, cantidades, precios, presentación y total', () => {
  const { context } = storefront();
  const text = vm.runInContext(`summaryText([
    {sku:'GN-TRIO', name:'Juego de 3 gnomos luminosos', pieces:3, price:25000, qty:1},
    {sku:'GN-ROJO', name:'Gnomo rojo', pieces:1, price:10000, qty:2}
  ])`, context);
  assert.match(text, /1 × Juego de 3 gnomos luminosos \(GN-TRIO\)/);
  assert.match(text, /2 × Gnomo rojo \(GN-ROJO\)/);
  assert.match(text, /25\.000 \/ juego/);
  assert.match(text, /10\.000 \/ unidad/);
  assert.match(text, /Subtotal: \$\s*20\.000/);
  assert.match(text, /Total del pedido: \$\s*45\.000 COP/);
  assert.match(text, /https:\/\/zhulgon.github.io\/Ventas_Navidad\//);
});

test('si se permite copiar, conserva todo el mensaje y explica cómo enviarlo', async () => {
  let copied;
  const { context, field, status } = storefront({ writeText: async text => { copied = text; } });
  await vm.runInContext('copyInstagramOrder()', context);
  assert.equal(copied, field.value);
  assert.match(status.textContent, /Pedido copiado/);
  assert.match(status.textContent, /pulsa Enviar/);
  assert.equal(field.selected, false);
});

for (const clipboard of [undefined, { writeText: async () => { throw new Error('denied'); } }]) {
  test(`permite copia manual cuando el portapapeles ${clipboard ? 'rechaza' : 'no existe'}`, async () => {
    const { context, field, status } = storefront(clipboard);
    await vm.runInContext('copyInstagramOrder()', context);
    assert.equal(field.focused, true);
    assert.equal(field.selected, true);
    assert.match(status.textContent, /manualmente/);
    assert.doesNotMatch(status.textContent, /Pedido copiado/);
  });
}
