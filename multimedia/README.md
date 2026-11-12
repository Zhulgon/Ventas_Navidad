# Reel y estados · Navidad BGA

Video vertical de 25,5 segundos en 1080 × 1920, 30 fps, MP4 H.264. Incluye ocho referencias de muñecos, muñequitos, manteles y fundas con los precios del catálogo al crear el video. Las figuras de anime están excluidas.

- `NavidadBGA-reel-estados.mp4`: versión con música instrumental original de campanillas y acordes suaves, sin voz.
- `NavidadBGA-vertical-sin-musica.mp4`: misma edición, sin pista de audio, para añadir otra música al compartir.
- `portada-reel.jpg`: imagen vertical para la portada.
- `pie-de-foto.txt`: texto sugerido para acompañarlo.
- `guion.json`: escenas, fotos de origen y precios.
- `verificacion.json`: comprobación de duración, dimensiones, fotogramas, audio y decodificación completa.

[Abrir y descargar desde el celular](https://zhulgon.github.io/Ventas_Navidad/reel/).

Las fotos de estudio se conservan completas, con un acercamiento suave y transiciones por fundido. La música se sintetiza desde notas y armónicos en el script, sin utilizar pistas ni samples externos. Las fotografías originales del catálogo ya estaban editadas con IA.

## Volver a generar

Requiere Python, las dependencias de `requirements.txt` y las fuentes Georgia y Segoe UI de Windows. El script toma las fotos y los precios de `docs/catalogo.json` y actualiza también los archivos de `docs/reel`.

```powershell
py -3 -m pip install -r multimedia/requirements.txt
py -3 multimedia/crear_reel.py
```

La reproducción, el formato H.264, los 765 fotogramas y el audio del video entregado se verificaron antes de guardarlo. Los precios del video son una edición fija; para reflejar cambios posteriores del inventario hay que volver a generarlo.
