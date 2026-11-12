# Reel y estados · Navidad BGA

Video vertical de 46,8 segundos en 1080 × 1920, 30 fps, MP4 H.264. Esta tercera edición muestra 13 referencias agrupadas en cuatro colecciones: los pequeños gnomos luminosos y los grandes tejidos sin luz; seis modelos de Papá Noel; variedad de manteles redondos, para mesas cuadradas o rectangulares y el desechable de PE; y dos juegos de fundas. El juego de fundas doradas tiene el precio corregido por el usuario: $20.000 COP. Los demás precios se toman del catálogo al crear el video. Las figuras de anime están excluidas.

- `NavidadBGA-reel-estados.mp4`: versión con música instrumental original de campanillas y acordes suaves, sin voz.
- `NavidadBGA-vertical-sin-musica.mp4`: misma edición, sin pista de audio, para añadir otra música al compartir.
- `portada-reel.jpg`: imagen vertical para la portada.
- `pie-de-foto.txt`: texto sugerido para acompañarlo.
- `guion.json`: escenas, fotos de origen y precios.
- `verificacion.json`: comprobación de duración, dimensiones, fotogramas, audio y decodificación completa.

[Abrir y descargar desde el celular](https://zhulgon.github.io/Ventas_Navidad/reel/).

Abre directamente con los muñequitos luminosos. Papá Noel tiene el mayor número de modelos: verde y dorado, blanco y dorado, rojo clásico, el juego azul de dos figuras, gris y rojo con bastón, y el modelo con osito. Cada referencia ocupa su propia escena y muestra su precio y presentación de venta. Las fotos de estudio se conservan completas, sin tarjetas ni marcos. El fondo prolonga los colores de cada fotografía, con un acercamiento suave. Las transiciones pasan brevemente por un fondo liso: los productos y precios de dos escenas nunca se superponen. La música se sintetiza desde notas y armónicos en el script, sin utilizar pistas ni samples externos. Las fotografías originales del catálogo ya estaban editadas con IA.

## Volver a generar

Requiere Python, las dependencias de `requirements.txt` y las fuentes Georgia y Segoe UI de Windows. El script toma las fotos y los precios de `docs/catalogo.json` y actualiza también los archivos de `docs/reel`.

```powershell
py -3 -m pip install -r multimedia/requirements.txt
py -3 multimedia/crear_reel.py
```

La reproducción, el formato H.264, los 1.404 fotogramas y el audio del video entregado se verificaron antes de guardarlo. Los precios del video son una edición fija; para reflejar cambios posteriores del inventario hay que volver a generarlo.
