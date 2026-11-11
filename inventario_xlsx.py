"""Read the inventory sheet and its embedded reference photographs."""

import io
import posixpath
import re
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

MAX_UPLOAD = 16 * 1024 * 1024
MAX_PHOTO = 2 * 1024 * 1024


def image_type(data):
    if not data or len(data) > MAX_PHOTO:
        return None
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def number(value, label, minimum=0, optional=False, integer=True):
    if optional and (value is None or str(value).strip() == ''):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        parsed = Decimal(str(value))
        if not parsed.is_finite() or not minimum <= parsed <= 1_000_000_000 or (integer and parsed != int(parsed)):
            raise ValueError
    except (InvalidOperation, ValueError, OverflowError):
        kind = 'entero' if integer else 'número'
        raise ValueError(f'{label} debe ser un {kind} entre {minimum} y 1.000.000.000.') from None
    return int(parsed) if integer else float(parsed)


def read_inventory(data):
    if len(data) > MAX_UPLOAD:
        raise ValueError('El Excel supera el límite de 16 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 2_000 or sum(f.file_size for f in archive.infolist()) > 48 * 1024 * 1024:
                raise ValueError('El Excel supera el tamaño permitido al abrirlo.')
            return read_sheet(archive)
    except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, OSError, RuntimeError, NotImplementedError):
        raise ValueError('No pude leer el archivo. Guarda el inventario como .xlsx e inténtalo de nuevo.') from None


def read_sheet(archive):
    def xml(path):
        data = archive.read(path)
        if b'<!DOCTYPE' in data.upper():
            raise ValueError('El archivo contiene XML no compatible.')
        return ET.fromstring(data)

    def relationships(path):
        folder, name = posixpath.split(path)
        rel_path = posixpath.join(folder, '_rels', name + '.rels')
        if rel_path not in archive.namelist():
            return {}
        return {rel.attrib['Id']: posixpath.normpath(posixpath.join(folder, rel.attrib['Target'])).lstrip('/')
                for rel in xml(rel_path) if rel.get('TargetMode') != 'External'}

    def attr(element, name):
        return next((value for key, value in element.attrib.items() if key.endswith('}' + name)), None)

    def rich_text(element):
        return ''.join(node.text or '' for node in element.iterfind('.//{*}t'))

    workbook_path = 'xl/workbook.xml'
    sheet = next((node for node in xml(workbook_path).iterfind('.//{*}sheet')
                  if node.get('name', '').strip().casefold() == 'inventario'), None)
    if sheet is None:
        raise ValueError('El Excel debe contener una hoja llamada Inventario.')
    path = relationships(workbook_path)[attr(sheet, 'id')]
    sheet = xml(path)
    strings = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        strings = [rich_text(node) for node in xml('xl/sharedStrings.xml')]

    photos = {}
    for drawing in sheet.iterfind('{*}drawing'):
        drawing_path = relationships(path)[attr(drawing, 'id')]
        targets = relationships(drawing_path)
        for anchor in xml(drawing_path):
            row = anchor.find('{*}from/{*}row')
            col = anchor.find('{*}from/{*}col')
            image = anchor.find('.//{*}blip')
            if row is None or col is None or col.text != '1' or image is None:
                continue
            target = targets.get(attr(image, 'embed'))
            if target:
                photo = archive.read(target)
                if not image_type(photo):
                    raise ValueError(f'La foto de la fila {int(row.text) + 1} debe ser JPG, PNG o WebP de hasta 2 MB.')
                photos.setdefault(int(row.text) + 1, photo)

    products, seen = [], set()
    found_header = False
    for row in sheet.iterfind('{*}sheetData/{*}row'):
        cells = {}
        for cell in row.iterfind('{*}c'):
            col = re.sub(r'\d', '', cell.attrib['r'])
            value = cell.findtext('{*}v', '')
            if cell.get('t') == 's':
                value = strings[int(value)]
            elif cell.get('t') == 'inlineStr':
                value = rich_text(cell)
            elif not value and cell.find('{*}f') is not None:
                value = '[fórmula sin valor guardado]'
            cells[col] = value.strip()
        if not found_header:
            found_header = (cells.get('A', '').casefold() == 'id' and
                            cells.get('D', '').casefold() == 'nombre del producto' and
                            cells.get('E', '').casefold() == 'juegos comprados')
            continue
        sku = cells.get('A', '').upper()
        name = cells.get('D', '')
        if not sku and not name:
            continue
        line = int(row.attrib['r'])
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_.-]{0,39}', sku) or not name:
            raise ValueError(f'Fila {line}: agrega un ID válido y el nombre del producto.')
        if sku in seen:
            raise ValueError(f'Fila {line}: el ID {sku} está repetido.')
        seen.add(sku)
        price = number(cells.get('J'), f'Precio de {sku}', optional=True)
        products.append(dict(sku=sku, name=name, category=cells.get('C') or 'Sin categoría',
                             bought=number(cells.get('E'), f'Juegos comprados de {sku}'),
                             pieces=number(cells.get('F'), f'Piezas por juego de {sku}', minimum=1),
                             dimensions=cells.get('H', ''), variant=cells.get('I', ''), price=price or None,
                             cost=number(cells.get('K'), f'Costo por juego de {sku}', optional=True, integer=False),
                             photo=photos.get(line)))
    if not found_header or not products:
        raise ValueError('No encontré filas de productos con los encabezados del inventario original.')
    if len(products) > 2_000:
        raise ValueError('El Excel puede incluir hasta 2.000 referencias.')
    return products
