import concurrent.futures
import logging
import uuid

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .agents import run_pipeline_for_session
from .models import PromptSession
from .serializers import CreateSessionSerializer
from .session_utils import delete_prompt_session

logger = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


@api_view(["POST"])
def create_session(request):
    """POST /api/sessions/ — create row and start pipeline (API key stays in RAM only)."""
    ser = CreateSessionSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    data = ser.validated_data
    session = PromptSession.objects.create(raw_prompt=data["prompt"])

    _executor.submit(
        run_pipeline_for_session,
        session.session_id,
        data["provider"],
        data["api_key"],
        data.get("model_name"),
    )

    return Response(
        {"session_id": str(session.session_id)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "DELETE"])
def session_detail(request, session_id):
    """GET poll status / result; DELETE wipe local row."""
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return Response(
            {"detail": "Invalid session id."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "DELETE":
        if not delete_prompt_session(sid):
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    session = PromptSession.objects.filter(pk=sid).first()
    if session is None:
        return Response(
            {"detail": "Not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "session_id": str(session.session_id),
            "status": session.status,
            "final_rehydrated_text": session.final_rehydrated_text,
            "error_message": session.error_message,
        }
    )
