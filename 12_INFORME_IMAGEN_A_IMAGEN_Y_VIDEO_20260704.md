# Auditoría Perchance: imagen a imagen e imagen a vídeo

Fecha: 2026-07-04

## Resultado ejecutivo

- Imagen a imagen: técnicamente posible con el `text-to-image-plugin` oficial mediante `referenceImage`. Los modificadores comunitarios auditados no lo usan correctamente.
- Imagen a vídeo: no aparece un backend nativo de Perchance. La opción real encontrada es un `iframe` hacia Hugging Face Spaces que ejecuta WAN 2.2 I2V.
- El generador `pretty-ai-video-generator` no usa un modelo de vídeo. Genera imágenes independientes y las codifica localmente como WebM, con GIF como fallback.

## Imagen a imagen

### Contrato descubierto en `text-to-image-plugin`

El código oficial acepta:

```javascript
generateImage({
  prompt,
  negativePrompt,
  seed,
  resolution,
  guidanceScale,
  referenceImage: {
    url: referenceDataUrl,
    blur: 0.15
  }
})
```

Hallazgos verificables en `01_text-to-image-plugin.html`:

- `referenceImage.url` se incorpora al mensaje enviado al iframe privado del backend.
- Admite una URL evaluada, una URL `blob:` o datos transferidos por `postMessage` como data URL.
- `referenceImage.blur` se valida en el intervalo 0-1.
- Los parámetros funcionales visibles en este contrato son `prompt`, `negativePrompt`, `seed`, `resolution`, `guidanceScale`, `referenceImage`, `removeBackground`, `saveTitle` y `saveDescription`.
- No se observan `model`, `sampler` ni `steps` en el contrato del plugin oficial.

Precaución de implementación: el camino que recibe un objeto `Blob` directo parece tener un posible acceso a `url.startsWith(...)` cuando `url` aún no está definido. Para el prototipo conviene usar data URL o URL `blob:` y comprobarlo en ejecución.

### Generadores comunitarios auditados

- `ai-image-modifier`: lee la imagen con `FileReader`, pero llama `generateImage(fullPrompt)` sin pasar la imagen. Es texto a imagen disfrazado de modificador.
- `image-to-image`: contiene comentarios que reconocen que la API real no está implementada y devuelve la propia imagen subida como resultado simulado.
- `dz10cs63ln`: detecta caras localmente, construye un prompt textual y llama `generateImage(prompt)`; no transmite la imagen ni los descriptores faciales.
- `b6dr62ehqb`: simula operaciones de edición y genera por texto; tampoco utiliza `referenceImage`.
- `image-editor-ai` y `modify-image-v2`: son editores locales o visores, no img2img generativo.

Conclusión: no reutilizar estos generadores. Crear un panel propio que pase explícitamente `referenceImage` al plugin oficial.

## Imagen a vídeo

### Generadores falsos o meramente locales

- `pretty-ai-video-generator`: genera un máximo de 48 fotogramas llamando repetidamente a `text-to-image-plugin`, incrementa una semilla escrita dentro del prompt y luego crea WebM con `MediaRecorder`; usa GIF como fallback. No conserva identidad ni continuidad latente entre fotogramas.
- `image-to-video-loop-creator`: no genera movimiento. Reproduce en secuencia las imágenes subidas y graba el canvas como WebM.

### Opción real encontrada

El generador Perchance `41w7crj7pe` solo incrusta este servicio externo:

`https://huggingface.co/spaces/zerogpu-aoti/wan2-2-fp8da-aoti-faster`

El Space ejecuta realmente:

- `Wan-AI/Wan2.2-I2V-A14B-Diffusers`;
- entrada de una imagen y prompt de movimiento;
- salida MP4 a 16 FPS;
- duración aproximada de 0,5 a 5 segundos;
- dimensiones adaptadas entre 480 y 832 píxeles, con 640x640 para imágenes cuadradas;
- seed reproducible y aleatoria;
- 1-30 pasos;
- dos escalas de guidance para las etapas de ruido alto y bajo;
- ejecución en Hugging Face ZeroGPU.

El repositorio del Space llama `demo.queue().launch(mcp_server=True)`, por lo que declara una superficie MCP además de la interfaz Gradio. La integración Perchance observada no usa esa API: solo muestra el Space en un iframe.

### Riesgos y arquitectura recomendada

- La imagen se procesa en Hugging Face, no en Perchance.
- La disponibilidad depende de ZeroGPU, la cola compartida y los límites del Space.
- El propietario del Space puede cambiar código, modelo o disponibilidad.
- Para un prototipo rápido: iframe del Space, con aviso explícito de privacidad y dependencia externa.
- Para una aplicación controlada: backend propio o endpoint contratado que ejecute WAN I2V; Perchance quedaría solo como interfaz.

## Próxima prueba necesaria

1. Crear un prototipo mínimo img2img con `referenceImage` usando una imagen sintética.
2. Comparar `blur` 0, 0.15, 0.5 y 1 para medir conservación de identidad/composición.
3. Capturar la petición del iframe de `image-generation.perchance.org` sin exponer cookies ni tokens.
4. Probar WAN con una imagen sintética y registrar cola, tiempo, MP4, seed y parámetros efectivos.

No se ha subido ninguna imagen ni se ha iniciado generación durante esta auditoría.
