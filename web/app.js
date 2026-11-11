const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
const notice = document.querySelector('#notice');
const publicSite = Boolean(window.COSAS_NAVIDENAS?.publicCatalog);
const customer = publicSite || location.pathname === '/catalogo';
const catalogUrl = () => new URL(publicSite ? './' : '/catalogo', location.href).href;
const currency = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const count = new Intl.NumberFormat('es-CO');
const date = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota' });
const money = value => value == null ? 'Por definir' : currency.format(value);
const unitName = (product, plural = false) => product.pieces === 1 ? (plural ? 'unidades' : 'unidad') : (plural ? 'juegos' : 'juego');
const normalize = text => text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim();
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const isMatch = (p, text) => normalize(`${p.name} ${p.sku} ${p.category} ${p.variant}`).includes(normalize(text));
const sum = (list, getter) => list.reduce((total, item) => total + getter(item), 0);
const icons = {
  dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  box: '<path d="m12 2 9 5v10l-9 5-9-5V7l9-5Zm0 10v10m9-15-9 5-9-5m4.5-2.5 9 5"/>',
  sale: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6m-6 4h6m-6 4h3"/>',
  upload: '<path d="M12 16V3m-4 4 4-4 4 4M4 15v5h16v-5"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  external: '<path d="M7 17 17 7M7 7h10v10"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.7" cy="10.7" r="5.7"/><path d="m15 15 5 5"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  tag: '<path d="M3 3h8l10 10-8 8L3 11V3Z"/><circle cx="7.5" cy="7.5" r=".8"/>',
  wallet: '<path d="M20 8V5H5a2 2 0 0 0 0 4h15v10H5a2 2 0 0 1-2-2V7m17 6h-4v3h4"/>',
  stock: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5m-18 4 9 5 9-5"/>',
  bag: '<path d="M5 8h14l1 13H4L5 8Zm4 2V6a3 3 0 0 1 6 0v4"/>',
  settings: '<path d="M5 4v16M12 4v16M19 4v16"/><path d="M3 9h4m3 6h4m3-7h4" stroke-width="3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m3 16 5-5 4 4 3-3 6 6"/><circle cx="15" cy="8" r="1"/>',
  sparkle: '<path d="M12 2v20M2 12h20M5 5l14 14m0-14L5 19"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m9 10.5 6-4m-6 7 6 4"/>',
};
const icon = name => `<svg aria-hidden="true" viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">${icons[name]}</svg>`;
function photo(p, css = '', original = false) {
  const source = original ? p.photo : p.studio_photo || p.photo;
  return source ? `<img class="${css}" src="${publicSite ? './fotos/' : '/foto/'}${escape(source)}" alt="${escape(p.name)}" loading="lazy">` : `<span class="photo-empty ${css}" aria-label="Sin fotografía">${icon('image')}</span>`;
}
const adminNav = [ ['resumen', 'Resumen', 'dashboard'], ['inventario', 'Inventario', 'box'], ['ventas', 'Ventas', 'sale'], ['importar', 'Importar Excel', 'upload'] ];
let data = { products: [], sales: [], whatsapp: '' };
let chosenFile, preview, timer;
const filters = { inventory: { text: '', category: '', status: '' }, catalog: { text: '', category: '' } };
const selectionKey = customer ? 'reventa:seleccion' : 'reventa:seleccion-prueba';
let selection = new Map();
try { selection = new Map(JSON.parse(localStorage.getItem(selectionKey) ?? '[]')); } catch { /* Empty selection. */ }

