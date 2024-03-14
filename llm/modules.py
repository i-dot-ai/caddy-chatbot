import random
from responses import send_message_to_adviser_space, update_message_in_adviser_space


def randomisation(event, split, control_group_message):
    """ Randomly assign users to a control group, and send them a message """
    space_id = event['space_id']
    thread_id = event['thread_id']

    random_number = random.random()

    if random_number < split:
        message = "Caddy is not available on your current call.  Please check back when the call is complete."
        send_message_to_adviser_space(space_id, message, thread_id)
        return "control", "end_interaction"

    else:
        return "treatment", "continue_interaction"