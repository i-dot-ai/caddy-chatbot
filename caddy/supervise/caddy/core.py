from caddy.models.core import SupervisionEvent, ApprovalEvent
from caddy.utils.tables import responses_table

from datetime import datetime


def store_approver_received_timestamp(event: SupervisionEvent):
    # Updating response in DynamoDB
    responses_table.update_item(
        Key={"threadId": str(event["thread_id"])},
        UpdateExpression="set approverReceivedTimestamp=:t",
        ExpressionAttributeValues={":t": str(datetime.now())},
        ReturnValues="UPDATED_NEW",
    )


def store_approver_event(approval_event: ApprovalEvent):
    # Updating response in DynamoDB
    responses_table.update_item(
        Key={"threadId": str(approval_event.thread_id)},
        UpdateExpression="set approverEmail=:email, approved=:approved, approvalTimestamp=:atime, userResponseTimestamp=:utime, supervisorMessage=:sMessage",
        ExpressionAttributeValues={
            ":email": approval_event.approver_email,
            ":approved": approval_event.approved,
            ":atime": str(approval_event.approval_timestamp),
            ":utime": str(approval_event.user_response_timestamp),
            ":sMessage": approval_event.supervisor_message,
        },
        ReturnValues="UPDATED_NEW",
    )
