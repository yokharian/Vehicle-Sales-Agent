"""
AI Agent for vehicle search and document queries using LangChain agents.

This agent can:
- Search vehicle catalogs with fuzzy matching
- Find relevant documents using semantic search
- Provide intelligent recommendations based on user preferences
"""

import sys
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI


sys.path.append(str(Path(__file__).parent))

from config import OPENROUTER_BASE_URL, AgentSettings
from tools.catalog_search import catalog_search_tool
from tools.document_search import document_search_tool


SYSTEM_PROMPT = """Eres un asistente virtual especializado en búsqueda de vehículos y atención al cliente para una empresa automotriz que actúa como agente comercial de Kavak. Asistes al cliente en su búsqueda y respondes preguntas generales sobre la empresa, siempre usando solo las herramientas disponibles.

HERRAMIENTAS DISPONIBLES:
- 'catalog_search': úsala para encontrar vehículos según los criterios del usuario, incluso con errores ortográficos, emplea la entrada del usuario directamente, sin modificarla o corregirla previamente.
- 'document_search': utilízala únicamente para responder sobre la empresa (sedes, servicios, cultura, propuesta de valor). No la uses para preguntas sobre vehículos.

INSTRUCCIONES:
1. Si el usuario pide ayuda para encontrar un coche, usa solo 'catalog_search' y muestra los resultados más relevantes. No justifiques recomendaciones.
2. Si pregunta sobre la empresa, usa solo 'document_search' para obtener la información.
3. Si no encuentras respuesta clara en catálogo o documentos, responde: "Lo siento, no tengo esa información disponible en este momento."
4. Si el mensaje es muy vago y no puedes determinar la petición, solicita amablemente que vuelva a intentarlo o dé más detalles.
5. Si no estás seguro de la intención del usuario, mantén la conversación activa de manera servicial: haz una pregunta de confirmación para entender mejor la solicitud, ofrece opciones relevantes relacionadas con vehículos o con la empresa, y muestra disposición para ayudar con sugerencias que puedan orientar al usuario.
6. Nunca inventes información; responde solo con datos confirmados por tus herramientas, manteniendo un tono profesional y alineado a la cultura de la empresa.

CONTEXTO OPERACIONAL:
- Canal: WhatsApp conversacional
- Audiencia: Clientes potenciales interesados en comprar vehículos o conocer más sobre la empresa
- Comportamiento: Comprender entradas con errores o expresiones vagas y responder de forma directa en lo comercial y cordial en lo informativo."""

SETTINGS = AgentSettings()


def build_chat_model(model_name: str) -> ChatOpenAI:
    """Build a chat model from the configured provider."""
    common_kwargs = {"temperature": 0.1, "max_tokens": 2000}
    if SETTINGS.model_provider == "openrouter":
        if not SETTINGS.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        return ChatOpenAI(
            model=model_name,
            api_key=SETTINGS.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            **common_kwargs,
        )
    if not SETTINGS.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    return ChatOpenAI(model=model_name, api_key=SETTINGS.openai_api_key, **common_kwargs)


standard_model = build_chat_model(SETTINGS.default_model)

tools = [catalog_search_tool, document_search_tool]

agent = create_agent(
    name="commercial-agent",
    model=standard_model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    debug=SETTINGS.debug,
)


def chat(message: str) -> dict[str, Any]:
    """
    Chat with the agent.

    Args:
        message: User message/query

    Returns:
        Dictionary containing response and metadata
    """
    try:
        inputs = {"messages": [{"role": "user", "content": message}]}

        response = agent.invoke(inputs)

        messages = response.get("messages", [])
        if messages:
            final_message = messages[-1]
            if hasattr(final_message, "content"):
                content = final_message.content
            else:
                content = str(final_message)
        else:
            content = "I couldn't generate a response."

        return {"response": content, "messages": messages, "success": True}
    except Exception as e:
        return {
            "response": f"Sorry, I encountered an error: {e!s}",
            "messages": [],
            "success": False,
            "error": str(e),
        }
