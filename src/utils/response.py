import json


class LambdaResponse:
    """
    Standardizes what every Lambda returns.

    These Lambdas aren't sitting behind API Gateway, so the HTTP-style
    "statusCode" isn't strictly required for anything to work - but
    keeping every Lambda's return shape identical makes CloudWatch
    logs predictable and means we could bolt on API Gateway later
    without changing this shape.
    """

    @staticmethod
    def success(message: str, data: dict = None) -> dict:
        return {
            "statusCode": 200,
            "body": json.dumps({"message": message, "data": data or {}}),
        }

    @staticmethod
    def error(message: str, status_code: int = 500) -> dict:
        return {
            "statusCode": status_code,
            "body": json.dumps({"error": message}),
        }
