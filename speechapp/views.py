import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .webrtc_server import handle_offer


@csrf_exempt
async def webrtc_offer(request: HttpRequest) -> JsonResponse:
    params = json.loads(request.body or "{}")
    answer = await handle_offer(params)
    return JsonResponse(answer)
