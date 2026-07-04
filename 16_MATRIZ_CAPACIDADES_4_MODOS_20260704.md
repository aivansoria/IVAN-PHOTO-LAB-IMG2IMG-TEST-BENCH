# Matriz de capacidades: texto/foto/vídeo

Fecha: 2026-07-04

## Regla de arquitectura

La futura página única puede reunir cuatro modos de interfaz, pero no debe fingir que todos pertenecen al mismo backend. Cada modo debe declarar el motor real, sus parámetros efectivos, el destino de los datos y sus limitaciones.

## Matriz ejecutiva

| Modo | Estado auditado | Motor real | Viabilidad actual |
|---|---|---|---|
| Texto → foto | Validado | `text-to-image-plugin` de Perchance | Sí, nativo |
| Foto → foto | Parcial | `text-to-image-plugin` con `referenceImage` | Sí para referencia visual; no para identidad/pose fiables |
| Foto → vídeo | Validado externamente | WAN 2.2 I2V 14B en Hugging Face ZeroGPU | Sí, mediante servicio externo |
| Texto → vídeo | No validado | Ningún backend real confirmado en la auditoría | No integrar todavía |

## 1. Texto → foto

### Parámetros que llegan al backend de Perchance

- `prompt`
- `negativePrompt`
- `seed`
- `resolution`: `512x512`, `512x768`, `768x512`, `768x768`
- `guidanceScale`: entero de 1 a 30
- `saveTitle`
- `saveDescription`
- `removeBackground`

`removeBackground` utiliza `briaai/RMBG-1.4` mediante Transformers en el navegador después de generar la imagen; no es un modelo alternativo de generación.

### Controles que no están en el contrato real

- `model`
- `sampler`
- `steps`
- `cfgScale`
- `upscale`
- `denoise`
- resoluciones 4K o personalizadas

La muestra `5yf90s8rdo` declara SD XL, SD 1.5, Realistic Vision, DreamShaper, Deliberate, Anything y OpenJourney, además de sampler, steps, CFG, upscale y denoise. El framework reenvía ese objeto al plugin, pero `text-to-image-plugin` solo construye la carga útil con los campos admitidos. Esos nombres de modelo y controles no seleccionan modelos del backend.

Las opciones de estilo, iluminación, calidad y atmósfera sí tienen efecto únicamente porque añaden texto al prompt o al negative prompt.

## 2. Foto → foto

### Contrato real descubierto

```javascript
referenceImage: {
  url: referenceDataUrl,
  blur: valueBetweenZeroAndOne
}
```

El plugin transmite la referencia al iframe privado de `image-generation.perchance.org`. Esto prueba condicionamiento por imagen, no preservación biométrica.

### Lo que no expone

- embedding facial;
- InstantID, PuLID, PhotoMaker o IP-Adapter FaceID;
- ControlNet/OpenPose;
- máscara de inpainting;
- fuerza de identidad separada;
- fuerza de pose;
- selección de modelo img2img;
- entrenamiento LoRA de una persona.

Conclusión: sirve para estudiar cuánto influye una imagen de referencia, pero no cumple por sí solo el objetivo de mantener la misma cara en distintas posiciones.

## 3. Foto → vídeo

### Servicio real localizado

El generador Perchance `41w7crj7pe` es un wrapper por iframe de:

`zerogpu-aoti/wan2-2-fp8da-aoti-faster`

Motor declarado por el código del Space:

- `Wan-AI/Wan2.2-I2V-A14B-Diffusers`;
- Lightning LoRA;
- cuantización FP8;
- salida MP4;
- 16 FPS;
- 8-80 fotogramas del modelo;
- duración aproximada 0,5-5 segundos;
- dimensiones adaptadas entre 480 y 832 píxeles;
- seed;
- 1-30 pasos;
- negative prompt;
- guidance para etapa de ruido alto y bajo.

La imagen sale de Perchance y se procesa en Hugging Face. La cola, disponibilidad y límites dependen de ZeroGPU.

## 4. Texto → vídeo

No existe aún un backend real confirmado en esta auditoría.

`pretty-ai-video-generator` no cuenta: genera fotogramas independientes con texto → foto y los graba localmente como WebM/GIF. No hay modelo temporal ni continuidad entre fotogramas.

Alternativa provisional posible, pero no equivalente a texto → vídeo nativo:

1. generar una imagen inicial con texto → foto;
2. enviar esa imagen y un prompt de movimiento a WAN I2V.

Esta tubería debe llamarse `texto → imagen → vídeo`, no ocultarse como un modelo T2V.

## Orden de construcción recomendado

1. Construir primero texto → foto con solo parámetros reales.
2. Añadir foto → foto como modo experimental y declarar que no bloquea identidad.
3. Integrar foto → vídeo como módulo externo WAN, aislado del backend Perchance.
4. Auditar y seleccionar un backend T2V real antes de crear su interfaz.
5. Solo después investigar un motor específico de identidad + pose para el servicio fotográfico principal.

## Criterio de aceptación para la página única

Cada resultado debe registrar:

- modo;
- motor y proveedor reales;
- parámetros enviados;
- seed devuelto o solicitado;
- tiempo;
- URL o archivo resultante;
- si la entrada salió de Perchance;
- nivel de garantía: experimental, externo o validado.

No debe mostrarse ningún selector si su valor no cambia la petición real del motor correspondiente.
