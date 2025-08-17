from rest_framework.response import Response

def success(result=None, message="성공", status_code=200, code="COMMON_200", meta=None):
    body = {
        "isSuccess": True,
        "message": message,
        "code": code
    }
    if meta is not None:
        body["meta"] = meta
    return Response(body, status=status_code)

def empty_list(message, code="COMMON_200"):
    return success(result=[], message=message, code=code, status_code=200, meta={"count": 0})