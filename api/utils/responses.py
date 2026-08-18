from rest_framework.response import Response
from rest_framework import status


def success_response(data, status_code=status.HTTP_200_OK, meta=None):
    body = {"success": True, "data": data}
    if meta is not None:
        body["meta"] = meta
    return Response(body, status=status_code)


def error_response(code, message, status_code=status.HTTP_400_BAD_REQUEST, details=None):
    if code == "VALIDATION_ERROR" and details and isinstance(details, dict):
        if "username" in details:
            err = details["username"]
            err_msg = err[0] if isinstance(err, list) and err else str(err)
            if "already exists" in err_msg.lower() or "taken" in err_msg.lower() or "استفاده شده" in err_msg:
                message = "Username is already taken."
            elif message in ("اطلاعات ارسالی نامعتبر است.", "Invalid request data.", "Invalid profile data."):
                message = f"Username error: {err_msg}"
        elif "email" in details:
            err = details["email"]
            err_msg = err[0] if isinstance(err, list) and err else str(err)
            if "already exists" in err_msg.lower() or "registered" in err_msg.lower() or "ثبت‌نام کرده" in err_msg:
                message = "Email is already registered."
            elif message in ("اطلاعات ارسالی نامعتبر است.", "Invalid request data.", "Invalid profile data."):
                message = f"Email error: {err_msg}"
        elif message == "اطلاعات ارسالی نامعتبر است.":
            message = "Invalid request data."

    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return Response({"success": False, "error": error}, status=status_code)


def no_content_response():
    return Response(status=status.HTTP_204_NO_CONTENT)
