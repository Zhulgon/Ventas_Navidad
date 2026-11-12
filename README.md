# Cosas Navideñas

Plataforma local de reventa con panel de inventario, ventas y catálogo. Cada ficha indica si se vende por unidad o por juego y cuántas piezas incluye.

## Catálogo en internet

Enlace para compartir: [Cosas Navideñas](https://zhulgon.github.io/Ventas_Navidad/).

GitHub Pages publica la carpeta `docs` de la rama `main`. El catálogo permite buscar, revisar fotos y precios, armar una selección y compartirla. Funciona aunque el equipo esté apagado. Las compras se acuerdan con el vendedor; seleccionar artículos no reserva existencias.

En **Mi selección → Pedir por Instagram**, el cliente obtiene un mensaje con los artículos, códigos, cantidades, precios y total. El resumen se copia y el botón **Abrir Instagram** lleva a `@navidadbga`; el cliente pulsa **Mensaje**, pega el pedido y lo envía. Si el navegador bloquea el portapapeles, puede copiar el texto manualmente. El carrito se conserva y la venta se registra en el panel cuando se confirme la compra.

El panel de gestión y el registro de ventas funcionan en la plataforma local. La web muestra el inventario de la última publicación. Para actualizarla después de cambiar precios, fotos o existencias, ejecuta desde esta carpeta:

```powershell
py -3 exportar_catalogo.py
git add docs
git commit -m "Actualizar catalogo publico"
git push
```

La exportación incluye las referencias visibles, sus precios, disponibilidad y fotografías. Los costos de compra, las notas de ventas y los datos de clientes se quedan fuera de `docs`. Los archivos de respaldo del repositorio se mantienen aparte del catálogo publicado.

## Video para estados y reels

[Ver y descargar el video desde el celular](https://zhulgon.github.io/Ventas_Navidad/reel/). La carpeta `multimedia` conserva el MP4 vertical de 24,6 segundos, la versión sin música, la portada y el guion para volver a generarlo. La edición actual destaca cinco referencias, con fotos más grandes, menos texto y un ritmo más pausado.

## Abrir en Windows

Ejecuta `Abrir plataforma.cmd`. Requiere Python 3.10 o posterior y abre [el panel](http://127.0.0.1:8131/) en el navegador. Mantén abierta la consola mientras uses la plataforma. También puedes iniciar desde PowerShell con `py -3 plataforma.py --abrir`.

La primera ejecución recupera el inventario guardado en `datos/inventario-inicial.sqlite3`, con los precios, cantidades, fotos y juegos de la entrega. Después, la aplicación trabaja con su base local en `.datos/reventa.sqlite3`.

Los Excel de compras están en `datos/fuentes`. Puedes importar una versión actualizada desde el panel. La carga toma los juegos comprados como stock inicial registrado. Los costos y precios se expresan en pesos colombianos por la presentación de venta indicada en la ficha.

## Operación diaria

1. **Importar Excel.** Guarda los cambios en el archivo, selecciona su versión reciente en el panel, revisa las filas y confirma. Conserva los encabezados y asigna un ID único a cada referencia. Para aumentar la compra del mismo artículo, cambia el total acumulado de juegos en su fila. Usa **Agregar artículo** para registrar compras directamente en la plataforma.
2. **Preparar el catálogo.** Define el precio de venta y activa **Mostrar en la vista cliente** para cada artículo listo. **Vista del catálogo** incluye borradores. **Vista cliente** muestra las referencias activadas y permite armar una selección. Puedes configurar el WhatsApp del negocio en **Contacto**.
3. **Registrar ventas.** Ingresa cantidad y precio real. El stock baja automáticamente. Al anular una venta, la cantidad regresa al inventario y el registro permanece en el historial. La ganancia bruta usa el costo guardado al registrar la venta.

Una reimportación aplica los campos que cambiaron en Excel desde la última carga. Los campos intactos conservan los ajustes hechos en la plataforma. Las ventas y los artículos omitidos del archivo se conservan. Se toma la primera foto JPG, PNG o WebP anclada en la columna B de cada fila. También puedes cargar la foto desde la ficha.

Las versiones de `fotos-estudio` se usan como portadas cuando coinciden con la referencia del producto. En el detalle puedes alternar entre el estudio editado con IA y la referencia del proveedor. Si cargas otra foto, esa nueva referencia pasa a ser la portada.

Los gnomos luminosos se venden por unidad a $10.000 COP o en juego de tres colores a $25.000 COP. El juego utiliza un dorado, un gris y un rojo del mismo inventario. Su disponibilidad y costo se calculan con esas unidades. Al venderlo se descuentan los tres muñecos, y al anular la venta se reponen. El resumen del inventario cuenta las unidades físicas.

El panel y la vista cliente funcionan en este equipo. El historial, el catálogo, las fotos y los ajustes se guardan en `.datos/reventa.sqlite3`. Para respaldar los datos, cierra la consola y copia esa base a un lugar seguro.