async function request(path, options) {
  if (publicSite && (path !== 'catalogo' || options)) throw new Error('Abre el panel local para administrar la tienda.');
  const response = await fetch(publicSite ? './catalogo.json' : `/api/${path}`, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
  return result;
}
const post = (path, value) => request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
const upload = (path, file) => request(path, { method: 'POST', body: file });
async function load() {
  data = await request(customer ? 'catalogo' : 'admin');
  saveSelection();
}

function toast(message) {
  clearTimeout(timer);
  notice.textContent = message;
  notice.hidden = false;
  timer = setTimeout(() => { notice.hidden = true; }, 4600);
}

function route() {
  if (customer) return 'catalogo';
  const current = location.hash.slice(1);
  return [...adminNav.map(([id]) => id), 'catalogo'].includes(current) ? current : 'resumen';
}

function brand(sidebar = false) {
  return `<a class="brand" href="${publicSite ? './' : customer ? '/catalogo' : '#resumen'}"><img src="${publicSite ? './' : '/'}marca.svg" alt="" width="40" height="40"><span>Cosas Navideñas<small>${sidebar ? 'ESTUDIO DE REVENTA' : 'COLECCIÓN Y TIENDA'}</small></span></a>`;
}

function render() {
  const page = route();
  const label = adminNav.find(([key]) => key === page)?.[1] || 'Vista del catálogo';
  if (customer) {
    app.innerHTML = `<div class="store"><header class="store-header">${brand()}<div class="store-actions"><button data-act="share-catalog" class="button outline" aria-label="Compartir catálogo">${icon('share')} <span>Compartir</span></button><button data-act="selection" class="button outline selection-button">${icon('bag')} Mi selección <span data-bag-count></span></button></div></header><main id="contenido">${catalog()}</main></div>`;
  } else {
    const content = ({ resumen: dashboard, inventario: inventory, ventas, importar: importer, catalogo: catalog })[page];
    app.innerHTML = `<div class="shell"><aside class="sidebar">${brand(true)}<div class="sidebar-content"><p class="nav-label">ESPACIO DE TRABAJO</p><nav aria-label="Panel de gestión">${adminNav.map(([id, name, image]) => `<a href="#${id}" ${page === id ? 'aria-current="page"' : ''}>${icon(image)}<span>${name}</span></a>`).join('')}</nav><p class="nav-label second">TIENDA</p><nav aria-label="Tienda"><a href="#catalogo" ${page === 'catalogo' ? 'aria-current="page"' : ''}>${icon('eye')}<span>Vista del catálogo</span></a><button data-act="settings">${icon('settings')}<span>Contacto</span></button></nav></div><footer class="sidebar-footer"><span class="online"></span><div>Inventario local<small>Guardado en este equipo</small></div></footer></aside><div class="workspace"><header class="topbar"><div><span>Gestión</span><span class="breadcrumb">/</span><strong>${label}</strong></div><a class="button outline" href="/catalogo" target="_blank" rel="noopener">Vista cliente ${icon('external')}</a></header><main id="contenido" class="main">${content()}</main></div></div>`;
  }
  if (page === 'catalogo') { updateCatalog(); updateBag(); }
  if (page === 'inventario') updateInventory();
}

const metric = (label, value, sub, glyph, tone) => `<div class="metric"><span class="metric-icon ${tone}">${icon(glyph)}</span><p>${label}</p><strong>${value}</strong><small>${sub}</small></div>`;
const heading = (label, title, description, action = '') => `<header class="page-heading"><div><p class="eyebrow">${label}</p><h1>${title}</h1><p class="muted">${description}</p></div>${action}</header>`;
const newButton = `<button class="button primary" data-act="add">${icon('plus')} Agregar artículo</button>`;

function dashboard() {
  const { products, sales } = data;
  const physical = products.filter(p => !p.is_bundle);
  const pending = products.filter(p => p.price == null);
  const visible = products.filter(p => p.published).length;
  const available = sum(physical, p => p.stock);
  const active = sales.filter(s => !s.voided);
  const investment = sum(physical, p => (p.cost ?? 0) * p.stock);
  const groups = categories(products).map(name => ({ name, qty: products.filter(p => p.category === name).length })).sort((a, b) => b.qty - a.qty || a.name.localeCompare(b.name, 'es'));
  const review = (pending.length ? pending : products.filter(p => !p.published)).slice(0, 4);
  return `<section class="hero"><svg class="hero-art" aria-hidden="true" viewBox="0 0 520 265" fill="none" stroke="currentColor"><defs><pattern id="dots" width="23" height="23" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="currentColor" stroke="none"/></pattern></defs><path d="M0 0h520v265H0z" fill="url(#dots)" stroke="none" opacity=".28"/><circle cx="338" cy="125" r="109" opacity=".37"/><circle cx="338" cy="125" r="88" opacity=".63"/><path d="M338 0v33m-12 13h24v16h-24zM285 126a53 53 0 1 1 106 0 53 53 0 1 1-106 0Zm53-46v91m-40-68 80 46m0-46-80 46m28-60 12 12 12-12m-24 73 12-12 12 12m-45-42 16-4-4-16m42 51-4-16 16-4m-66 0 16 4-4 16m42-51-4 16 16 4M455 42v42m-21-21h42m-34-13 26 26m0-26-26 26M207 162v32m-16-16h32m235-21v18m-9-9h18" stroke-linecap="round"/><circle cx="245" cy="66" r="3"/><circle cx="421" cy="210" r="3"/></svg><div class="hero-copy"><p class="eyebrow"><span></span> PANEL DE REVENTA</p><h1>Cosas Navideñas</h1><p>Administra tus compras, prepara tu catálogo y registra cada venta desde un solo lugar.</p><div class="hero-actions"><a href="#inventario" class="button light">Ver inventario ${icon('arrow')}</a><a href="#importar" class="button translucent">${icon('upload')} Importar Excel</a></div></div></section>
    <section class="metrics" aria-label="Indicadores de inventario">
      ${metric('Referencias', count.format(products.length), `${groups.length} categorías en el inventario`, 'box', 'sage')}
      ${metric('Existencias disponibles', count.format(available), `${count.format(sum(physical, p => p.stock * p.pieces))} piezas en total`, 'stock', 'gold')}
      ${metric('Costo del stock', money(investment), physical.some(p => p.stock && p.cost == null) ? 'Suma de los costos conocidos' : 'Costo registrado de lo disponible', 'wallet', 'pink')}
      ${metric('Ingresos por ventas', money(sum(active, s => s.qty * s.price)), `${count.format(active.length)} ventas registradas`, 'sale', 'sage')}
    </section>
    <div class="dashboard-grid"><section class="panel categories"><div class="panel-head"><div><p class="eyebrow">INVENTARIO</p><h2>Por categoría</h2></div><a class="inline-link" href="#inventario">Ver todo ${icon('arrow')}</a></div>
      ${groups.length ? `<ol class="category-list">${groups.map(g => `<li><button data-act="category" data-id="${escape(g.name)}"><span>${escape(g.name)}</span><progress aria-label="Referencias de ${escape(g.name)}" value="${g.qty}" max="${groups[0].qty}"></progress><strong>${g.qty}</strong></button></li>`).join('')}</ol>` : `<p class="empty">Importa tus artículos para ver la distribución.</p>`}</section>
      <section class="panel review"><div class="panel-head"><div><p class="eyebrow">PREPARA TU TIENDA</p><h2>${pending.length ? 'Precios por definir' : 'Catálogo'}</h2></div><span class="badge amber">${pending.length ? `${pending.length} pendientes` : `${visible} visibles`}</span></div>
      <div class="review-list">${review.map(p => `<button data-act="edit" data-id="${escape(p.sku)}">${photo(p, 'thumb')}<span><small>${escape(p.sku)} · ${escape(p.category)}</small><strong>${escape(p.name)}</strong></span>${icon('arrow')}</button>`).join('') || '<p class="empty">Aquí verás artículos pendientes de preparar.</p>'}</div><a class="inline-link review-link" href="#catalogo">Abrir vista del catálogo ${icon('external')}</a></section></div>`;
}

function categories(products) { return [...new Set(products.map(p => p.category))].sort((a, b) => a.localeCompare(b, 'es')); }
function options(values, current) { return values.map(name => `<option ${name === current ? 'selected' : ''}>${escape(name)}</option>`).join(''); }
function inventory() {
  const { text, category, status } = filters.inventory;
  return `${heading('CONTROL DE EXISTENCIAS', 'Inventario', 'Revisa tus referencias, costos y precios de venta.', newButton)}
    <section class="panel inventory-panel"><div class="toolbar"><label class="search">${icon('search')}<input type="search" aria-label="Buscar en inventario" placeholder="Buscar por nombre, código o variante" value="${escape(text)}" data-filter="text" data-context="inventory"></label><select aria-label="Filtrar por categoría" data-filter="category" data-context="inventory"><option value="">Todas las categorías</option>${options(categories(data.products), category)}</select><select aria-label="Filtrar por estado" data-filter="status" data-context="inventory"><option value="">Todos los estados</option>${options(['Precio pendiente', 'Sin stock', 'Visible', 'Borrador'], status)}</select></div><div id="inventory-results"></div></section>`;
}

const productStatus = p => p.price == null ? ['Precio pendiente', 'amber'] : p.published ? ['Visible', 'green'] : ['Borrador', 'neutral'];
function updateInventory() {
  const { text, category, status } = filters.inventory;
  const matches = data.products.filter(p => isMatch(p, text) && (!category || p.category === category) && (!status || (status === 'Sin stock' ? p.stock === 0 : productStatus(p)[0] === status)));
  document.querySelector('#inventory-results').innerHTML = `<div class="results">${matches.length} de ${data.products.length} referencias</div>${matches.length ? `<div class="table-wrap"><table><thead><tr><th>Artículo</th><th>Categoría</th><th>Stock</th><th>Costo</th><th>Precio de venta</th><th>Catálogo</th><th>Acciones</th></tr></thead><tbody>${matches.map(p => { const [statusLabel, tone] = productStatus(p); return `<tr><td><button class="item-name" data-act="edit" data-id="${escape(p.sku)}">${photo(p, 'thumb')}<span><small>${escape(p.sku)}</small><strong>${escape(p.name)}</strong></span></button></td><td>${escape(p.category)}</td><td><strong>${count.format(p.stock)}</strong><small>${p.pieces === 1 ? 'Venta por unidad' : `${count.format(p.pieces)} piezas / juego`}</small></td><td>${money(p.cost)}</td><td>${money(p.price)}</td><td><span class="badge ${tone}">${statusLabel}</span></td><td><button class="text-button" data-act="sale" data-id="${escape(p.sku)}" ${p.stock ? '' : 'disabled'}>Vender</button></td></tr>`; }).join('')}</tbody></table></div>` : '<p class="empty">No hay artículos para estos filtros.</p>'}`;
}

function ventas() {
  const active = data.sales.filter(s => !s.voided);
  const known = active.filter(s => s.cost != null);
  return `${heading('HISTORIAL COMERCIAL', 'Ventas', 'Registra las ventas realizadas y consulta el stock que descontó cada una.', `<button class="button primary" data-act="sale" ${data.products.some(p => p.stock > 0) ? '' : 'disabled'}>${icon('plus')} Registrar venta</button>`)}
    <div class="metrics sales-metrics">${metric('Artículos vendidos', count.format(sum(active, s => s.qty)), `${active.length} registros vigentes`, 'box', 'sage')}${metric('Ingresos', money(sum(active, s => s.price * s.qty)), 'Total de ventas vigentes', 'wallet', 'gold')}${metric('Ganancia bruta', known.length || !active.length ? money(sum(known, s => (s.price - s.cost) * s.qty)) : 'Por calcular', known.length === active.length ? 'Ingresos menos costo de los artículos' : 'Solo ventas con costo registrado', 'tag', 'pink')}</div>
    <section class="panel"><div class="panel-head"><h2>Movimientos</h2></div>${data.sales.length ? `<div class="table-wrap"><table><thead><tr><th>Artículo</th><th>Fecha</th><th>Cliente</th><th>Cantidad</th><th>Total</th><th>Estado</th><th></th></tr></thead><tbody>${data.sales.map(s => `<tr><td><strong>${escape(s.name)}</strong><small>${escape(s.sku)}${s.note ? ` · ${escape(s.note)}` : ''}</small></td><td>${date.format(new Date(s.created))}</td><td>${escape(s.buyer || '—')}</td><td>${count.format(s.qty)}</td><td>${money(s.qty * s.price)}</td><td><span class="badge ${s.voided ? 'neutral' : 'green'}">${s.voided ? 'Anulada' : 'Registrada'}</span></td><td>${s.voided ? '' : `<button class="text-button" data-act="void" data-id="${s.id}">Anular</button>`}</td></tr>`).join('')}</tbody></table></div>` : '<p class="empty">Aún no hay ventas registradas.</p>'}</section>`;
}

function importer() {
  const changes = preview ? preview.added + preview.updated : 0;
  return `${heading('CARGA DE COMPRAS', 'Importar Excel', 'Agrega referencias nuevas o actualiza las existentes con su mismo ID.')}
    <div class="import-grid"><section class="panel import-panel"><h2>Archivo de inventario</h2><p class="muted">Selecciona la versión más reciente del archivo con la hoja <strong>Inventario</strong>.</p>
      <form id="import-form"><label class="dropzone">${icon('upload')}<strong>Selecciona un archivo .xlsx</strong><input type="file" id="workbook" accept=".xlsx" ${chosenFile ? '' : 'required'}><small>${chosenFile ? escape(chosenFile.name) : 'Máximo 16 MB'}</small></label><p class="form-error" role="alert"></p><button class="button primary" type="submit">Revisar archivo ${icon('arrow')}</button></form></section>
    <aside class="panel import-guide"><p class="eyebrow">CÓMO SE ACTUALIZA</p><h2>Trabaja con tu mismo Excel</h2><ol><li>Agrega una fila con un ID único para cada nueva referencia.</li><li>Usa el mismo ID para corregir un artículo o aumentar los juegos comprados.</li><li>Verifica la vista previa y confirma la importación.</li></ol><p class="muted">Las ventas se conservan. Se aplican los cambios del Excel desde la última carga. Las filas ausentes se conservan en la plataforma.</p></aside></div>
    ${preview ? `<section class="panel import-preview"><div class="panel-head"><div><p class="eyebrow">RESULTADO DE LA REVISIÓN</p><h2>${changes ? `${changes} referencias para importar` : 'El inventario ya está al día'}</h2></div>${changes ? '<button class="button primary" data-act="apply-import">Confirmar importación</button>' : ''}</div><div class="preview-badges"><span class="badge green">${preview.added} nuevas</span><span class="badge amber">${preview.updated} actualizadas</span><span class="badge neutral">${preview.unchanged} sin cambios</span></div><p id="import-error" class="form-error" role="alert"></p>${changes ? `<ul class="import-list">${preview.rows.map(p => `<li><strong>${escape(p.sku)}</strong><span>${escape(p.name)}</span><span class="badge ${p.status === 'added' ? 'green' : 'amber'}">${p.status === 'added' ? 'Nueva' : 'Actualizada'}</span></li>`).join('')}</ul>` : ''}</section>` : ''}`;
}

function catalog() {
  const { text, category } = filters.catalog;
  const images = ['GN-TRIO', 'TM-026', 'TM-001'].map(sku => data.products.find(p => p.sku === sku && p.photo)).filter(Boolean);
  const featured = [...new Set([...images, ...data.products.filter(p => p.photo)])].slice(0, 3);
  return `${customer ? '' : '<div class="preview-bar">'+icon('eye')+' <span><strong>Vista de trabajo.</strong> Aquí puedes revisar también los borradores.</span><button data-act="selection" class="button outline">'+icon('bag')+' Mi selección <span data-bag-count></span></button></div>'}
    <section class="catalog-hero"><div><p class="eyebrow">${icon('sparkle')} COLECCIÓN DE TEMPORADA</p><h1>Pequeños detalles,<br><em>grandes fiestas.</em></h1><p>Explora fundas, manteles, figuras y otros hallazgos para regalar, decorar y crear.</p><a class="button primary" href="#coleccion" data-act="collection">Ver colección ${icon('arrow')}</a></div>${featured.length ? `<div class="featured">${featured.map(p => photo(p)).join('')}</div>` : ''}</section>
    <section class="catalog-collection" id="coleccion"><div class="collection-heading"><div><p class="eyebrow">EXPLORA LA COLECCIÓN</p><h2>Todos los artículos</h2></div><label class="search">${icon('search')}<input type="search" aria-label="Buscar en el catálogo" placeholder="Buscar artículos" value="${escape(text)}" data-filter="text" data-context="catalog"></label></div><div class="chips" aria-label="Categorías del catálogo">${['', ...categories(data.products)].map(name => `<button class="chip" aria-pressed="${category === name}" data-act="catalog-category" data-id="${escape(name)}">${escape(name || 'Todo')}</button>`).join('')}</div><div id="catalog-results"></div></section>`;
}

function updateCatalog() {
  const { text, category } = filters.catalog;
  const matches = data.products.filter(p => isMatch(p, text) && (!category || p.category === category));
  document.querySelector('#catalog-results').innerHTML = matches.length ? `<div class="results">${matches.length} ${matches.length === 1 ? 'artículo' : 'artículos'}</div><div class="catalog-grid">${matches.map(p => `<article class="product-card"><button class="product-image" data-act="detail" data-id="${escape(p.sku)}" aria-label="Ver ${escape(p.name)}">${photo(p)}${!customer && !p.published ? '<span class="badge neutral">Borrador</span>' : ''}</button><div class="product-copy"><p class="eyebrow">${escape(p.category)}</p><h3><button data-act="detail" data-id="${escape(p.sku)}">${escape(p.name)}</button></h3><p>${p.pieces === 1 ? '1 pieza' : `${count.format(p.pieces)} piezas por juego`}</p><div class="product-foot"><strong>${p.price == null ? 'Precio por definir' : money(p.price)}</strong><button class="button outline" data-act="detail" data-id="${escape(p.sku)}">Ver ${icon('arrow')}</button></div></div></article>`).join('')}</div>` : `<div class="panel empty">${customer && !data.products.length ? 'Estamos preparando la colección. Vuelve pronto para ver los artículos disponibles.' : 'No hay artículos para estos filtros.'}</div>`;
}

function openDialog(title, content, label = 'COSAS NAVIDEÑAS') {
  dialog.innerHTML = `<div class="dialog-head"><div><p class="eyebrow">${label}</p><h2 id="dialog-title">${title}</h2></div><button class="icon-button" data-act="close" aria-label="Cerrar">${icon('close')}</button></div>${content}`;
  if (!dialog.open) dialog.showModal();
}
const input = (label, key, value, extra = '') => `<label class="field"><span>${label}</span><input name="${key}" value="${escape(value)}" ${extra}></label>`;
const formEnd = label => `<p class="form-error" role="alert"></p><div class="form-actions"><button class="button outline" type="button" data-act="close">Cancelar</button><button class="button primary" type="submit">${label}</button></div>`;

function productDialog(p = { pieces: 1, total: 1 }) {
  const editing = Boolean(p.sku);
  openDialog(editing ? `Editar ${escape(p.sku)}` : 'Agregar artículo', `<form id="product-form" data-editing="${editing}">
    <div class="edit-photo">${photo(p, 'thumb', true)}<label class="field"><span>Foto del artículo</span><input type="file" name="picture" accept="image/jpeg,image/png,image/webp"><small>${p.studio_photo ? 'La ficha usa una versión de estudio de esta referencia. ' : ''}JPG, PNG o WebP de hasta 2 MB.</small></label><input type="hidden" name="photo" value="${escape(p.photo)}"></div>
    <div class="field-grid">${input('Código único', 'sku', p.sku, `maxlength="40" required ${editing ? 'readonly' : 'placeholder="Ej. NAV-001"'}`)}${input('Categoría', 'category', p.category, 'maxlength="60" list="category-options" required')}<datalist id="category-options">${options(categories(data.products))}</datalist></div>
    ${input('Nombre del producto', 'name', p.name, 'maxlength="200" required')}
    <div class="field-grid">${input('Cantidad registrada', 'total', p.total, `type="number" min="${p.sold ?? 0}" max="1000000000" required ${p.is_bundle ? 'readonly' : ''}`)}${input('Piezas por presentación', 'pieces', p.pieces, `type="number" min="1" max="1000000000" required ${p.is_bundle ? 'readonly' : ''}`)}</div>
    ${p.is_bundle ? '<p class="form-help">El juego utiliza las existencias de sus muñecos individuales. Cantidad y costo se calculan automáticamente.</p>' : ''}
    <p class="form-help">${editing ? `${p.sold} vendidos · ${p.stock} disponibles. El total registrado incluye los vendidos.` : 'Registra la cantidad disponible y cuántas piezas incluye cada presentación.'}</p>
    <div class="field-grid">${input('Medidas', 'dimensions', p.dimensions, 'maxlength="200"')}${input('Variante', 'variant', p.variant, 'maxlength="200"')}</div>
    <div class="field-grid">${input('Costo por presentación (COP)', 'cost', p.cost, `type="number" min="0" step="any" max="1000000000" ${p.is_bundle ? 'readonly' : ''}`)}${input('Precio de venta (COP)', 'price', p.price, 'type="number" min="1" max="1000000000"')}</div>
    <label class="checkbox"><input type="checkbox" name="published" ${p.published ? 'checked' : ''}><span>Mostrar en la vista cliente <small>Requiere precio de venta.</small></span></label>
    ${formEnd('Guardar artículo')}</form>`, 'INVENTARIO');
}

function saleDialog(sku) {
  const available = data.products.filter(p => p.stock > 0);
  const p = available.find(p => p.sku === sku) || available[0];
  if (!p) return toast('Agrega existencias para registrar una venta.');
  openDialog('Registrar venta', `<form id="sale-form"><label class="field"><span>Artículo</span><select name="sku">${available.map(item => `<option value="${escape(item.sku)}" ${item === p ? 'selected' : ''}>${escape(item.sku)} · ${escape(item.name)}</option>`).join('')}</select></label>
    <div class="field-grid">${input('Cantidad', 'qty', 1, `type="number" min="1" max="${p.stock}" required`)}${input('Precio por presentación (COP)', 'price', p.price, 'type="number" min="1" max="1000000000" required')}</div><p class="form-help" id="sale-stock">${p.stock} ${unitName(p, p.stock !== 1)} disponibles</p>
    ${input('Cliente (opcional)', 'buyer', '', 'maxlength="100"')}<label class="field"><span>Nota (opcional)</span><textarea name="note" rows="2" maxlength="400"></textarea></label>${formEnd('Confirmar venta')}</form>`, 'VENTAS');
}

function settingsDialog() {
  openDialog('Contacto de la tienda', `<form id="settings-form"><p class="muted">Si configuras WhatsApp, el cliente podrá abrir su selección en un chat y enviarla manualmente.</p>${input('WhatsApp con código de país', 'whatsapp', data.whatsapp, 'inputmode="numeric" maxlength="15" placeholder="57 seguido del número"')}<p class="form-help">Solo dígitos. Puedes dejarlo vacío y copiar el pedido.</p>${formEnd('Guardar contacto')}</form>`, 'CONFIGURACIÓN');
}

function detail(p, original = false) {
  const currentQuantity = selectedItems().find(item => item.sku === p.sku)?.qty || 0;
  const canAdd = p.price > 0 && currentQuantity < selectionLimit(p);
  const referenceLink = p.photo !== p.studio_photo ? ` · <button class="text-button" data-act="${original ? 'detail' : 'original'}" data-id="${escape(p.sku)}">${original ? 'Ver estudio' : 'Ver referencia'}</button>` : '';
  const comparison = p.studio_photo ? `<p class="photo-caption">${original ? 'Foto de referencia' : 'Imagen de estudio editada con IA'}${referenceLink}</p>` : '';
  openDialog(escape(p.name), `<div class="detail"><div>${photo(p, 'detail-photo', original)}${comparison}</div><div class="detail-info"><span class="badge green">${escape(p.sku)}</span><dl><dt>Presentación</dt><dd>${p.pieces === 1 ? 'Venta por unidad' : `${count.format(p.pieces)} piezas por juego`}</dd>${p.variant ? `<dt>Variante</dt><dd>${escape(p.variant)}</dd>` : ''}${p.dimensions ? `<dt>Medidas</dt><dd>${escape(p.dimensions)}</dd>` : ''}<dt>Disponibilidad</dt><dd>${p.stock ? `${p.stock} ${unitName(p, p.stock !== 1)} ${p.stock === 1 ? 'disponible' : 'disponibles'}` : 'Agotado'}</dd></dl><div class="detail-price">${p.price == null ? 'Precio por definir' : money(p.price)}</div><button class="button primary" data-act="select" data-id="${escape(p.sku)}" ${canAdd ? '' : 'disabled'}>${icon('plus')} Agregar a mi selección</button>${customer ? '' : `<button class="text-button" data-act="edit" data-id="${escape(p.sku)}">Editar artículo</button>`}</div></div>`, escape(p.category));
}

function productParts(product) {
  return product.components?.length ? product.components : [{ sku: product.sku, quantity: 1, stock: product.stock }];
}

function selectedItems() {
  const remaining = new Map();
  for (const product of data.products) {
    for (const part of productParts(product)) remaining.set(part.sku, part.stock);
  }
  const items = [];
  for (const [sku, requested] of selection) {
    const product = data.products.find(p => p.sku === sku);
    if (!product || product.price <= 0 || !Number.isInteger(requested) || requested <= 0) continue;
    const parts = productParts(product);
    const capacity = Math.min(product.stock, ...parts.map(part => Math.floor(remaining.get(part.sku) / part.quantity)));
    const qty = Math.max(0, Math.min(requested, capacity));
    if (qty === 0) continue;
    items.push({ ...product, qty });
    for (const part of parts) remaining.set(part.sku, remaining.get(part.sku) - qty * part.quantity);
  }
  return items;
}

function selectionLimit(product) {
  const parts = productParts(product);
  const remaining = new Map(parts.map(part => [part.sku, part.stock]));
  for (const item of selectedItems()) {
    if (item.sku === product.sku) continue;
    for (const part of productParts(item)) {
      if (remaining.has(part.sku)) remaining.set(part.sku, remaining.get(part.sku) - item.qty * part.quantity);
    }
  }
  return Math.max(0, Math.min(product.stock, ...parts.map(part => Math.floor(remaining.get(part.sku) / part.quantity))));
}
function updateBag() {
  const qty = sum(selectedItems(), p => p.qty);
  for (const element of document.querySelectorAll('[data-bag-count]')) element.textContent = qty;
}
function saveSelection() {
  selection = new Map(selectedItems().map(item => [item.sku, item.qty]));
  try { localStorage.setItem(selectionKey, JSON.stringify([...selection])); } catch { /* Keep in memory. */ }
  updateBag();
}
function summaryText(items) {
  const total = sum(items, p => p.price * p.qty);
  return ['Hola, quisiera consultar por estos artículos de Cosas Navideñas:', '', ...items.map(p => `${p.qty} × ${p.name} (${p.sku}) — ${money(p.qty * p.price)}`), '', `Total de la selección: ${money(total)} COP`].join('\n');
}
function selectionDialog() {
  const items = selectedItems();
  const whatsapp = data.whatsapp ? `https://wa.me/${data.whatsapp}?text=${encodeURIComponent(summaryText(items))}` : '';
  openDialog('Mi selección', items.length ? `<div class="selection-list">${items.map(p => `<div>${photo(p, 'thumb')}<span><strong>${escape(p.name)}</strong><small>${money(p.price)} / ${unitName(p)}</small></span><label><span class="visually-hidden">Cantidad de ${escape(p.name)}</span><input type="number" min="1" max="${selectionLimit(p)}" value="${p.qty}" data-selection="${escape(p.sku)}"></label><button class="icon-button" data-act="remove" data-id="${escape(p.sku)}" aria-label="Quitar ${escape(p.name)}">${icon('close')}</button></div>`).join('')}</div><div class="selection-total"><span>Total estimado</span><strong>${money(sum(items, p => p.price * p.qty))}</strong></div><p class="form-help">Comparte esta lista para confirmar disponibilidad y acordar la compra.</p><div class="form-actions"><button class="button outline" data-act="copy">Copiar selección</button><button class="button primary" data-act="share-selection">${icon('share')} Compartir selección</button>${whatsapp ? `<a class="button primary" href="${escape(whatsapp)}" target="_blank" rel="noopener">Abrir WhatsApp ${icon('external')}</a>` : ''}</div>` : '<p class="empty">Tu selección está vacía. Agrega artículos con precio y disponibilidad desde la colección.</p>', 'CATÁLOGO');
}

async function busy(button, job) {
  if (button.disabled) return;
  button.disabled = true;
  try { await job(); } finally { button.disabled = false; }
}

async function handleSubmit(event) {
  const form = event.target;
  const formId = form.getAttribute('id');
  const actions = {
    'product-form': ['producto', 'Artículo guardado.'], 'sale-form': ['venta', 'Venta registrada.'],
    'settings-form': ['contacto', 'Contacto guardado.'], 'void-form': ['anular', 'Venta anulada y stock repuesto.'],
  };
  if (formId !== 'import-form' && !actions[formId]) return;
  event.preventDefault();
  const errorBox = form.querySelector('.form-error');
  errorBox.textContent = '';
  const values = Object.fromEntries(new FormData(form));
  await busy(event.submitter ?? form.querySelector('[type="submit"]'), async () => {
    try {
      if (formId === 'import-form') {
        if (!chosenFile) throw new Error('Selecciona el Excel para continuar.');
        preview = await upload('importar', chosenFile);
        render();
        return;
      }
      if (formId === 'product-form') {
        if (values.picture.size) {
          if (values.picture.size > 2 * 1024 * 1024) throw new Error('La foto debe pesar hasta 2 MB.');
          values.photo = (await upload('foto', values.picture)).photo;
        }
        delete values.picture;
        values.editing = form.dataset.editing === 'true';
        values.published = form.elements.published.checked;
      }
      const [endpoint, message] = actions[formId];
      await post(endpoint, values);
      dialog.close();
      await load();
      render();
      toast(message);
    } catch (error) {
      if (errorBox.isConnected && (!form.closest('dialog') || dialog.open)) errorBox.textContent = error.message;
      else toast(error.message);
    }
  });
}

async function handleAction(event) {
  const button = event.target.closest('[data-act]');
  if (!button) return;
  const { act, id } = button.dataset;
  const product = data.products.find(p => p.sku === id);
  if (act === 'add') productDialog();
  if (act === 'edit' && product) productDialog(product);
  if (act === 'detail' && product) detail(product);
  if (act === 'original' && product?.studio_photo) detail(product, true);
  if (act === 'sale') saleDialog(id);
  if (act === 'settings') settingsDialog();
  if (act === 'close') dialog.close();
  if (act === 'selection') selectionDialog();
  if (act === 'share-catalog' || act === 'share-selection') {
    const text = act === 'share-selection' ? summaryText(selectedItems()) : 'Mira la colección de Cosas Navideñas';
    try {
      if (navigator.share) await navigator.share({ title: 'Cosas Navideñas', text, url: catalogUrl() });
      else {
        await navigator.clipboard.writeText(`${text}\n${catalogUrl()}`);
        toast(act === 'share-selection' ? 'Selección y enlace copiados.' : 'Enlace del catálogo copiado.');
      }
    } catch (error) {
      if (error.name !== 'AbortError') openDialog('Comparte el catálogo', `<label class="field"><span>Texto para compartir</span><textarea readonly rows="8">${escape(text + '\n' + catalogUrl())}</textarea></label>`);
    }
  }
  if (act === 'category') {
    Object.assign(filters.inventory, { category: id, text: '', status: '' });
    location.hash = 'inventario';
  }
  if (act === 'catalog-category') {
    filters.catalog.category = id;
    for (const chip of app.querySelectorAll('[data-act="catalog-category"]')) chip.setAttribute('aria-pressed', chip === button);
    updateCatalog();
  }
  if (act === 'collection') {
    event.preventDefault();
    document.querySelector('#coleccion').scrollIntoView({ block: 'start' });
  }
  if (act === 'select' && product?.price && product.stock > 0) {
    const currentQuantity = selectedItems().find(item => item.sku === id)?.qty || 0;
    if (currentQuantity >= selectionLimit(product)) return toast('Las unidades disponibles ya están incluidas en tu selección.');
    selection.set(id, currentQuantity + 1);
    saveSelection();
    dialog.close();
    toast('Artículo agregado a tu selección.');
  }
  if (act === 'remove') {
    selection.delete(id);
    saveSelection();
    selectionDialog();
  }
  if (act === 'copy') {
    const text = summaryText(selectedItems());
    try {
      await navigator.clipboard.writeText(text);
      dialog.close();
      toast('Selección copiada.');
    } catch {
      openDialog('Copia tu selección', `<label class="field"><span>Resumen del pedido</span><textarea readonly rows="8">${escape(text)}</textarea></label>`);
      dialog.querySelector('textarea').select();
    }
  }
  if (act === 'void') openDialog('Anular venta', `<form id="void-form"><p class="muted">Las existencias volverán al stock y la venta quedará marcada como anulada en el historial.</p><input type="hidden" name="id" value="${escape(id)}">${formEnd('Anular venta')}</form>`, 'VENTAS');
  if (act === 'apply-import' && chosenFile) await busy(button, async () => {
    try {
      const result = await upload('importar?aplicar=1', chosenFile);
      chosenFile = preview = null;
      await load();
      render();
      toast(`Importación completa. ${result.added} nuevas, ${result.updated} actualizadas.`);
    } catch (error) { const output = document.querySelector('#import-error'); if (output) output.textContent = error.message; else toast(error.message); }
  });
}

document.addEventListener('click', handleAction);
document.addEventListener('submit', handleSubmit);
document.querySelector('.skip').addEventListener('click', event => {
  event.preventDefault();
  const main = document.querySelector('#contenido');
  main?.setAttribute('tabindex', '-1');
  main?.focus();
});
document.addEventListener('input', event => {
  const { context, filter } = event.target.dataset;
  if (!context) return;
  filters[context][filter] = event.target.value;
  if (context === 'inventory') updateInventory();
  else updateCatalog();
});
document.addEventListener('change', event => {
  const field = event.target;
  if (field.id === 'workbook') {
    chosenFile = field.files[0];
    preview = null;
    render();
    document.querySelector('#workbook').focus();
  }
  if (field.form?.id === 'sale-form' && field.name === 'sku') {
    const p = data.products.find(item => item.sku === field.value);
    field.form.elements.qty.value = 1;
    field.form.elements.qty.max = p.stock;
    field.form.elements.price.value = p.price ?? '';
    document.querySelector('#sale-stock').textContent = `${p.stock} disponibles`;
  }
  const sku = field.dataset.selection;
  if (sku) {
    selection.set(sku, Math.min(Number(field.max), Math.max(1, Math.trunc(Number(field.value)) || 1)));
    saveSelection();
    selectionDialog();
  }
});
window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
load().then(render).catch(error => { app.innerHTML = `<p class="loading">${escape(error.message)}</p>`; });
