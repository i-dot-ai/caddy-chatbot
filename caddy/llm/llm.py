import json

from caddy import core as caddy
from caddy.services.evaluation.core import execute_optional_modules
from integrations.google_chat.core import GoogleChat


def lambda_handler(event, context):
    match event["source_client"]:
        case "Google Chat":
            google_chat = GoogleChat()

            (
                modules_to_use,
                module_outputs_json,
                continue_conversation,
                control_group_message,
            ) = execute_optional_modules(
                event, execution_time="before_message_processed"
            )

            message_query = caddy.format_chat_message(
                event, modules_to_use, module_outputs_json
            )

            caddy.store_message(message_query)
            caddy.store_evaluation_module(
                thread_id=message_query.thread_id,
                user_arguments=message_query.user_arguments,
                argument_output=message_query.argument_output,
            )

            if continue_conversation is False:
                google_chat.update_message_in_adviser_space(
                    message_query.space_id,
                    message_query.message_id,
                    {"text": control_group_message},
                )
                return

            module_outputs_json = json.loads(module_outputs_json)
            for output in module_outputs_json.values():
                if isinstance(output, dict) and output.get("end_interaction"):
                    return

            chat_history = caddy.get_chat_history(message_query)

            google_chat.update_message_in_adviser_space(
                space_id=message_query.conversation_id,
                message_id=message_query.message_id,
                message=google_chat.messages["GENERATING_RESPONSE"],
            )

            llm_response = caddy.query_llm(message_query, chat_history)

            response_card = google_chat.create_card(llm_response)
            response_card = json.dumps(response_card)

            llm_response.response_card = response_card

            caddy.store_response(llm_response)

            supervision_event = caddy.format_supervision_event(
                message_query, llm_response
            )

            google_chat.update_message_in_adviser_space(
                space_id=message_query.conversation_id,
                message_id=message_query.message_id,
                message=google_chat.messages["AWAITING_APPROVAL"],
            )

            caddy.store_user_thanked_timestamp(llm_response)

            caddy.send_for_supervisor_approval(supervision_event)
        case "Microsoft Teams":
            raise Exception("Unsupported Source Client")
        case "Caddy Local":
            """
            TODO - Add Caddy tests
            """
            return "LLM Invoke Test"
        case _:
            raise Exception("Unsupported Source Client")
