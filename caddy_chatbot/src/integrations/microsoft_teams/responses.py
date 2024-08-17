from fastapi import status
from fastapi.responses import JSONResponse, Response

# --- Status Responses --- #
NO_CONTENT = Response(status_code=status.HTTP_204_NO_CONTENT)
ACCEPTED = Response(status_code=status.HTTP_202_ACCEPTED)
OK = Response(status_code=status.HTTP_200_OK)
