"""Renderiza el reel vertical de Navidad BGA con las fotos publicadas del catálogo."""

import argparse
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.datos' / 'video-runtime'))
import imageio_ffmpeg

OUT = ROOT / 'multimedia'
CACHE = ROOT / '.datos' / 'reel-navidad'
W, H, FPS, OVERLAP = 1080, 1920, 30, 12
PAPER, PINE, DEEP, GOLD = '#f7f5ef', '#214a3a', '#17372c', '#e5c387'
FONTS = Path('C:/Windows/Fonts')


def font(size, serif=False, bold=False):
    name = 'georgiab.ttf' if serif and bold else 'georgia.ttf' if serif else 'seguisb.ttf' if bold else 'segoeui.ttf'
    return ImageFont.truetype(str(FONTS / name), size)


def centered(draw, text, y, size, fill, serif=False, bold=False):
    face = font(size, serif, bold)
    box = draw.textbbox((0, 0), text, font=face)
    if box[2] - box[0] > W - 150:
        raise ValueError(f'El texto no cabe: {text}')
    draw.text(((W - box[2] + box[0]) / 2, y - box[1]), text, font=face, fill=fill)


def tracked(draw, text, y, fill, size=27, spacing=6):
    face = font(size, bold=True)
    widths = [draw.textlength(c, font=face) for c in text]
    x = (W - sum(widths) - spacing * (len(text) - 1)) / 2
    for char, width in zip(text, widths):
        draw.text((x, y), char, font=face, fill=fill)
        x += width + spacing


def star(draw, cx, cy, radius, fill):
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = radius if i % 2 == 0 else radius * .42
        points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    draw.polygon(points, fill=fill)


def background(dark=False):
    top = np.array([23, 55, 44] if dark else [247, 245, 239], dtype=np.float32)
    bottom = np.array([33, 74, 58] if dark else [239, 232, 218], dtype=np.float32)
    t = np.linspace(0, 1, H)[:, None, None]
    colors = top[None, None, :] * (1 - t) + bottom[None, None, :] * t
    pixels = np.broadcast_to(colors, (H, W, 3)).astype(np.uint8).copy()
    return Image.fromarray(pixels)


def price(value):
    return '$' + f'{value:,}'.replace(',', '.')


def make_scenes():
    products = {p['sku']: p for p in json.loads((ROOT / 'docs/catalogo.json').read_text('utf-8'))['products']}
    specs = [
        (0, 3.6, 'GN-TRIO', 'MUÑEQUITOS PEQUEÑOS CON LUZ', ['La Navidad', 'empieza en casa.'],
         'El trío luminoso', 'También individuales: $10.000'),
        (0, 3.6, 'GN-TEJIDOS', 'GNOMOS GRANDES · SIN LUZ', ['Piernas largas,', 'mucho encanto.'],
         'Cada gnomo', 'Modelos surtidos · Sin luz'),
        (1, 3.0, 'TM-010', 'PAPÁ NOEL · COLECCIÓN', ['Verde', 'y dorado.'], 'Por unidad', 'Verde y dorado'),
        (1, 3.0, 'TM-011', 'PAPÁ NOEL · COLECCIÓN', ['Blanco', 'y dorado.'], 'Por unidad', 'Atuendo dorado'),
        (1, 3.0, 'TM-012', 'PAPÁ NOEL · COLECCIÓN', ['El encanto', 'del rojo clásico.'], 'Por unidad', 'Traje rojo escocés'),
        (1, 3.0, 'TM-019', 'PAPÁ NOEL · COLECCIÓN', ['Azul', 'de invierno.'], 'Juego de 2 figuras', 'Azul y blanco'),
        (1, 3.0, 'TM-046', 'PAPÁ NOEL · COLECCIÓN', ['Gris, rojo', 'y mucho estilo.'], 'Por unidad', 'Con bastón'),
        (1, 3.0, 'TM-045', 'PAPÁ NOEL · COLECCIÓN', ['Santa', 'con su osito.'], 'Por unidad', 'Traje rojo y verde'),
        (2, 3.6, 'MT-ROJO-REDONDO', 'MANTELES REDONDOS', ['Una mesa', 'para celebrar.'],
         'Por unidad', 'Redondo · 150 cm'),
        (2, 3.6, 'MT-BLANCO-LAZOS', 'MANTELES · MÁS FORMAS', ['Cuadrados y', 'rectangulares.'],
         'Modelo con lazos', 'Blanco y rojo'),
        (2, 3.6, 'MT-PE-NACIMIENTO', 'MANTEL DESECHABLE · PE', ['La tradición', 'en tu mesa.'],
         'Por unidad', 'Desechable · 220 × 130 cm'),
        (3, 3.6, 'FD-AZUL-4', 'FUNDAS DE COJÍN', ['Un rincón', 'para soñar.'],
         'Juego de 4 fundas', '45 × 45 cm'),
        (3, 3.6, 'TM-005', 'FUNDAS DE COJÍN', ['El encanto', 'de los dorados.'],
         'Juego de 4 fundas', '45 × 45 cm'),
    ]
    assert all(products[sku]['price'] == 10000 for sku in ('GN-DORADO', 'GN-GRIS', 'GN-ROJO'))
    assert products['TM-005']['price'] == 20000
    scenes = []
    for number, (chapter, seconds, sku, category, title, unit, detail) in enumerate(specs):
        p = products[sku]
        assert p['category'] != 'Figuras anime' and p['price'] > 0
        scenes.append(dict(kind='product', frames=round(seconds*FPS)+OVERLAP, number=number,
                           chapter=chapter, sku=sku, category=category, title=title,
                           price=p['price'], unit=unit, detail=detail, pieces=p['pieces'],
                           source='docs/fotos/' + (p['studio_photo'] or p['photo'])))
    scenes.append(dict(kind='outro', frames=108))
    return scenes


