def envelope_postprocessing_hook(result, generator, request, public):
    """
    OpenAPI postprocessing hook for drf_spectacular.
    Automatically wraps operation response schemas in standard JSON response envelopes:
    - 2xx: { "success": true, "data": <original_schema>, "meta": {...} }
    - 4xx/5xx: { "success": false, "error": { "code": "...", "message": "...", "details": {...} } }
    """
    paths = result.get("paths", {})

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue

            responses = operation["responses"]
            for status_code, response_obj in responses.items():
                if not isinstance(response_obj, dict):
                    continue

                content = response_obj.get("content", {})
                if "application/json" not in content:
                    continue

                json_schema = content["application/json"].get("schema")
                if not json_schema:
                    continue

                code_int = int(status_code) if str(status_code).isdigit() else 200

                if 200 <= code_int < 300:
                    wrapped_schema = {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "default": True,
                                "example": True,
                            },
                            "data": json_schema,
                        },
                        "required": ["success", "data"],
                    }
                    content["application/json"]["schema"] = wrapped_schema
                elif 400 <= code_int < 600:
                    wrapped_schema = {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "default": False,
                                "example": False,
                            },
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string",
                                        "example": "VALIDATION_ERROR",
                                    },
                                    "message": {
                                        "type": "string",
                                        "example": "Invalid request data.",
                                    },
                                    "details": {
                                        "type": "object",
                                        "nullable": True,
                                    },
                                },
                                "required": ["code", "message"],
                            },
                        },
                        "required": ["success", "error"],
                    }
                    content["application/json"]["schema"] = wrapped_schema

    return result
