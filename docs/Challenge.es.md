# Agente comercial de AI

El proyecto consiste en desarrollar un bot que se apalanque de LLMs para simular el comportamiento de un agente comercial de Kavak. El bot se deberá disponibilizar por medio de una API en Python o Go.

La evaluación será realizada en función de su pragmatismo, capacidad de estructurar el problema, planteamiento de la solución, buenas prácticas de desarrollo, capacidad de priorizar y creatividad. La completitud no es un factor en la evaluación.

## El bot comercial deberá tener las siguientes capacidades

- Responder información básica sobre la propuesta de valor de Kavak.
- Dentro de lo posible se deberán reducir las alucinaciones dentro del chatbot
- El chatbot deberá ser capaz de manejar las complejidades del uso lenguaje natural para la interacción (por ejemplo, errores en la redacción de la marca y modelo por parte del usuario).
- Brindar recomendaciones de los autos disponibles en extracto del catálogo dadas las preferencias del cliente.
- Otorgar planes de financiamiento tomando como base el enganche, el precio del auto, una tasa de interés del 10% y plazos de financiamiento de entre 3 y 6 años.

## Como entregable del ejercicio esperamos lo siguiente

- Demo en vivo del bot conectado a whatsapp (como pista puedes crear una cuenta de Twilio y utilizar el sandbox).
- Diagrama de alto nivel sobre componentes y arquitectura.
- Diagrama sobre prompts/arquitectura de agentes/tools en caso de aplicar.
- Código en python o Go del bot.
- Propuesta de roadmap y backlog para llevar este bot a producción, algunas de las preguntas que deberá responder este roadmap son:
  - ¿Cómo pondrías esto en producción?
  - ¿Cómo evaluarías el desempeño del agente?
  - ¿Cómo probarías que una nueva versión del agente no tiene retroceso en su funcionalidad?

Sé tan creativo como gustes, recuerda que el objetivo final es desarrollar un bot que replique a un agente comercial, siéntete libre de proponer cualquier solución que te ayude a llegar a este objetivo.

Puedes versionar el bot, no es necesario desarrollar todas las capacidades listadas, únicamente considera que puedas cumplir con el entregable del ejercicio. Bonus points si en tu desarrollo logras garantizar reproducibilidad, es decir, generar un manual con el cual cualquier persona pueda instalar tu bot.

## Recursos

- Propuesta de valor de Kavak (utiliza la información contenida en este página):
<https://www.kavak.com/mx/blog/sedes-de-kavak-en-mexico>
- API Key temporal de Open AI:
sk-proj-...
- CSV de ejemplo para catálogo (adjunto en el correo).

*considera que esta API Key tiene un rate limit de 50,000 Tokens por minuto y únicamente tiene acceso a la versión default de gpt-3.5-turbo, gpt-4-turbo y gpt-4o.
