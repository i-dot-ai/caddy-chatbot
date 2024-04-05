import json

from caddy import core as caddy
from caddy.services.evaluation.core import execute_optional_modules
from integrations.google_chat.core import GoogleChat


def lambda_handler(event, context):
    match event["source_client"]:
        case "Google Chat":
            google_chat = GoogleChat()

            existing_call, values, survey_complete = caddy.check_existing_call(
                event["thread_id"]
            )

            if survey_complete is True:
                google_chat.update_message_in_adviser_space(
                    space_id=event["space_id"],
                    message_id=event["message_id"],
                    message=google_chat.messages["SURVEY_ALREADY_COMPLETED"],
                )
                return

            if existing_call is False:
                (
                    modules_to_use,
                    module_outputs_json,
                    continue_conversation,
                    control_group_message,
                ) = execute_optional_modules(
                    event, execution_time="before_message_processed"
                )
                caddy.store_evaluation_module(
                    thread_id=event["thread_id"],
                    user_arguments=modules_to_use[0],
                    argument_output=module_outputs_json,
                    continue_conversation=continue_conversation,
                    control_group_message=control_group_message,
                )
            elif existing_call is True:
                modules_to_use = values["modulesUsed"]
                module_outputs_json = values["moduleOutputs"]
                continue_conversation = values["continueConversation"]
                control_group_message = values["controlGroupMessage"]

            message_query = caddy.format_chat_message(event)

            caddy.store_message(message_query)

            if continue_conversation is False:
                google_chat.update_message_in_adviser_space(
                    message_query.conversation_id,
                    message_query.message_id,
                    {"text": control_group_message},
                )
                if survey_complete is False:
                    google_chat.run_survey(
                        message_query.user,
                        message_query.thread_id,
                        message_query.conversation_id,
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

            llm_response, source_documents = caddy.query_llm(
                message_query, chat_history
            )

            response_card = google_chat.create_card(llm_response, source_documents)
            response_card = json.dumps(response_card)

            llm_response.llm_response_json = response_card

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
