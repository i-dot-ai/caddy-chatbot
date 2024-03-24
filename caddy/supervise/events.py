import os
import json
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime
from responses import (
    send_message_to_supervisor_space,
    send_message_to_adviser_space,
    update_message_in_supervisor_space,
    update_message_in_adviser_space,
    delete_message_in_adviser_space,
    respond_to_supervisor_thread,
)
from utils import (
    create_supervision_card,
    create_updated_supervision_card,
    create_supervision_request_card,
    create_approved_card,
    create_rejected_card,
    success_dialog,
    failed_dialog,
    get_user_to_add_details_dialog,
    get_user_to_remove_details_dialog,
    user_list_dialog,
    get_supervisor_response_dialog,
)
from models import (
    User,
    SupervisionEvent,
    ApprovalEvent,
    store_approver_received_timestamp,
    store_approver_event,
    responses_table,
)
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from survey import run_survey

patch_all()

dynamodb = boto3.resource("dynamodb")
users = dynamodb.Table(os.getenv("USERS_TABLE_NAME"))


@xray_recorder.capture()
def receive_new_ai_response(event: SupervisionEvent):
    initial_query = event["llmPrompt"]
    ai_response = event["llm_answer"]
    user = event["user"]
    llm_response_json = event["llm_response_json"]
    conversation_id = event["conversation_id"]
    response_id = event["response_id"]
    message_id = event["message_id"]
    thread_id = event["thread_id"]

    supervisor_space = get_designated_supervisor_space(userId=user)

    match supervisor_space:
        case "Unknown":
            update_message_in_adviser_space(
                space_id=conversation_id,
                message_id=message_id,
                response_type="text",
                message={
                    "text": "For this query my response requires your supervisors approval before I can send it to you but it doesn't look like your supervisor has registered you to use my support yet, *please speak to a supervisor in order to get set up*"
                },
            )
        case other:
            (
                request_awaiting,
                request_approved,
                request_rejected,
            ) = create_supervision_request_card(
                user_identifier=user, initial_query=initial_query
            )

            (
                new_request_thread,
                new_request_message_id,
            ) = send_message_to_supervisor_space(
                space_id=supervisor_space, message=request_awaiting
            )

            card = create_supervision_card(
                card_for_approval=llm_response_json,
                conversation_id=conversation_id,
                response_id=response_id,
                message_id=message_id,
                thread_id=thread_id,
                new_request_message_id=new_request_message_id,
                request_approved=request_approved,
                request_rejected=request_rejected,
                user_email=user,
            )

            respond_to_supervisor_thread(
                space_id=supervisor_space, message=card, thread_id=new_request_thread
            )

            store_approver_received_timestamp(
                event=event, timestamp=datetime.now(), table=responses_table
            )


@xray_recorder.capture()
def received_approval(event):
    card = json.loads(event["common"]["parameters"]["aiResponse"])
    users_space = event["common"]["parameters"]["conversationId"]
    approver = event["user"]["email"]
    response_id = event["common"]["parameters"]["responseId"]
    thread_id = event["common"]["parameters"]["threadId"]
    supervisor_space = event["space"]["name"].split("/")[1]
    message_id = event["message"]["name"].split("/")[3]
    supervisor_card = {"cardsV2": event["message"]["cardsV2"]}
    user_message_id = event["common"]["parameters"]["messageId"]
    request_message_id = event["common"]["parameters"]["newRequestId"]
    request_card = json.loads(event["common"]["parameters"]["requestApproved"])
    user_email = event["common"]["parameters"]["userEmail"]

    approved_card = create_approved_card(card=card, approver=approver)

    print(f"### APPROVED CARD \n\n {approved_card} \n\n ###END OF APPROVED CARD")

    updated_supervision_card = create_updated_supervision_card(
        supervision_card=supervisor_card,
        approver=approver,
        approved=True,
        supervisor_message="",
    )
    update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=message_id,
        new_message=updated_supervision_card,
    )

    update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=request_message_id,
        new_message=request_card,
    )

    update_message_in_adviser_space(
        space_id=users_space,
        message_id=user_message_id,
        response_type="text",
        message={"text": "*Status:* _*Completed*_"},
    )

    update_message_in_adviser_space(
        space_id=users_space,
        message_id=user_message_id,
        response_type="cardsV2",
        message=approved_card,
    )

    approval_event = ApprovalEvent(
        response_id=response_id,
        thread_id=thread_id,
        approver_email=approver,
        approved=True,
        approval_timestamp=event["eventTime"],
        user_response_timestamp=datetime.now(),
        supervisor_message=None,
    )
    store_approver_event(approval_event, table=responses_table)

    run_survey(user_email=user_email, adviser_space_id=users_space, thread_id=thread_id)


