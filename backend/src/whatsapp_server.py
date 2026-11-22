import asyncio
import hmac
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

sys.path.append(str(Path(__file__).parent))

from agent import chat
from config import TwilioSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GENERIC_ERROR_RESPONSE = (
    "Lo siento, ocurrió un error procesando tu mensaje. Por favor, inténtalo más tarde."
)


def mask_phone_number(number: str) -> str:
    return f"****{number[-4:]}" if len(number) >= 4 else "****"


class SendMessageRequest(BaseModel):
    to_number: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str


class WhatsAppVehicleAssistant:
    def __init__(self):
        settings = TwilioSettings()

        try:
            self.twilio_client = Client(settings.account_sid, settings.auth_token)
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            raise

        self._whatsapp_number = settings.whatsapp_number

    def send_whatsapp_message(self, to_number: str, message: str) -> Dict[str, Any]:
        if not self.twilio_client:
            return {"success": False, "error": "Twilio client not initialized"}

        try:
            from_number = self._whatsapp_number
            if not from_number:
                return {
                    "success": False,
                    "error": "Twilio WhatsApp number not configured",
                }

            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"

            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"

            message_obj = self.twilio_client.messages.create(
                from_=from_number, body=message, to=to_number
            )

            logger.info(f"WhatsApp message sent successfully. SID: {message_obj.sid}")
            return {
                "success": True,
                "sid": message_obj.sid,
                "status": message_obj.status,
            }

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {type(e).__name__}")
            return {"success": False, "error": str(e)}

    def handle_whatsapp_message(self, from_number: str, message_body: str) -> str:
        try:
            logger.info(
                "Received WhatsApp message (%d chars) from %s",
                len(message_body),
                mask_phone_number(from_number),
            )
            response = self._handle_with_ai_agent(message_body)

            if len(response) > 1600:
                response = response[:1600] + "...\n\n[Respuesta truncada]"

            logger.info(
                "Sending WhatsApp response (%d chars) to %s",
                len(response),
                mask_phone_number(from_number),
            )
            return response

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {type(e).__name__}")
            return GENERIC_ERROR_RESPONSE

    @staticmethod
    def _handle_with_ai_agent(message: str) -> str:
        try:
            result = chat(message)
            if result["success"]:
                return str(result["response"])
            logger.error("Agent failed internally: %s", result.get("error"))
            return GENERIC_ERROR_RESPONSE

        except Exception as e:
            logger.error(f"Agent invocation failed: {type(e).__name__}")
            return GENERIC_ERROR_RESPONSE


assistant: WhatsAppVehicleAssistant | None = None


def _require_valid_twilio_signature(request: Request, params: dict) -> bool:
    auth_token = TwilioSettings().auth_token
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN is unset; rejecting unauthenticated webhook call")
        return False
    validator = RequestValidator(auth_token)
    return validator.validate(
        str(request.url), params, request.headers.get("X-Twilio-Signature", "")
    )


def create_fastapi_app() -> FastAPI:
    app = FastAPI(
        title="WhatsApp Vehicle Assistant",
        description="AI-powered vehicle search via WhatsApp using Twilio",
        version="1.0.0",
    )

    @app.post("/whatsapp/webhook")
    async def whatsapp_webhook(request: Request):
        """Handle incoming WhatsApp messages via webhook."""
        try:
            form_data = await request.form()
            message_body = form_data.get("Body", "")
            from_number = form_data.get("From", "")

            if not _require_valid_twilio_signature(request, dict(form_data)):
                return PlainTextResponse("Forbidden", status_code=403)

            if not message_body or not from_number:
                logger.warning("Received empty message or sender")
                return Response("OK", status_code=200)

            from_number = from_number.replace("whatsapp:", "")

            global assistant
            if not assistant:
                assistant = WhatsAppVehicleAssistant()

            response_text = await asyncio.to_thread(
                assistant.handle_whatsapp_message, from_number, message_body
            )

            twiml_response = MessagingResponse()
            twiml_response.message(response_text)

            return Response(content=str(twiml_response), media_type="text/xml")

        except Exception as e:
            logger.error(f"Error handling WhatsApp webhook: {type(e).__name__}")
            twiml_response = MessagingResponse()
            twiml_response.message(GENERIC_ERROR_RESPONSE)
            return Response(content=str(twiml_response), media_type="text/xml")

    @app.get("/whatsapp/webhook")
    async def whatsapp_webhook_verify(request: Request):
        """Handle webhook verification."""
        return PlainTextResponse(request.query_params.get("hub.challenge", ""))

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(status="healthy", service="whatsapp-vehicle-assistant")

    @app.post("/send-message")
    async def send_message(request: Request, request_data: SendMessageRequest):
        """Send a WhatsApp message via API."""
        api_key = TwilioSettings().send_message_api_key
        if not api_key:
            logger.warning("SEND_MESSAGE_API_KEY is unset; /send-message is disabled")
            raise HTTPException(
                status_code=503, detail="send-message endpoint is disabled"
            )
        if not hmac.compare_digest(api_key, request.headers.get("x-api-key", "")):
            logger.warning("Rejected /send-message call with a missing or wrong API key")
            raise HTTPException(status_code=403, detail="Invalid API key")

        try:
            global assistant
            if not assistant:
                assistant = WhatsAppVehicleAssistant()

            result = await asyncio.to_thread(
                assistant.send_whatsapp_message,
                request_data.to_number,
                request_data.message,
            )
            return result

        except Exception as e:
            logger.error(f"Error sending message: {type(e).__name__}")
            raise HTTPException(status_code=500, detail="Failed to send message")

    return app


def start_whatsapp_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    import uvicorn

    app = create_fastapi_app()

    print("🚀 Starting WhatsApp Vehicle Assistant Server (FastAPI)")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🔗 Webhook URL: http://{host}:{port}/whatsapp/webhook")
    print(f"❤️  Health Check: http://{host}:{port}/health")
    print(f"📤 Send Message API: http://{host}:{port}/send-message")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔧 ReDoc Documentation: http://{host}:{port}/redoc")
    print()
    print("Configure your Twilio WhatsApp webhook to point to the webhook URL above.")
    print("Make sure to set the following environment variables:")
    print("- TWILIO_ACCOUNT_SID")
    print("- TWILIO_AUTH_TOKEN")
    print("- TWILIO_WHATSAPP_NUMBER")
    print("- SEND_MESSAGE_API_KEY (enables POST /send-message)")
    print()

    uvicorn.run(app, host=host, port=port, log_level="debug" if debug else "info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WhatsApp Vehicle Assistant Server")

    parser.add_argument("--host", default="0.0.0.0", help="Host for WhatsApp server")
    parser.add_argument("--port", type=int, default=5000, help="Port for WhatsApp server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    start_whatsapp_server(host=args.host, port=args.port, debug=args.debug)