def plates(scene, picture=None):
    if scene['kind'] == 'product':
        # The background comes from the photo itself: no card, frame or competing collage.
        pixels = np.array(picture.resize((120, 120)), dtype=np.float32)
        # Extend the studio's edge colors vertically, so the photo has no visible rectangular panel.
        rows = pixels[:, [0, 1, 2, -3, -2, -1], :].mean(axis=1).astype(np.uint8)
        base = Image.new('RGB', (W, H), tuple(int(v) for v in rows[0]))
        strip = Image.fromarray(rows[:, None, :]).resize((W, 1080), Image.Resampling.BILINEAR)
        base.paste(strip, (0, 430))
        ImageDraw.Draw(base).rectangle((0, 1510, W, H), fill=tuple(int(v) for v in rows[-1]))
        d = ImageDraw.Draw(base)
        tracked(d, scene['category'], 170, PINE, 24, 3)
        for i, line in enumerate(scene['title']):
            centered(d, line, 240 + i*88, 78, DEEP, serif=True)
        d.line((92, 1532, 988, 1532), fill='#baac90', width=2)
        face = font(86, bold=True)
        value = price(scene['price'])
        box = d.textbbox((0, 0), value, font=face)
        d.text((92, 1568-box[1]), value, font=face, fill=PINE)
        # Presentation stays beside the price; "fundas" and the trio/unit distinction remain explicit.
        unit_size = 34 if scene['sku'] != 'GN-TRIO' else 35
        d.text((590, 1565), scene['unit'], font=font(unit_size, bold=True), fill=DEEP)
        if scene['sku'] == 'GN-TRIO':
            centered(d, scene['detail'], 1682, 32, DEEP)
        else:
            detail_size = 31
            while d.textlength(scene['detail'], font=font(detail_size)) > 398:
                detail_size -= 1
            d.text((590, 1618), scene['detail'], font=font(detail_size), fill='#586257')
        for i in range(4):
            x = 498+i*28
            active = i == scene['chapter']
            d.ellipse((x-4, 1756-4, x+4, 1756+4), fill=PINE if active else '#bcae96')
        centered(d, '@navidadbga', 1790, 29, PINE)
        return base

    base = background(dark=True)
    d = ImageDraw.Draw(base)
    for cx, cy, r in [(W + 60, 250, 340), (-160, 1660, 360)]:
        d.ellipse((cx-r, cy-r, cx+r, cy+r), outline='#46624c', width=2)
        d.ellipse((cx-r+30, cy-r+30, cx+r-30, cy+r-30), outline='#3e5c46', width=2)
    star(d, 540, 288, 38, GOLD)
    tracked(d, 'NAVIDAD BGA', 380, '#f0d9ae', 30, 7)
    centered(d, 'Que tu casa', 640, 84, '#fff7e6', serif=True)
    centered(d, 'se sienta Navidad.', 752, 84, '#fff7e6', serif=True)
    d.line((450, 968, 630, 968), fill=GOLD, width=3)
    centered(d, '@navidadbga', 1110, 78, '#fff7e6', bold=True)
    centered(d, 'Pedidos por mensaje', 1226, 40, '#f0d9ae')
    centered(d, 'Bucaramanga', 1515, 34, '#dfd8c6')
    centered(d, 'Consulta disponibilidad · Precios en COP', 1580, 28, '#dfd8c6')
    return base