@xray_recorder.capture()
def received_rejection(event):
    supervisor_card = {"cardsV2": event["message"]["cardsV2"]}
    users_space = event["common"]["parameters"]["conversationId"]
    approver = event["user"]["email"]
    response_id = event["common"]["parameters"]["responseId"]
    supervisor_space = event["space"]["name"].split("/")[1]
    message_id = event["message"]["name"].split("/")[3]
    user_message_id = event["common"]["parameters"]["messageId"]
    supervisor_message = event["common"]["formInputs"]["supervisorResponse"][
        "stringInputs"
    ]["value"][0]
    thread_id = event["common"]["parameters"]["threadId"]
    request_message_id = event["common"]["parameters"]["newRequestId"]
    request_card = json.loads(event["common"]["parameters"]["requestRejected"])
    user_email = event["common"]["parameters"]["userEmail"]

    update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=request_message_id,
        new_message=request_card,
    )

    update_message_in_adviser_space(
        space_id=users_space,
        message_id=user_message_id,
        response_type="text",
        message={"text": f"*Status:* _*AI response rejected by {approver}*_"},
    )

    send_message_to_adviser_space(
        response_type="text",
        space_id=users_space,
        thread_id=thread_id,
        message=f"*{approver} says:* \n\n {supervisor_message}",
    )

    updated_supervision_card = create_updated_supervision_card(
        supervision_card=supervisor_card,
        approver=approver,
        approved=False,
        supervisor_message=supervisor_message,
    )
    update_message_in_supervisor_space(
        space_id=supervisor_space,
        message_id=message_id,
        new_message=updated_supervision_card,
    )

    rejection_event = ApprovalEvent(
        response_id=response_id,
        thread_id=thread_id,
        approver_email=approver,
        approved=False,
        approval_timestamp=event["eventTime"],
        user_response_timestamp=datetime.now(),
        supervisor_message=supervisor_message,
    )
    store_approver_event(rejection_event, table=responses_table)

    run_survey(user_email=user_email, adviser_space_id=users_space, thread_id=thread_id)

    return success_dialog()


@xray_recorder.capture()
def get_user_details(type: str):
    match type:
        case "Add":
            return get_user_to_add_details_dialog()
        case "Remove":
            return get_user_to_remove_details_dialog()


@xray_recorder.capture()
def add_user(event):
    userEmail = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]
    userRole = event["common"]["formInputs"]["role"]["stringInputs"]["value"][0]
    supervisionSpaceId = event["space"]["name"].split("/")[1]

    match userRole:
        case "Supervisor":
            isApprover = True
        case "Adviser":
            isApprover = False

    try:
        user = User(
            user_email=userEmail,
            is_approver=isApprover,
            is_super_user=False,
            created_at=datetime.now(),
            supervision_space_id=supervisionSpaceId,
        )

        users.put_item(
            Item={
                "userEmail": user.user_email,
                "isApprover": user.is_approver,
                "isSuperUser": False,
                "createdAt": user.created_at.isoformat(),
                "supervisionSpaceId": user.supervision_space_id,
            }
        )

        return success_dialog()
    except Exception as error:
        return failed_dialog(error)


@xray_recorder.capture()
def remove_user(event):
    userEmail = event["common"]["formInputs"]["email"]["stringInputs"]["value"][0]

    try:
        users.delete_item(Key={"userEmail": userEmail})
        return success_dialog()
    except Exception as error:
        return failed_dialog(error)


@xray_recorder.capture()
def list_users(event):
    supervisionSpaceId = event["space"]["name"].split("/")[1]
    supervision_space_name = event["space"]["displayName"]

    response = users.scan(
        FilterExpression=Attr("supervisionSpaceId").eq(supervisionSpaceId)
    )

    user_list = response["Items"]

    supervision_users = []

    for user in user_list:
        match user["isApprover"]:
            case False:
                role = "Adviser"
            case True:
                role = "Supervisor"
        user_info = f"{user['userEmail']}: {role}"
        supervision_users.append(f"{user_info}\n")

    supervision_users = "".join(supervision_users)

    return user_list_dialog(
        supervision_users=supervision_users, space_display_name=supervision_space_name
    )


@xray_recorder.capture()
def get_designated_supervisor_space(userId: str):
    user_details_response = users.get_item(Key={"userEmail": userId})

    if "Item" in user_details_response:
        return user_details_response["Item"]["supervisionSpaceId"]
    else:
        print("No supervisor space found for user")
        return "Unknown"


@xray_recorder.capture()
def get_supervisor_response(event):
    conversation_id = event["common"]["parameters"]["conversationId"]
    response_id = event["common"]["parameters"]["responseId"]
    message_id = event["common"]["parameters"]["messageId"]
    thread_id = event["common"]["parameters"]["threadId"]
    new_request_message_id = event["common"]["parameters"]["newRequestId"]
    request_rejected = event["common"]["parameters"]["requestRejected"]
    user_email = event["common"]["parameters"]["userEmail"]

    return get_supervisor_response_dialog(
        conversation_id,
        response_id,
        message_id,
        thread_id,
        new_request_message_id,
        request_rejected,
        user_email,
    )


@xray_recorder.capture()
def introduce_caddy_supervisor(event):
    match event["space"]["type"]:
        case "DM":
            return json.dumps(
                {
                    "text": "Hi, I'm the supervisor assistant for Caddy! Caddy is an AI support for Citizens Advice advisers. \n *To get started you will need to register the advisers into your supervision space so their messages come to you, you can do this by typing `/addUser` into the chat, other user management functionality can be seen using /help*"
                }
            )
        case "ROOM":
            return json.dumps(
                {
                    "text": f"Hi, thank you for adding me to {event['space']['displayName']}, I'm the supervisor assistant for Caddy! Caddy is an AI support for Citizens Advice advisers. \n\nCaddy uses information from the below sites to form answers: \nGOV UK \nCitizens Advice \nAdviserNet \n\n*To get started you will need to register the advisers into your supervision space so their messages come to you, you can do this by typing `/addUser` into the chat, other user management functionality can be seen using `/help`*"
                }
            )
