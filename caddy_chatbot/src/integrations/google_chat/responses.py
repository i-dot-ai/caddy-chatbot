from fastapi import status
from fastapi.responses import JSONResponse, Response
from integrations.google_chat import content

# --- Status Responses --- #
NO_CONTENT = Response(status_code=status.HTTP_204_NO_CONTENT)
ACCEPTED = Response(status_code=status.HTTP_202_ACCEPTED)

# --- Text Responses --- #
DOMAIN_NOT_ENROLLED = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.DOMAIN_NOT_ENROLLED,
)

USER_NOT_ENROLLED = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.USER_NOT_ENROLLED,
)


INTRODUCE_CADDY_IN_DM = JSONResponse(
    status_code=status.HTTP_200_OK, content=content.INTRODUCE_CADDY_IN_DM
)

INTRODUCE_CADDY_SUPERVISOR_IN_DM = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.INTRODUCE_CADDY_SUPERVISOR_IN_DM,
)


def introduce_caddy_in_space(space_name):
    text = content.INTRODUCE_CADDY_IN_SPACE.format(space_name=space_name)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"text": text},
    )


def introduce_caddy_supervisor_in_space(space_name):
    text = content.INTRODUCE_CADDY_SUPERVISOR_IN_SPACE.format(space_name=space_name)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"text": text})


# --- Card Responses --- #

# TODO Add clean card responses

# --- Dialog Responses --- #

SUCCESS_DIALOG = JSONResponse(
    status_code=status.HTTP_200_OK,
    content=content.SUCCESS_DIALOG,
)