def frame(scene, plate, picture, index):
    result = plate.copy()
    if picture is not None:
        t = index / (scene['frames'] - 1)
        eased = .5 - .5 * math.cos(math.pi * t)
        size = round(1040 + 40 * eased)
        image = picture.resize((size, size), Image.Resampling.LANCZOS)
        # Feather only the outer eight pixels of the studio background, leaving products complete.
        mask = Image.new('L', (size, size), 0)
        md = ImageDraw.Draw(mask)
        for edge in range(9):
            md.rectangle((edge, edge, size-1-edge, size-1-edge), fill=round(255*edge/8))
        result.paste(image, ((W-size)//2, 430+(1080-size)//2), mask)
    return result


def soundtrack(seconds, filename):
    """Composición original de celesta, acordes suaves y campanillas; sin samples."""
    rate = 48000
    samples = np.zeros((math.ceil(seconds*rate), 2), dtype=np.float64)

    def note(midi, start, length, volume, pan=0, bell=False):
        start_index = round(start*rate)
        count = min(round(length*rate), len(samples)-start_index)
        if count <= 0:
            return
        t = np.arange(count)/rate
        hz = 440*2**((midi-69)/12)
        attack = np.minimum(1, t/.009)
        if bell:
            tone = sum(a*np.sin(2*np.pi*hz*ratio*t)*np.exp(-decay*t)
                       for ratio,a,decay in [(1,.72,2.6),(2,.17,4),(2.76,.065,5),(4.07,.028,7)])
            envelope = attack*np.minimum(1, np.maximum(0,(length-t)/.20))
        else:
            tone = np.sin(2*np.pi*hz*t)+.15*np.sin(2*np.pi*2*hz*t)
            envelope = np.minimum(1,t/.13)*np.minimum(1,np.maximum(0,(length-t)/.6))*np.exp(-.25*t)
        signal = tone*envelope*volume
        samples[start_index:start_index+count,0] += signal*math.sqrt((1-pan)/2)
        samples[start_index:start_index+count,1] += signal*math.sqrt((1+pan)/2)

    chords = [(48,52,55),(45,48,52),(41,45,48),(43,47,50)]
    melody = [(76,79,84,79),(76,81,79,76),(77,81,84,81),(74,79,83,79)]
    bar, beat = 2.4, .6
    for b in range(math.ceil(seconds/bar)):
        for pitch in chords[b%4]:
            note(pitch, b*bar, 2.7, .045, pan=(pitch%3-1)*.2)
        for n,pitch in enumerate(melody[b%4]):
            note(pitch, b*bar+n*beat+.15, 1.6, .095, pan=(-.2 if n%2 else .2), bell=True)
        if b%2==0:
            note(96,b*bar+1.95,1.0,.025,pan=.4,bell=True)
    t = np.arange(len(samples))/rate
    envelope = np.minimum(1,t/.7)*np.minimum(1,np.maximum(0,(seconds-t)/1.2))
    samples *= envelope[:,None]
    samples *= .60/max(np.max(np.abs(samples)), .001)
    with wave.open(str(filename),'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    CACHE.mkdir(parents=True,exist_ok=True)
    scenes=make_scenes()
    total_frames=sum(s['frames'] for s in scenes)-OVERLAP*(len(scenes)-1)
    duration=total_frames/FPS
    prepared=[]
    for scene in scenes:
        photo=Image.open(ROOT/scene['source']).convert('RGB') if scene['kind']=='product' else None
        plate=plates(scene, photo)
        prepared.append((scene,plate,photo))
    for i,(scene,plate,photo) in enumerate(prepared):
        frame(scene,plate,photo,scene['frames']//2).save(CACHE/f'{i:02}.jpg',quality=94)
    frame(*prepared[0],69).save(OUT/'portada-reel.jpg',quality=95)
    manifest=dict(brand='Navidad BGA', edition=3, format='1080×1920, 9:16', fps=FPS, frames=total_frames,
                  art_direction='Colecciones ordenadas: gnomos pequeños con luz y grandes sin luz; seis modelos de Papá Noel; variedad de manteles; fundas con precio corregido',
                  chapters=['Muñequitos y gnomos', 'Papá Noel', 'Manteles', 'Fundas'],
                  duration_seconds=duration, transitions='Paso de 12 fotogramas por un fondo liso, sin superponer productos; acercamiento suave sin recortar',
                  audio='Composición instrumental original sintetizada en crear_reel.py; sin samples externos',
                  instagram='https://www.instagram.com/navidadbga/', catalog='https://zhulgon.github.io/Ventas_Navidad/',
                  scenes=scenes)
    (OUT/'guion.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.preview:
        print(f'Previsualizaciones listas: {len(scenes)} escenas; duración {duration:.1f} s.',flush=True)
        return
    executable=imageio_ffmpeg.get_ffmpeg_exe()
    silent=OUT/'NavidadBGA-vertical-sin-musica.mp4'
    log=CACHE/'render.log'
    command=[executable,'-hide_banner','-loglevel','warning','-y','-f','rawvideo','-vcodec','rawvideo',
             '-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an',
             '-vf','scale=out_color_matrix=bt709:out_range=tv',
             '-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-threads','4',
             '-profile:v','high','-level:v','4.1','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
             '-movflags','+faststart',str(silent)]
    with log.open('wb') as errors:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=errors)
        tail=[]
        previous_plate=None
        written=0
        try:
            for number,(scene,plate,photo) in enumerate(prepared):
                next_tail=[]
                bridge=None
                if previous_plate is not None:
                    color=tuple(round((a+b)/2) for a,b in zip(previous_plate.getpixel((0,0)),plate.getpixel((0,0))))
                    bridge=Image.new('RGB',(W,H),color)
                for i in range(scene['frames']):
                    current=frame(scene,plate,photo,i)
                    if tail and i<OVERLAP:
                        # Fade through one calm color; two products and two prices never overlap.
                        half=OVERLAP//2
                        if i<half:
                            weight=.5-.5*math.cos(math.pi*(i+1)/half)
                            current=Image.blend(tail[i],bridge,weight)
                        else:
                            weight=.5-.5*math.cos(math.pi*(i-half+1)/half)
                            current=Image.blend(bridge,current,weight)
                    elif i>=scene['frames']-OVERLAP:
                        next_tail.append(current)
                        continue
                    process.stdin.write(current.tobytes())
                    written+=1
                tail=next_tail
                previous_plate=plate
                print(f'Escena {number+1}/{len(prepared)}: {scene.get("sku",scene["kind"])}',flush=True)
            for current in tail:
                process.stdin.write(current.tobytes())
                written+=1
            process.stdin.close()
            code=process.wait()
            if code:
                raise RuntimeError(log.read_text('utf-8',errors='replace'))
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
        assert written==total_frames,(written,total_frames)
    wav=CACHE/'musica-original.wav'
    soundtrack(duration,wav)
    target=OUT/'NavidadBGA-reel-estados.mp4'
    subprocess.run([executable,'-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(wav),
                    '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k',
                    '-af','loudnorm=I=-18:TP=-1.5:LRA=9','-shortest','-movflags','+faststart',str(target)],check=True)
    public=ROOT/'docs/reel'
    public.mkdir(parents=True,exist_ok=True)
    for asset in (target,silent,OUT/'portada-reel.jpg'):
        shutil.copyfile(asset,public/asset.name)
    print(f'Listo: {target} ({duration:.1f} segundos).',flush=True)


if __name__=='__main__':
    main()
