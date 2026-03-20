# middleware/request_context.py

import uuid
from datetime import datetime


def generate_request_id():

    year = datetime.utcnow().year
    short_id = str(uuid.uuid4())[:6]

    return f"DG-{year}-{short_id}"