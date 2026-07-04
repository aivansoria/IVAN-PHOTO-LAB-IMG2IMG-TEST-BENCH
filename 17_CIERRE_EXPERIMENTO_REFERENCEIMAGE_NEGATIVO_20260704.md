# Cierre del experimento `referenceImage`

Fecha: 2026-07-04

## Resultado

El experimento es técnicamente válido y funcionalmente negativo para el objetivo de conservar identidad facial en distintas posiciones.

La importación correcta sigue siendo:

```perchance
generateImage = {import:text-to-image-plugin}
```

No se ha localizado un plugin oficial separado llamado `image-to-image-plugin`. El propio `text-to-image-plugin` acepta `referenceImage.url` y `referenceImage.blur`, por lo que la fotografía sí se envió al backend.

## Lo demostrado

- la imagen de referencia se transmitió;
- `blur`, seed, resolución y guidance se enviaron de forma constante;
- el backend generó una persona diferente;
- `referenceImage` condiciona la generación, pero no bloquea identidad ni pose;
- Perchance no expone embeddings faciales, InstantID, PuLID, PhotoMaker, IP-Adapter FaceID ni ControlNet/OpenPose.

## Correcciones documentales del banco

- la matriz reinicia historial y contador;
- la exportación omite Data URLs;
- se muestran nombre, MIME, bytes y dimensiones de la referencia;
- se advierte cuando el archivo supera 10 MB;
- cada tarjeta muestra índice, blur, seed, guidance, resolución y tiempo;
- la llamada a `generateImage` y el contrato `referenceImage` permanecen sin cambios.

## Decisión

Cerrar esta vía como no apta para el servicio principal de identidad + pose. Conservar el banco únicamente como prueba reproducible del contrato de Perchance.
