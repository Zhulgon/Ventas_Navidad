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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.datos' / 'video-runtime'))
import imageio_ffmpeg

OUT = ROOT / 'multimedia'
CACHE = ROOT / '.datos' / 'reel-navidad'
W, H, FPS, OVERLAP = 1080, 1920, 30, 10
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
        ('GN-TRIO', 'MUÑEQUITOS', 'Gnomos luminosos', 'el trío de 3 colores', 'También por unidad: $10.000'),
        ('GN-TEJIDOS', 'MUÑEQUITOS', 'Gnomos tejidos', 'cada uno', 'Varios modelos para elegir'),
        ('TM-010', 'MUÑECOS', 'Papá Noel verde y dorado', 'por unidad', ''),
        ('TM-019', 'MUÑECOS', 'Papá Noel azul y blanco', 'el juego de 2 figuras', ''),
        ('MT-BLANCO-LAZOS', 'MANTELES', 'Blanco con lazos rojos', 'por unidad', ''),
        ('MT-RENOS-180', 'MANTELES', 'Navidad de estilo vintage', 'por unidad', 'Redondo · Diámetro 180 cm'),
        ('FD-AZUL-4', 'FUNDAS', 'Paisajes de invierno', 'el juego de 4 fundas', '45 × 45 cm'),
        ('TM-001', 'FUNDAS', 'Blanco y dorado', 'el juego de 4 fundas', '45 × 45 cm'),
    ]
    assert all(products[sku]['price'] == 10000 for sku in ('GN-DORADO', 'GN-GRIS', 'GN-ROJO'))
    scenes = [dict(kind='intro', frames=45)]
    for sku, category, title, unit, detail in specs:
        p = products[sku]
        assert p['category'] != 'Figuras anime' and p['price'] > 0
        scenes.append(dict(kind='product', frames=90, sku=sku, category=category, title=title,
                           price=p['price'], unit=unit, detail=detail, pieces=p['pieces'],
                           source='docs/fotos/' + (p['studio_photo'] or p['photo'])))
    scenes.append(dict(kind='outro', frames=90))
    return scenes


def plates(scene):
    if scene['kind'] == 'product':
        base = background()
        d = ImageDraw.Draw(base)
        star(d, 111, 184, 27, PINE)
        d.text((164, 151), 'Navidad BGA', font=font(47, bold=True), fill=PINE)
        d.line((80, 248, 1000, 248), fill='#d7d4c8', width=2)
        tracked(d, scene['category'], 290, PINE)
        centered(d, scene['title'], 351, 58, DEEP, serif=True)

        shadow = Image.new('RGBA', (W, H))
        ImageDraw.Draw(shadow).rounded_rectangle((70, 455, 1010, 1395), radius=30, fill=(40, 53, 40, 35))
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))
        base = Image.alpha_composite(base.convert('RGBA'), shadow).convert('RGB')
        d = ImageDraw.Draw(base)
        d.rounded_rectangle((70, 435, 1010, 1375), radius=30, fill='#fffefa')
        centered(d, price(scene['price']), 1430, 80, PINE, bold=True)
        centered(d, scene['unit'], 1537, 38, DEEP)
        if scene['detail']:
            centered(d, scene['detail'], 1601, 29, '#626d65')
        d.line((270, 1681, 810, 1681), fill='#c8c7ba', width=2)
        centered(d, '@navidadbga', 1725, 35, PINE, bold=True)
        return base

    base = background(dark=True)
    d = ImageDraw.Draw(base)
    for cx, cy, r in [(W + 60, 250, 340), (-160, 1660, 360)]:
        d.ellipse((cx-r, cy-r, cx+r, cy+r), outline='#46624c', width=2)
        d.ellipse((cx-r+30, cy-r+30, cx+r-30, cy+r-30), outline='#3e5c46', width=2)
    star(d, 540, 216, 30, GOLD)
    tracked(d, 'NAVIDAD BGA', 280, '#f0d9ae', 30, 7)
    if scene['kind'] == 'intro':
        cover = Image.open(ROOT / 'instagram/perfil/portada.jpg').convert('RGB').resize((700, 700), Image.Resampling.LANCZOS)
        mask = Image.new('L', (700, 700))
        ImageDraw.Draw(mask).ellipse((0, 0, 699, 699), fill=255)
        base.paste(cover, (190, 425), mask)
        d = ImageDraw.Draw(base)
        centered(d, 'Pequeños detalles,', 1220, 77, '#fff7e6', serif=True)
        centered(d, 'grandes fiestas.', 1325, 77, '#fff7e6', serif=True)
        centered(d, 'Bucaramanga', 1510, 35, '#dfd8c6')
        centered(d, '@navidadbga', 1630, 40, '#f0d9ae', bold=True)
    else:
        centered(d, 'Elige tus favoritos.', 540, 83, '#fff7e6', serif=True)
        centered(d, 'Haz tu pedido por mensaje', 690, 42, '#dfd8c6')
        centered(d, 'Instagram', 925, 37, '#f0d9ae')
        centered(d, '@navidadbga', 1000, 76, '#fff7e6', bold=True)
        d.rounded_rectangle((75, 1215, 1005, 1410), radius=24, fill='#f7f5ef')
        tracked(d, 'CATÁLOGO', 1244, PINE, 25, 5)
        centered(d, 'zhulgon.github.io/Ventas_Navidad/', 1314, 36, PINE, bold=True)
        centered(d, 'Bucaramanga', 1530, 35, '#dfd8c6')
        centered(d, 'Consulta disponibilidad', 1605, 29, '#dfd8c6')
    return base


def frame(scene, plate, picture, index):
    result = plate.copy()
    if picture is not None:
        t = index / (scene['frames'] - 1)
        eased = .5 - .5 * math.cos(math.pi * t)
        size = round(875 + 25 * eased)
        image = picture.resize((size, size), Image.Resampling.LANCZOS)
        result.paste(image, ((W-size)//2, 455+(900-size)//2))
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
        plate=plates(scene)
        prepared.append((scene,plate,photo))
    for i,(scene,plate,photo) in enumerate(prepared):
        frame(scene,plate,photo,scene['frames']//2).save(CACHE/f'{i:02}.jpg',quality=94)
    frame(*prepared[1],45).save(OUT/'portada-reel.jpg',quality=95)
    manifest=dict(brand='Navidad BGA', format='1080×1920, 9:16', fps=FPS, frames=total_frames,
                  duration_seconds=duration, transitions='Fundidos de 10 fotogramas y acercamiento suave sin recortar el producto',
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
        written=0
        try:
            for number,(scene,plate,photo) in enumerate(prepared):
                next_tail=[]
                for i in range(scene['frames']):
                    current=frame(scene,plate,photo,i)
                    if tail and i<OVERLAP:
                        weight=.5-.5*math.cos(math.pi*(i+1)/(OVERLAP+1))
                        current=Image.blend(tail[i],current,weight)
                    elif i>=scene['frames']-OVERLAP:
                        next_tail.append(current)
                        continue
                    process.stdin.write(current.tobytes())
                    written+=1
                tail=next_tail
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
