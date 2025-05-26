from .client import get_ai_client
from .constants import DEFAULT_MODEL, EXTRA_HEADERS

# def get_ai_response(prompt, model=DEFAULT_MODEL, headers=EXTRA_HEADERS):
#     client = get_ai_client()
    
#     try:
#         completion = client.chat.completions.create(
#             extra_headers=headers,
#             model=model,
#             messages=[{"role": "user", "content": prompt}]
#         )
#         return completion.choices[0].message.content
#     except Exception as e:
#         # Handle or log the error appropriately
#         raise

def get_ai_response(prompt, model=DEFAULT_MODEL):
    client = get_ai_client()
    
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content
    except Exception as e:
        # Handle or log the error appropriately
        raise