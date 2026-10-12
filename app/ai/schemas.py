"""Provider-neutral JSON schemas for grading responses."""

# JSON schema for structured output - forces the model to return valid JSON
RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "Score according to OMJ criteria (0, 2, 5, or 6 for etap2/3; 0, 1, or 3 for etap1)"
        },
        "feedback": {
            "type": "string",
            "description": "Constructive feedback in Polish explaining the score"
        },
        "issue_type": {
            "type": "string",
            "enum": ["none", "wrong_task", "injection"],
            "description": "Type of issue detected: none (normal), wrong_task (wrong problem), injection (manipulation attempt)"
        },
        "abuse_score": {
            "type": "integer",
            "description": "Confidence score 0-100 for abuse detection"
        }
    },
    "required": ["score", "feedback", "issue_type", "abuse_score"]
}
